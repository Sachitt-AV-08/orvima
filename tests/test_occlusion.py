"""Occlusion handling, with a fake page so the retry logic is pinned directly.

The live tests in test_sticky_headers.py cover the geometry inside the JS, which
cannot be executed without a browser. These cover the Python around it: the
retry budget, and - more importantly - that a case which cannot be fixed is
reported on the first observation rather than retried.
"""

from __future__ import annotations

import inspect

import orvima.occlusion as mod
from orvima.occlusion import uncover


class FakePage:
    """Stands in for a Playwright page.

    Simulates the *result* the JS would produce, so it cannot catch a bug inside
    the JS - that is an honest limit, and the live tests cover it. What this
    pins is the control flow around it, which is pure Python and easy to get
    wrong in a way that looks fine.
    """

    def __init__(self, script):
        self._script = script
        self.calls = 0
        self.args: list = []

    def evaluate(self, _expression, arg=None):
        self.calls += 1
        self.args.append(arg)
        return self._script(self.calls)


class TestAlreadyClear:
    def test_a_clear_element_needs_no_scroll(self):
        page = FakePage(lambda n: {"occluded": False, "scrolled": 0})
        result = uncover(page, "#x")
        assert result["uncovered"] is True
        assert page.calls == 1, "it re-probed an element that was never occluded"

    def test_a_missing_element_is_named_not_guessed(self):
        page = FakePage(lambda n: {"error": "no such element"})
        result = uncover(page, "#gone")
        assert result["uncovered"] is False
        assert result["error"] == "no such element"

    def test_the_selector_and_margin_are_passed_through(self):
        """The JS reads arg[0] as the selector and arg[1] as the margin.

        Passing the wrong shape makes `selector` undefined inside the page, and
        the resulting `querySelector(undefined)` error is opaque.
        """
        page = FakePage(lambda n: {"occluded": False})
        uncover(page, "#x", margin=9)
        assert page.args[0] == ["#x", 9]


class TestRecovery:
    def test_one_scroll_then_clear_is_the_normal_case(self):
        states = iter(
            [
                {"occluded": True, "scrollable": True, "scrolled": 51, "blockers": ["bar"]},
                {"occluded": False, "scrolled": 0},
            ]
        )
        page = FakePage(lambda n: next(states))
        result = uncover(page, "#x")
        assert result["uncovered"] is True
        assert result["scrolled"] == 51
        assert result["cleared"] == ["bar"]

    def test_it_retries_while_scrolling_still_helps(self):
        states = iter(
            [
                {"occluded": True, "scrollable": True, "scrolled": 20, "blockers": ["bar"]},
                {"occluded": True, "scrollable": True, "scrolled": 20, "blockers": ["bar"]},
                {"occluded": False, "scrolled": 0},
            ]
        )
        page = FakePage(lambda n: next(states))
        result = uncover(page, "#x", attempts=3)
        assert result["uncovered"] is True
        assert result["attempts"] == 3

    def test_the_attempt_budget_is_respected(self):
        page = FakePage(
            lambda n: {"occluded": True, "scrollable": True, "scrolled": 10, "blockers": ["bar"]}
        )
        result = uncover(page, "#x", attempts=3)
        assert result["uncovered"] is False
        assert result["attempts"] == 3
        assert page.calls == 3


class TestUnfixableCasesReportImmediately:
    """The property that matters most.

    When scrolling cannot clear the overlay, retrying is pure waste: the geometry
    is fixed, so the second and third attempts return the same answer. Reporting
    on the first observation is what lets a caller say "a sticky header covers
    this" instead of surfacing a 10-second timeout that mentions nothing.
    """

    def test_a_page_pinned_at_the_top_reports_at_once(self):
        page = FakePage(
            lambda n: {
                "occluded": True,
                "scrollable": False,
                "blockers": ["bar"],
                "reason": "already at the top of the page; no scroll left to clear the overlay",
                "scrollY": 0,
                "maxScroll": 0,
            }
        )
        result = uncover(page, "#x")
        assert result["uncovered"] is False
        assert "no scroll left" in result["reason"]
        assert result["blockers"] == ["bar"]
        assert page.calls == 1, f"retried {page.calls} times on an unfixable layout"

    def test_a_page_pinned_at_the_bottom_reports_at_once(self):
        page = FakePage(
            lambda n: {
                "occluded": True,
                "scrollable": False,
                "blockers": ["footer"],
                "reason": "already at the bottom of the page; no scroll left to clear the overlay",
            }
        )
        result = uncover(page, "#x")
        assert result["uncovered"] is False
        assert "no scroll left" in result["reason"]
        assert page.calls == 1

    def test_an_in_flow_occluder_is_distinguished_from_a_pinned_one(self):
        """A modal scrim cannot be scrolled past, and must not be described as
        a sticky header - the caller's next move differs."""
        page = FakePage(
            lambda n: {
                "occluded": True,
                "scrollable": False,
                "blockers": ["scrim"],
                "reason": "covered by an in-flow element, which scrolling cannot clear",
            }
        )
        result = uncover(page, "#x")
        assert result["uncovered"] is False
        assert "in-flow" in result["reason"]
        assert page.calls == 1

    def test_a_zero_delta_occlusion_is_not_retried(self):
        """delta 0 with no scrollable flag is a wall in disguise.

        Scrolling by zero cannot change what is on top, so this must be
        reported immediately like any other unfixable case.
        """
        page = FakePage(
            lambda n: {
                "occluded": True,
                "scrollable": False,
                "blockers": ["veil"],
                "delta": 0,
                "reason": "the element cannot be positioned clear of the overlay in this viewport",
            }
        )
        result = uncover(page, "#x")
        assert result["uncovered"] is False
        assert page.calls == 1

    def test_a_missing_reason_still_produces_a_readable_one(self):
        page = FakePage(lambda n: {"occluded": True, "scrollable": False})
        result = uncover(page, "#x")
        assert result["uncovered"] is False
        assert result["reason"], "an unfixable case with no reason is not actionable"


class TestRecoveryIsReported:
    """What a caller learns about a successful recovery.

    An agent that just scrolled the page under an element it is about to act on
    is in a materially different position from one that acted immediately, and it
    cannot know that unless the result says so.
    """

    def test_a_plain_element_reports_no_movement_and_no_occluder(self):
        page = FakePage(lambda n: {"occluded": False, "blockers": []})
        result = uncover(page, "#x")
        assert result["uncovered"] is True
        assert result["scrolled"] == 0
        assert result["cleared"] == [], (
            "nothing was covering the element, so nothing should be named as "
            "having been cleared"
        )

    def test_a_scrolled_element_reports_the_distance_and_the_occluder(self):
        states = iter(
            [
                {"occluded": True, "scrollable": True, "scrolled": 51, "blockers": ["bar"]},
                {"occluded": False, "blockers": []},
            ]
        )
        page = FakePage(lambda n: next(states))
        result = uncover(page, "#x")
        assert result["uncovered"] is True
        assert result["scrolled"] == 51, (
            "the page moved, and the caller must be able to see that it moved"
        )
        assert result["cleared"] == ["bar"], (
            "the occluder was erased by the clearing observation, so the caller "
            "cannot report what was in the way"
        )
        assert result["blockers"] == [], "nothing is covering it any more"

    def test_the_distance_sums_across_multiple_legs(self):
        states = iter(
            [
                {"occluded": True, "scrollable": True, "scrolled": 20, "blockers": ["bar"]},
                {"occluded": True, "scrollable": True, "scrolled": 31, "blockers": ["bar"]},
                {"occluded": False, "blockers": []},
            ]
        )
        page = FakePage(lambda n: next(states))
        result = uncover(page, "#x", attempts=3)
        assert result["uncovered"] is True
        assert result["scrolled"] == 51, (
            f"two legs of 20 and 31 should total 51, got {result['scrolled']}"
        )


class TestTheSafetyBoundary:
    """`uncover` moves the page and reports. It must never act.

    This is the property the whole module exists to protect: a page is moved so
    the *caller* can look again and decide, not so the module can guess. Asserted
    against the source, because a runtime check could not tell the difference.
    """

    def test_uncover_calls_no_page_actions(self):
        source = inspect.getsource(uncover)
        for forbidden in (".click(", ".fill(", ".type(", ".press(", ".tap(", ".check("):
            assert forbidden not in source, (
                f"uncover() calls {forbidden!r}. It may only move the page and "
                "report - acting on a possibly still-occluded element is the "
                "failure this module exists to prevent"
            )

    def test_uncover_only_uses_evaluate(self):
        """Belt and braces: the page interaction surface is exactly one call."""
        source = inspect.getsource(uncover)
        assert source.count("page.evaluate") == 1

    def test_the_js_never_dispatches_input_events(self):
        """The JS must not synthesise clicks either.

        `element.click()` in page script would bypass Playwright entirely and
        could hit whatever is on top. Only scrolling is allowed.
        """
        js = mod._UNCOVER_JS
        for forbidden in (".click()", "dispatchEvent", "MouseEvent", "KeyboardEvent", ".submit("):
            assert forbidden not in js, (
                f"the in-page script contains {forbidden!r}; it may only scroll"
            )

    def test_the_js_scrolls_with_scroll_to_not_scroll_by_blindness(self):
        """scrollTo with a computed target, so the clamp is checkable."""
        assert "window.scrollTo(0, target)" in mod._UNCOVER_JS


class TestMarginDefault:
    def test_the_default_margin_is_positive(self):
        """A zero margin rounds the element straight back under the bar's edge."""
        assert mod._CLEAR_MARGIN_PX > 0
