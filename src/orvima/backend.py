"""The navigation contract, implemented once.

`expect_url` and `expect_text` promise the caller that an action is judged
against what they said they wanted, not merely against whether the DOM moved.
That promise was implemented on `BrowserController` and left as an
unconditional `"verified": True` on the other two navigation backends, so the
tool layer forwarded an expectation that two backends silently discarded.

The failure mode this causes is worse than a missing feature. A verification
result that always says "verified" cannot be used to detect a verification
failure, and `orvima.bench` drives the agent through one of these backends - so
the benchmark that is supposed to measure the agent's judgement is itself
incapable of an incorrect judgement.

So the contract lives here, once, and a backend supplies only primitives:

    _perform_navigate(url)   move. Must not substitute a different destination.
    _state()                 {"url": ..., "title": ...}
    _read_page_state()       {"url": ..., "text": ...}
    _count_matching(sel)     int, or None when it genuinely cannot be read.

`navigate` is implemented in terms of those, and a test asserts that no
subclass overrides it - so the next backend cannot reintroduce the bug by
accident.

`verified` is derived here rather than asserted. A backend that quietly swaps
the requested url for one it can serve must report `verified: False`, which is
what `_landed_on` checks; `DemoBrowser` used to fold every unknown url back to
its home page and call that a successful navigation.
"""

from __future__ import annotations

from .errors import BrowserError
from .expectations import DEFAULT_EXPECT_TIMEOUT_MS, ExpectationChecker, ExpectationSet


def _landed_on(requested: str, landed: str | None) -> bool:
    """Whether the page we ended up on is the page that was asked for.

    Compares the parts a redirect cannot change without changing the meaning of
    the request: the host and the path. Query and fragment are ignored, because
    a site that reorders or re-encodes them has not gone somewhere else, and a
    trailing slash is not a different page.

    A redirect to a login page or to another account changes the host or the
    path, so this is False there - which is the case `expect_url` was written
    for, and the reason "did the DOM move" was never enough.
    """
    if not landed:
        return False
    want, got = requested.strip(), landed.strip()
    if want == got:
        return True

    def normalise(url: str) -> str:
        return url.rstrip("/").rsplit("?", 1)[0].rsplit("#", 1)[0].lower()

    return normalise(want) == normalise(got)


class NavigationBackend:
    """Mixin providing navigation and its verification, for any page backend.

    Subclasses implement `_perform_navigate` plus the readers. They do not
    implement `navigate`, and must not: overriding it would hand the
    expectation contract back to a backend that previously dropped it.
    """

    #: Whether this backend's navigate result includes `load_state`. The real
    #: controller reports a Playwright load state; the in-memory backends have
    #: no load event to report, and inventing one would be a claim about a
    #: browser that is not there.
    REPORTS_LOAD_STATE = False

    # ---------------------------------------------------------- primitives --
    def _perform_navigate(self, url: str) -> None:
        """Move to `url`. Must land on `url` or raise.

        Folding an unreachable url onto some other page is not permitted: the
        whole point of this class is that the destination is checkable.
        """
        raise NotImplementedError

    def _state(self) -> dict:
        """`{"url": ..., "title": ...}` for the current page."""
        raise NotImplementedError

    def _read_page_state(self) -> dict:
        """`{"url": ..., "text": ...}`, for polling an expectation.

        Returning a real text body is what makes `expect_text` meaningful on
        this backend. Returning "" is honest for a backend with no page content,
        but then every `expect_text` fails - which is the correct outcome, since
        it cannot be shown otherwise.
        """
        raise NotImplementedError

    def _count_matching(self, selector: str | None) -> int | None:
        """How many elements `selector` matches, or None when unreadable.

        None is not a failure to answer; it is the answer "I cannot tell". The
        checker treats it as unmet, so an unreadable count cannot pass a count
        expectation.
        """
        return None

    def _perform_click(self, selector: str) -> dict:
        """Click `selector` and return a result including `verified`.

        `verified` here is the signature-level check - "did something change" -
        which a click on the wrong element can pass. Intent-level checking is
        the base class's job, from the expectation the caller stated.
        """
        raise NotImplementedError

    # ------------------------------------------------------------ contract --
    def navigate(self, url: str, **expect) -> dict:
        """Navigate to `url`, judged against any expectation the caller stated.

        Raises `BrowserError` when a stated expectation does not come true. A
        hard error rather than a `verified: False` flag: the caller asked for a
        specific outcome, and a flag they may ignore is how verification becomes
        theatre.
        """
        self._perform_navigate(url)
        state = self._state()
        landed = state.get("url")
        report = self._check_expectations(expect, None)
        result = {
            **state,
            "verified": _landed_on(url, landed),
            **report,
        }
        if self.REPORTS_LOAD_STATE:
            result["load_state"] = "domcontentloaded"
        return result

    def click(self, selector: str, **expect) -> dict:
        """Click `selector`, judged against any expectation the caller stated.

        Also implemented here rather than per backend. A click is the action
        where a wrong outcome is most expensive and most silent: it lands on the
        wrong account, opens a modal instead of confirming, or dismisses the
        very dialog the agent should have read. So both in-memory backends
        shipped a `click` that took the expectation keywords and dropped them.
        """
        result = self._perform_click(selector)
        # Judged against the selector the caller named, not the attribute
        # selector a ref resolves to, so `expect_count` counts what was aimed at.
        report = self._check_expectations(expect, selector)
        return {**result, **report}

    def _check_expectations(self, expect: dict, selector: str | None) -> dict:
        """Judge an action against what the caller said it expected.

        Returns a dict to merge into the tool result. It is **empty** when the
        caller stated no expectation, not a passing report: adding
        ``expectationsMet`` to every result would make a feature nobody asked
        for part of the contract every caller has to read.
        """
        wanted = ExpectationSet(
            url=expect.get("expect_url"),
            text=expect.get("expect_text"),
            count=expect.get("expect_count"),
            count_target=expect.get("expect_for"),
            timeout_ms=expect.get("expect_timeout_ms", DEFAULT_EXPECT_TIMEOUT_MS),
        )
        if not wanted.any_given():
            return {}

        report = ExpectationChecker(self._read_page_state, self._count_matching).check(
            wanted, selector
        )
        if not report.passed:
            raise BrowserError(
                f"the action completed but {report.failure_message()}. "
                "The page may have gone somewhere other than intended - check "
                "where you actually are before continuing"
            )
        return report.summary()
