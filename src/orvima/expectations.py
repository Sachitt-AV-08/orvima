"""Intent-level verification: did the action do what the caller meant?

The signature check that predates this module asks "did anything change?". That
is a low bar, and it is easy to pass. A click that navigates to the *wrong*
account, opens a modal instead of confirming, or lands on a page whose text
happened to shift all report success. An agent that trusts those reports
proceeds confidently on a page it is not on.

So callers may state what they expected, and the action is judged against that:

- ``expect_url``   - a substring of the resulting url
- ``expect_text``  - a substring of the resulting page text
- ``expect_count`` - an exact number of elements matching the acted-on selector

All three are optional and default to ``None``, which preserves today's
signature-level behaviour exactly. Nothing here changes for a caller who does
not opt in - that is the whole reason this is additive. In particular no
expectation keys appear in the result of a caller who stated none; a caller
should not have to learn about a feature it did not use.

``expect_count`` needs something to count. It counts the acted-on element by
default, which covers "click the accordion and expect one expanded panel". For
the far more common "click the filter, expect 3 results in the list" the acted
element is the button, not the results, so a caller can name a different target
with ``expect_for``. Without that the feature is close to useless for lists,
which is where a count is usually wanted.

Failure is a hard error rather than a ``verified: false`` flag. The caller asked
for a specific outcome; getting a different one means the action did not do what
was intended, and a flag that a caller can ignore is how verification becomes
theatre. The mitigation in the plan for that risk is "never report success
without evidence", and the evidence is the expectation.

Each expectation is polled rather than sampled once, because the outcome of a
click is frequently asynchronous - a navigation, a spinner, a fetch. A single
check immediately after the action would fail on a page that was about to be
correct. The wait is bounded and reports what it actually saw.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

#: Default time an expectation is given to come true. Long enough for a
#: navigation or a fetch, short enough that a genuinely wrong outcome fails
#: rather than stalling the run.
DEFAULT_EXPECT_TIMEOUT_MS = 5000

#: How often the page is re-read while waiting.
_POLL_INTERVAL_S = 0.1


@dataclass
class Expectation:
    """One stated expectation and what actually turned out to be true."""

    kind: str  # "url" | "text" | "count"
    wanted: Any
    seen: Any = None
    ok: bool = False

    def describe(self) -> str:
        """A human-readable account, used in error messages."""
        if self.kind == "url":
            return f"expected url to contain {self.wanted!r}, got {self.seen!r}"
        if self.kind == "text":
            return f"expected the page to show {self.wanted!r}, it does not"
        if self.kind == "count":
            return f"expected {self.wanted} matching element(s), found {self.seen}"
        return f"expected {self.kind}={self.wanted!r}, got {self.seen!r}"


@dataclass
class ExpectationSet:
    """All of a caller's expectations, plus the polling outcome."""

    url: str | None = None
    text: str | None = None
    count: int | None = None
    timeout_ms: int = DEFAULT_EXPECT_TIMEOUT_MS
    #: What expect_count counts. None means "the acted-on element".
    count_target: str | None = None

    def any_given(self) -> bool:
        return any(v is not None for v in (self.url, self.text, self.count))

    def kinds_given(self) -> list[str]:
        return [k for k, v in (("url", self.url), ("text", self.text), ("count", self.count)) if v is not None]


@dataclass
class VerificationReport:
    """The result of checking a set of expectations."""

    passed: bool = True
    checks: list[Expectation] = field(default_factory=list)
    waited_ms: int = 0

    def failures(self) -> list[Expectation]:
        return [c for c in self.checks if not c.ok]

    def summary(self) -> dict:
        """A compact form for a tool result: what was expected, what was seen."""
        return {
            "expectationsMet": self.passed,
            "waitedMs": self.waited_ms,
            "checks": [
                {"kind": c.kind, "wanted": c.wanted, "seen": c.seen, "ok": c.ok}
                for c in self.checks
            ],
        }

    def failure_message(self) -> str:
        """Name every unmet expectation, not just the first.

        Reporting one at a time means a caller fixes it, retries, and discovers
        the next. Every unmet expectation is named in a single pass.
        """
        if self.passed:
            return ""
        parts = [c.describe() for c in self.failures()]
        plural = "expectation" if len(parts) == 1 else "expectations"
        return (
            f"{len(parts)} {plural} not met after {self.waited_ms}ms: "
            + "; ".join(parts)
        )


def _norm(value: Any) -> str:
    """Whitespace-collapsed, for comparing page text without its layout."""
    return " ".join(str(value or "").split()).strip().lower()


class ExpectationChecker:
    """Polls a page until every stated expectation holds, or the wait runs out.

    Constructed around a reader callable rather than a BrowserController, so the
    polling logic is testable without a browser and so this module has no
    opinion about how the page is read.
    """

    def __init__(self, read_page, read_count):
        """
        ``read_page()`` -> dict with at least ``url`` and ``text``.
        ``read_count(selector)`` -> int, or None when the selector cannot be read.
        """
        self._read_page = read_page
        self._read_count = read_count

    def check(self, expectations: ExpectationSet, selector: str | None = None) -> VerificationReport:
        """Wait for every expectation, then report.

        ``selector`` is the acted-on element, used as the default target for
        ``expect_count``. ``expectations.count_target`` overrides it.
        """
        if not expectations.any_given():
            return VerificationReport(passed=True)

        target = expectations.count_target or selector
        deadline = time.monotonic() + max(0, expectations.timeout_ms) / 1000
        report = VerificationReport(passed=True)
        started = time.monotonic()

        while True:
            page = self._read_page()
            checks = self._evaluate(expectations, page, target)
            report.checks = checks
            report.passed = all(c.ok for c in checks)

            if report.passed:
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(_POLL_INTERVAL_S)

        report.waited_ms = int((time.monotonic() - started) * 1000)
        return report

    def _evaluate(self, expectations: ExpectationSet, page: dict, selector: str | None) -> list[Expectation]:
        checks: list[Expectation] = []

        if expectations.url is not None:
            actual = page.get("url") or ""
            checks.append(
                Expectation(
                    kind="url",
                    wanted=expectations.url,
                    seen=actual,
                    # Substring, so a caller can pin a path or a query without
                    # having to reproduce the whole url including a session id.
                    ok=expectations.url in actual,
                )
            )

        if expectations.text is not None:
            actual = page.get("text") or ""
            wanted = _norm(expectations.text)
            seen = _norm(actual)
            checks.append(
                Expectation(
                    kind="text",
                    wanted=expectations.text,
                    # Only whether it was present. Echoing 3000 characters of
                    # page text into an error message helps nobody, and the
                    # snapshot already carries the text for a caller that needs it.
                    seen="present" if wanted and wanted in seen else "absent",
                    ok=bool(wanted) and wanted in seen,
                )
            )

        if expectations.count is not None:
            actual = self._read_count(selector) if selector else None
            checks.append(
                Expectation(
                    kind="count",
                    wanted=expectations.count,
                    seen=actual if actual is not None else "unreadable",
                    # Exact equality, not ">=" or "<=". "3 results" and "300
                    # results" are not the same outcome, and an approximate match
                    # would let a filter that did nothing pass.
                    ok=actual is not None and actual == expectations.count,
                )
            )

        return checks
