"""Intent-level verification against a real page.

The gate the plan asks for, in both directions:

- a click that navigates to the WRONG page fails when an expectation was given
- the same click still passes when none was given

Both matter. If the second failed, adding expectations would have broken every
existing caller. If the first failed, the feature would be decoration.

The fixture makes this a real test rather than a formality: clicking "Pay now
(beta)" navigates, changes the DOM, and reports success by every signature-level
measure available. Only stating what you expected reveals that the agent is now
on the wrong page. That is the scenario this phase exists for - a silent wrong
outcome, not a crash.

Run: pytest tests/test_expect.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_real_mode import _skip_reason  # noqa: E402

if _skip_reason:
    pytestmark = pytest.mark.skip(reason=_skip_reason)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CHECKOUT = (FIXTURES_DIR / "checkout_page.html").resolve().as_uri()

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402
from orvima.tools import tool_browse_click, tool_browse_navigate  # noqa: E402


@pytest.fixture(scope="module")
def ctl():
    controller = BrowserController(headless=True)
    controller.start()
    try:
        yield controller
    finally:
        controller.close()


class TestTheWrongPageIsCaught:
    """The direction that matters: a wrong outcome must not read as success."""

    def test_a_click_landing_on_the_wrong_page_fails_an_expectation(self, ctl):
        ctl.navigate(CHECKOUT)
        with pytest.raises(BrowserError) as caught:
            ctl.click(
                "#wrong",
                expect_url="nav_target",
                expect_timeout_ms=1500,
            )
        message = str(caught.value)
        assert "expected url to contain 'nav_target'" in message
        assert "trap.html" in message, "the error should show where it actually went"

    def test_the_wrong_page_click_reports_failure_through_the_tool(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(ctl, selector="#wrong", expect_url="nav_target")
        assert not result.get("ok"), f"the tool reported a wrong-page click as ok: {result}"
        assert "expected url to contain" in result.get("error", "")

    def test_text_mismatch_is_caught_too(self, ctl):
        """A url can look right while the page is wrong - a stale shell, a
        banner, an error rendered in place. Checking the text catches that."""
        ctl.navigate(CHECKOUT)
        with pytest.raises(BrowserError) as caught:
            ctl.click("#wrong", expect_text="Order confirmed", expect_timeout_ms=1500)
        assert "expected the page to show 'Order confirmed'" in str(caught.value)

    def test_the_check_fails_even_though_the_click_genuinely_worked(self, ctl):
        """Confirms the test is measuring intent, not action success.

        If this click did not really navigate, every assertion above would pass
        for the wrong reason.
        """
        ctl.navigate(CHECKOUT)
        before = ctl.page.url
        ctl.click("#wrong")
        assert ctl.page.url != before, "the fixture did not navigate; the test is vacuous"
        assert ctl.page.url.endswith("trap.html")
        assert "Order confirmed" not in (ctl.page.content() or "")


class TestTheOrdinaryPathIsUnchanged:
    """The direction that keeps this additive."""

    def test_the_same_click_succeeds_when_no_expectation_is_given(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(ctl, selector="#wrong")
        assert result.get("ok"), (
            "adding expectations broke a caller who uses none - the same "
            f"click must still work: {result}"
        )

    def test_a_correct_expectation_passes(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(ctl, selector="#good", expect_url="nav_target")
        assert result.get("ok"), result
        assert result.get("expectationsMet") is True
        checks = {c["kind"]: c for c in result.get("checks", [])}
        assert checks["url"]["ok"] is True

    def test_a_correct_url_expectation_plus_text_passes(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(
            ctl,
            selector="#good",
            expect_url="nav_target",
            expect_text="Order confirmed",
        )
        assert result.get("ok"), result
        assert len(result.get("checks", [])) == 2

    def test_expectations_are_absent_from_the_result_when_none_were_asked_for(self, ctl):
        """The result shape must not grow keys a caller has to learn about."""
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(ctl, selector="#good")
        assert result.get("ok")
        assert "expectationsMet" not in result, (
            "an unstated expectation still added a key to the result"
        )


class TestCountExpectation:
    """The case a count is usually wanted for: a filtered result list.

    This is why expect_for exists. Counting the clicked element - the filter
    button - can only ever be 1, which verifies nothing.
    """

    def test_a_filter_can_verify_the_result_list_it_changed(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(
            ctl, selector="#filter", expect_count=3, expect_for=".result"
        )
        assert result.get("ok"), result
        check = result["checks"][0]
        assert check["kind"] == "count"
        assert check["seen"] == 3, "did not count the results the filter left behind"

    def test_a_wrong_count_is_caught(self, ctl):
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(
            ctl, selector="#filter", expect_count=99, expect_for=".result"
        )
        assert not result.get("ok"), f"a list of 3 passed a check for 99: {result}"
        assert "expected 99 matching element(s), found 3" in result.get("error", "")

    def test_without_expect_for_the_clicked_element_is_counted(self, ctl):
        """The documented default, stated so it cannot change unnoticed."""
        ctl.navigate(CHECKOUT)
        result = tool_browse_click(ctl, selector="#filter", expect_count=1)
        assert result.get("ok"), result
        assert result["checks"][0]["seen"] == 1, "expected the button itself to be counted"


class TestNavigateExpectation:
    def test_navigating_to_the_expected_place_passes(self, ctl):
        target = CHECKOUT.replace("checkout_page.html", "nav_target.html")
        result = tool_browse_navigate(ctl, target, expect_text="Order confirmed")
        assert result.get("ok"), result

    def test_navigating_with_a_wrong_expectation_fails(self, ctl):
        trap = CHECKOUT.replace("checkout_page.html", "trap.html")
        result = tool_browse_navigate(ctl, trap, expect_text="Order confirmed")
        assert not result.get("ok")
        assert "expected the page to show 'Order confirmed'" in result.get("error", "")

    def test_navigate_without_expectations_is_unchanged(self, ctl):
        trap = CHECKOUT.replace("checkout_page.html", "trap.html")
        result = tool_browse_navigate(ctl, trap)
        assert result.get("ok")
        assert "expectationsMet" not in result


class TestAsynchronousOutcomes:
    def test_a_slow_page_is_waited_for_rather_than_failed(self, ctl):
        """A single immediate check would fail here, and a caller who hit that
        once would stop using expectations entirely."""
        ctl.navigate(CHECKOUT)
        # Aim at the filter, which updates the page text after the click.
        result = tool_browse_click(
            ctl, selector="#filter", expect_text="showing 1 of 3", expect_timeout_ms=3000
        )
        assert result.get("ok"), result
