"""Iframe and shadow-DOM traversal, against a real browser.

The gap these close: `document.querySelectorAll` does not cross a frame
boundary, so a form inside an iframe was invisible to the snapshot. An agent
would see an empty box and could not act on it.

Three properties are asserted, and the third matters as much as the first two:

1. a same-origin frame's controls appear in the outline and can be acted on
2. an open shadow root's controls appear and can be acted on
3. a frame the browser refuses to expose is reported in ``notTraversed`` by src
   and reason, not silently skipped

That third one is the honesty requirement. Silently dropping part of a page
would leave a planner believing it had seen everything, and it would then act
confidently on a page it has only partly read.

Run: pytest tests/test_nested.py -q
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
NESTED = (FIXTURES_DIR / "nested_page.html").resolve().as_uri()

from orvima.browser import BrowserController  # noqa: E402


@pytest.fixture(scope="module")
def ctl():
    """One browser for the module - each launch costs ~1.5 GB here."""
    controller = BrowserController(headless=True)
    controller.start()
    try:
        yield controller
    finally:
        controller.close()


def ref_for(snap: dict, label: str) -> str:
    for item in snap["items"]:
        if label.lower() in (item.get("label") or item.get("text") or "").lower():
            return item["ref"]
    raise AssertionError(f"no ref for {label!r}; saw {[i['label'] for i in snap['items']]}")


class TestShadowRoot:
    def test_controls_inside_an_open_shadow_root_are_outlined(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        labels = [i["label"] for i in snap["items"]]
        assert "Shadow email" in labels, "the shadow root's input was not outlined"
        assert "Shadow submit" in labels, "the shadow root's button was not outlined"
        assert "shadow host(s) traversed" in snap["shadowDom"], snap["shadowDom"]

    def test_a_shadow_control_is_flagged_as_such(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        shadow_items = [i for i in snap["items"] if i.get("inShadow")]
        assert shadow_items, "no item was marked as living in a shadow root"
        assert any(i["label"] == "Shadow submit" for i in shadow_items)

    def test_clicking_through_a_shadow_root_reaches_the_real_control(self, ctl):
        ctl.navigate(NESTED)
        ref = ref_for(ctl.snapshot(), "Shadow submit")
        ctl.click(f'[data-orvima-ref="{ref}"]')
        # The fixture's handler fills the field; proving it ran proves the click
        # went to the shadow control and not to something that merely looks like it.
        value = ctl.page.locator("#shadow-email").input_value()
        assert value == "shadow@example.com", f"the shadow control did not run (value={value!r})"


class TestSameOriginFrame:
    def test_controls_inside_a_same_origin_frame_are_outlined(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        refs = [i["ref"] for i in snap["items"]]
        assert any("Frame email" == i["label"] for i in snap["items"]), (
            f"the frame's input was not outlined; saw {[i['label'] for i in snap['items']]}"
        )
        # Refs are namespaced per frame, so two frames can both have an e1.
        frame_refs = [r for r in refs if r.startswith("f")]
        assert frame_refs, f"no frame-scoped refs; all refs were {refs}"

    def test_refs_are_unique_across_frames(self, ctl):
        ctl.navigate(NESTED)
        refs = [i["ref"] for i in ctl.snapshot()["items"]]
        assert len(refs) == len(set(refs)), f"duplicate refs: {refs}"

    def test_clicking_inside_a_frame_reaches_the_frames_own_control(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        ref = ref_for(snap, "Frame submit")
        # Pick the frame that is a direct child of the page, not the one nested
        # inside the shadow root, so this isolates frame traversal.
        ref = next(
            r["ref"]
            for r in snap["items"]
            if r["label"] == "Frame submit" and r.get("framePath") == ["same-origin"]
        )
        ctl.click(f'[data-orvima-ref="{ref}"]')
        assert ctl.page.frames[1].evaluate("() => window.__log") == ["frame-submit"], (
            "the click did not reach the frame's own control"
        )

    def test_a_frame_nested_inside_a_shadow_root_is_also_found(self, ctl):
        """Both traversals at once - the case a single-pass walker misses."""
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        nested = [i for i in snap["items"] if i.get("framePath") == ["nested-frame"]]
        assert nested, "the frame inside the shadow root was not outlined"
        assert any(i["label"] == "Frame submit" for i in nested)


class TestUnreachableFramesAreReported:
    def test_a_frame_the_browser_will_not_expose_is_named_not_dropped(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        not_traversed = snap.get("notTraversed")
        assert isinstance(not_traversed, list), "notTraversed must always be present"
        assert not_traversed, (
            "the cross-origin frame was neither traversed nor reported - it was "
            "silently dropped, which is the failure mode this test exists for"
        )
        entry = not_traversed[0]
        assert entry.get("src"), "the report must name the frame's src"
        assert entry.get("reason"), "the report must say why it could not be read"

    def test_the_summary_line_reflects_what_was_skipped(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        assert "not reachable" in snap["iframes"], (
            f"the iframe summary hides the gap: {snap['iframes']!r}"
        )
        assert "notTraversed" in snap["iframes"], snap["iframes"]


class TestContractUnchanged:
    def test_a_plain_selector_still_works_across_the_whole_page(self, ctl):
        """The 19-tool contract: callers passing selectors are unaffected."""
        ctl.navigate(NESTED)
        ctl.click("#shadow-submit")
        assert ctl.page.locator("#shadow-email").input_value() == "shadow@example.com"

    def test_snapshot_shape_keeps_its_existing_keys(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        for key in ("url", "title", "items", "body", "truncated", "iframes", "shadowDom"):
            assert key in snap, f"snapshot lost the {key!r} key"
