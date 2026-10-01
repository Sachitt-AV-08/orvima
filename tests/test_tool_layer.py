"""The tool layer, exercised the way an agent actually calls it.

The traversal tests in test_nested.py drive ``browser.click`` directly. That is
not the path an agent takes: the planner hands a ref to ``browse_click``, which
validates it through ``_resolve`` first.

This file exists because that gap hid a real defect. ``_resolve`` accepted only
``^e\\d+$``, so the ``f1:e3`` refs the snapshot hands out for frame content were
rejected with "invalid ref" - the traversal worked perfectly at the browser layer
and was completely unreachable in production. Every traversal test passed while
the feature was unusable. A test that stops one layer short of the real entry
point is a test of the wrong thing.

Run: pytest tests/test_tool_layer.py -q
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
from orvima.tools import tool_browse_click, tool_browse_fill  # noqa: E402


@pytest.fixture(scope="module")
def ctl():
    controller = BrowserController(headless=True)
    controller.start()
    try:
        yield controller
    finally:
        controller.close()


def ref_for(snap: dict, label: str) -> str:
    for item in snap["items"]:
        if label.lower() == (item.get("label") or "").lower():
            return item["ref"]
    raise AssertionError(f"no ref for {label!r}; saw {[i['label'] for i in snap['items']]}")


class TestRefValidationAcceptsWhatSnapshotsHandOut:
    """A ref the snapshot produces must survive _resolve unchanged.

    This is the invariant that was broken: the snapshot emitted f1:e3 and
    _resolve threw on it.
    """

    def test_a_frame_ref_is_not_rejected(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        frame_refs = [i["ref"] for i in snap["items"] if ":" in i["ref"]]
        assert frame_refs, "the fixture produced no frame-scoped refs to check"

        result = tool_browse_click(ctl, ref=frame_refs[0])
        assert result.get("ok"), (
            f"the tool layer rejected a ref the snapshot itself produced: {result}"
        )

    def test_every_ref_in_a_snapshot_is_usable_by_the_tool_layer(self, ctl):
        """Broadest form of the same invariant: none of them are decorative."""
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        ctl.navigate(NESTED)  # re-snapshot so the refs below are live again
        snap = ctl.snapshot()
        for item in snap["items"]:
            tag = item["tag"]
            if tag in ("input", "textarea", "select"):
                result = tool_browse_fill(ctl, "x", ref=item["ref"])
            elif tag in ("a", "button"):
                result = tool_browse_click(ctl, ref=item["ref"])
            else:
                continue
            assert result.get("ok"), f"ref {item['ref']!r} ({tag}) was rejected: {result}"


class TestToolLayerRejectsWhatItShould:
    """Loosening the ref pattern must not loosen it into accepting junk."""

    def test_an_arbitrary_string_is_still_rejected(self, ctl):
        result = tool_browse_click(ctl, ref="not-a-ref")
        assert not result.get("ok"), f"accepted junk ref: {result}"

    def test_a_selector_injection_in_a_ref_is_still_rejected(self, ctl):
        result = tool_browse_click(ctl, ref='e1"], script')
        assert not result.get("ok"), f"accepted a malformed ref: {result}"

    def test_providing_both_ref_and_selector_is_still_rejected(self, ctl):
        result = tool_browse_click(ctl, ref="e1", selector="#publish")
        assert not result.get("ok")
        assert "not both" in result.get("error", ""), result


class TestFrameActionThroughTheToolLayer:
    def test_a_click_inside_a_frame_really_reaches_the_frames_control(self, ctl):
        """The whole point: reachable by an agent, not just by a unit test."""
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        ref = next(
            i["ref"]
            for i in snap["items"]
            if i["label"] == "Frame submit" and i.get("framePath") == ["same-origin"]
        )
        result = tool_browse_click(ctl, ref=ref)
        assert result.get("ok"), result
        assert ctl.page.frames[1].evaluate("() => window.__log") == ["frame-submit"], (
            "the tool-layer click did not reach the frame's own control"
        )

    def test_a_fill_inside_a_frame_writes_to_the_frames_field(self, ctl):
        ctl.navigate(NESTED)
        snap = ctl.snapshot()
        ref = next(
            i["ref"]
            for i in snap["items"]
            if i["label"] == "Frame email" and i.get("framePath") == ["same-origin"]
        )
        result = tool_browse_fill(ctl, "typed@example.com", ref=ref)
        assert result.get("ok"), result
        assert result.get("verified"), f"fill was not verified: {result}"
        assert (
            ctl.page.frames[1].locator("#frame-email").input_value()
            == "typed@example.com"
        ), "the value did not land in the frame's field"