"""Ref identity across a re-render, against a real browser.

Unit tests in test_identity.py cover the matching logic. These cover the thing
that actually matters: whether a *click* lands on the right element after the
page rebuilds itself underneath the agent.

The fixture (rerender_page.html) re-renders shortly after load, which is after
any snapshot has been taken, and records which element was really clicked. The
assertion is on that record, not on the DOM afterwards - inferring intent from
the final page state is exactly the mistake that lets a hijacked ref pass.

Run: pytest tests/test_rerender.py -q
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_real_mode import _skip_reason  # noqa: E402

if _skip_reason:
    pytestmark = pytest.mark.skip(reason=_skip_reason)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RERENDER = (FIXTURES_DIR / "rerender_page.html").resolve().as_uri()

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402


@pytest.fixture
def ctl():
    """One browser for the whole test, not one per assertion.

    Each launch costs ~1.5 GB on this machine, and a class where every method
    built its own controller exhausted memory mid-file and turned a logic
    failure into a confusing "could not start a browser". A session-scoped
    controller and an explicit navigate per test keeps the footprint flat.
    """
    controller = BrowserController(headless=True)
    controller.start()
    try:
        yield controller
    finally:
        controller.close()


def ref_for(ctl: BrowserController, label: str) -> str:
    """The ref the snapshot assigned to the button with this text."""
    snap = ctl.snapshot()
    for item in snap.get("items", []):
        if label.lower() in (item.get("label") or item.get("text") or "").lower():
            return item["ref"]
    raise AssertionError(f"no ref found for {label!r}: {snap.get('items')}")


def wait_for_rerender(ctl: BrowserController) -> None:
    for _ in range(60):
        if ctl.page.evaluate("() => window.__rerenderFired"):
            return
        time.sleep(0.05)
    raise AssertionError("the fixture never re-rendered")


class TestRefSurvivesReplace:
    """The node is destroyed and an identical one created - the common case."""

    def test_click_lands_on_the_intended_element_after_a_rebuild(self, ctl):
        ctl.navigate(RERENDER + "?mode=replace&after=200")
        ref = ref_for(ctl, "Publish")
        wait_for_rerender(ctl)

        # The attribute is gone, so the ref has to be re-resolved by identity
        # or this raises.
        ctl.click(f'[data-orvima-ref="{ref}"]')

        clicked = ctl.page.evaluate("() => window.__clicks")
        assert clicked, "the click did not reach any button"
        assert all(c == "publish" for c in clicked), f"clicked the wrong element: {clicked}"

    def test_a_stale_ref_with_no_substitute_is_refused(self, ctl):
        """Deleting the target must produce an error, not a click on a neighbour."""
        ctl.navigate(RERENDER + "?mode=replace&after=200")
        ref = ref_for(ctl, "Delete everything")
        wait_for_rerender(ctl)

        # Rename it before removing it, so the registry's recorded identity
        # ("Delete everything") stops matching anything on the page. Removing it
        # alone is not enough: the registry searches the *last snapshot*, and the
        # snapshot still contains this very entry, so it would find itself as its
        # own substitute and hand back a selector for a node that no longer
        # exists. That is the bug the live-page check in _guard_ref catches, and
        # this test is what proves it does.
        ctl.page.evaluate(
            """() => {
                const el = document.getElementById('delete');
                el.removeAttribute('id');
                el.textContent = 'Archive instead';
                el.remove();
            }"""
        )
        time.sleep(0.1)

        with pytest.raises(BrowserError, match="stale"):
            ctl.click(f'[data-orvima-ref="{ref}"]')

        assert ctl.page.evaluate("() => window.__clicks") == [], (
            "a refused click must not have reached the page"
        )


class TestRefHijackIsRefused:
    """A different button steals the ref's slot. This must not be clicked."""

    def test_a_ref_pointing_at_a_different_element_is_not_clicked(self, ctl):
        ctl.navigate(RERENDER + "?mode=hijack&after=200")
        ref = ref_for(ctl, "Publish")
        wait_for_rerender(ctl)

        # The decoy reads "Delete everything" and now carries Publish's ref, so
        # the selector resolves to a destructive control that was never the one
        # the snapshot described.
        stolen = ctl.page.evaluate(
            """(ref) => {
                const el = document.querySelector('[data-orvima-ref="' + ref + '"]');
                return el ? el.id : null;
            }""",
            ref,
        )
        assert stolen == "publish-clone-decoy", f"the fixture did not hijack the ref (got {stolen})"

        with pytest.raises(BrowserError):
            ctl.click(f'[data-orvima-ref="{ref}"]')

        assert ctl.page.evaluate("() => window.__clicks") == [], (
            "a hijacked ref was clicked; this is the failure mode the whole "
            "identity layer exists to prevent"
        )

    def test_an_untouched_ref_still_works_after_a_rerender(self, ctl):
        """The guard must not break the ordinary case: a ref that is still valid."""
        ctl.navigate(RERENDER + "?mode=replace&after=200")
        save_ref = ref_for(ctl, "Save draft")
        wait_for_rerender(ctl)

        ctl.click(f'[data-orvima-ref="{save_ref}"]')
        assert ctl.page.evaluate("() => window.__clicks") == ["save"], (
            "a still-valid ref stopped working after an unrelated re-render"
        )


class TestPlainSelectorsAreUnaffected:
    """The 19-tool contract: selectors are the caller's business, not ours."""

    def test_a_plain_css_selector_is_passed_straight_through(self, ctl):
        ctl.navigate(RERENDER + "?mode=replace&after=200")
        wait_for_rerender(ctl)
        ctl.click("#publish")
        assert ctl.page.evaluate("() => window.__clicks") == ["publish"]
