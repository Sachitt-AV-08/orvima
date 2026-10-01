"""Intent-level verification, with no browser involved.

The polling logic is deliberately separated from Playwright: ExpectationChecker is
constructed around two reader callables, so what matters here is the decision
logic - when to keep waiting, when to give up, and what to report - and none of it
needs a page.

Run: pytest tests/test_expectations.py -q
"""

from __future__ import annotations

from orvima.expectations import ExpectationChecker, ExpectationSet


class FakePage:
    """A page whose url and text can be scripted, changing over time."""

    def __init__(self, script: list[dict] | None = None, url: str = "https://x.test/a", text: str = ""):
        # Each entry is the state after one poll; the last entry repeats.
        self._script = script or []
        self._url = url
        self._text = text
        self._polls = 0

    def read(self) -> dict:
        self._polls += 1
        if self._polls <= len(self._script):
            state = self._script[self._polls - 1]
            self._url = state.get("url", self._url)
            self._text = state.get("text", self._text)
        return {"url": self._url, "text": self._text}


def checker(page: FakePage, count: int | None = 3):
    return ExpectationChecker(page.read, lambda _sel: count)


# --- the additive promise ---------------------------------------------------


def test_no_expectation_means_no_checking():
    """The whole reason this is optional: nothing changes for a caller who
    does not opt in, and the wait costs nothing."""
    page = FakePage(url="https://x.test/somewhere-else")
    report = checker(page).check(ExpectationSet(timeout_ms=5000))
    assert report.passed
    assert report.checks == []
    assert page._polls == 0, "an unstated expectation still polled the page"


def test_a_mismatch_you_never_asked_about_is_not_a_failure():
    page = FakePage(url="https://x.test/wrong", text="nothing you wanted")
    report = checker(page).check(ExpectationSet(timeout_ms=100))
    assert report.passed, "verified itself against expectations nobody stated"


# --- url ---------------------------------------------------------------------


def test_a_url_that_never_matches_fails():
    page = FakePage(url="https://x.test/login?next=%2Fhome")
    report = checker(page).check(ExpectationSet(url="/home", timeout_ms=200))
    assert not report.passed
    assert "expected url to contain '/home'" in report.failure_message()


def test_a_url_matching_as_a_substring_passes():
    """A caller pins a path or query, not a session id they cannot know."""
    page = FakePage(url="https://x.test/home?session=abc123")
    report = checker(page).check(ExpectationSet(url="/home", timeout_ms=200))
    assert report.passed


def test_an_asynchronous_navigation_is_waited_for():
    """Sampling once would fail on a page that was about to be correct, which
    would train a caller not to use expectations at all."""
    page = FakePage(
        script=[
            {"url": "https://x.test/loading"},
            {"url": "https://x.test/loading"},
            {"url": "https://x.test/done"},
        ]
    )
    report = checker(page).check(ExpectationSet(url="/done", timeout_ms=3000))
    assert report.passed
    assert page._polls >= 3, "gave up before the page settled"


# --- text --------------------------------------------------------------------


def test_absent_text_is_reported_as_absent_not_dumped():
    """Echoing 3000 characters of page text into an error helps nobody."""
    page = FakePage(text="Welcome back. Your cart is empty.")
    report = checker(page).check(ExpectationSet(text="Order confirmed", timeout_ms=200))
    assert not report.passed
    failure = report.failures()[0]
    assert failure.seen == "absent"
    assert failure.describe() == (
        "expected the page to show 'Order confirmed', it does not"
    )


def test_text_matching_ignores_layout_whitespace_and_case():
    page = FakePage(text="Order\n   confirmed\n   for  3 items")
    report = checker(page).check(ExpectationSet(text="order confirmed", timeout_ms=200))
    assert report.passed


def test_empty_expectation_text_never_matches_anything():
    """A caller passing "" means a bug, not a wildcard. Matching every page
    would report success for an action that did nothing."""
    page = FakePage(text="anything at all")
    report = checker(page).check(ExpectationSet(text="", timeout_ms=200))
    assert not report.passed


# --- count -------------------------------------------------------------------


def test_count_is_exact_not_approximate():
    """"3 results" and "300 results" are not the same outcome, and a >= style
    check would let a filter that did nothing pass.

    The page really has 300 matches. Expecting 3 must fail - that is the whole
    point of the exact check.
    """
    page = FakePage()
    assert not checker(page, count=300).check(
        ExpectationSet(count=3, timeout_ms=100), selector=".result"
    ).passed, "300 results satisfied an expectation of 3"
    assert checker(page, count=300).check(
        ExpectationSet(count=300, timeout_ms=100), selector=".result"
    ).passed


def test_an_unreadable_count_fails_rather_than_passing():
    page = FakePage()
    report = checker(page, count=None).check(
        ExpectationSet(count=2, timeout_ms=100), selector=".result"
    )
    assert not report.passed, "could not count anything, but reported success"
    assert "unreadable" in report.failure_message()


def test_a_count_with_no_selector_cannot_be_checked():
    page = FakePage()
    report = checker(page).check(ExpectationSet(count=1, timeout_ms=100), selector=None)
    assert not report.passed


# --- multiple expectations ---------------------------------------------------


def test_every_unmet_expectation_is_named_at_once():
    """Reporting one at a time means a caller fixes it, retries, and finds the
    next - a slow loop for information we already had."""
    page = FakePage(url="https://x.test/a", text="nothing")
    report = checker(page).check(
        ExpectationSet(url="/b", text="Order confirmed", count=7, timeout_ms=200)
    )
    message = report.failure_message()
    assert message.startswith("3 expectations not met")
    assert "/b" in message
    assert "Order confirmed" in message
    assert "expected 7 matching element(s)" in message


def test_one_satisfied_expectation_does_not_mask_a_failed_one():
    page = FakePage(url="https://x.test/right", text="nothing")
    report = checker(page).check(
        ExpectationSet(url="/right", text="Order confirmed", timeout_ms=200)
    )
    assert not report.passed
    assert len(report.failures()) == 1
    assert report.checks[0].ok and not report.checks[1].ok


# --- reporting ---------------------------------------------------------------


def test_the_summary_is_serialisable_and_names_what_was_seen():
    page = FakePage(url="https://x.test/login")
    report = checker(page).check(ExpectationSet(url="/home", timeout_ms=100))
    summary = report.summary()
    assert summary["expectationsMet"] is False
    assert summary["checks"][0] == {
        "kind": "url",
        "wanted": "/home",
        "seen": "https://x.test/login",
        "ok": False,
    }
    assert summary["waitedMs"] >= 0


def test_a_zero_timeout_still_checks_once():
    """A caller who sets no timeout should not get a free pass - but must not
    hang either."""
    page = FakePage(url="https://x.test/right")
    report = checker(page).check(ExpectationSet(url="/right", timeout_ms=0))
    assert report.passed
    assert page._polls == 1, f"polled {page._polls} times with a zero timeout"
