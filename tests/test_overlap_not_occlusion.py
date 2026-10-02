"""Regression: an outlined form field is not an occluded one.

Found by pointing the new occlusion probe at Google's sign-in page. orvima
refused to fill the email field, reporting "covered by an in-flow element".
Google does not stop people signing in, so the probe was wrong - and a probe
that refuses real sign-in forms is worse than no probe.

The shape, reproduced here in miniature, is Google's outlined text field:

    <div class="wrapper">      <- absolutely positioned, inset -2px
      <input id="identifierId">  <- position: relative, z-index 1
    </div>

The wrapper's border box *overlaps* the input geometrically and sits above it in
document order, so the naive reading is "something covers this field". But the
input carries `z-index: 1`, so it paints above the wrapper, and
`elementsFromPoint` puts the input at index 0 with the wrapper at index 1. The
wrapper is underneath and intercepts nothing.

Two bugs made this fail, and both are worth pinning separately:

  * The walk continued *past* the target and scanned the whole stack, so
    anything overlapping in any direction counted.
  * The guard meant to discard elements painted below the target was
    `Number(style.zIndex) <= elZ`. `z-index: auto` parses to `NaN`, and every
    comparison against `NaN` is false, so the guard never fired for the
    `z-index: auto` that most elements carry. It was inert.

The third case here, `pointer-events: none`, is the mirror image: a genuinely
large overlay that receives no pointer and therefore blocks nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402
from orvima.occlusion import uncover  # noqa: E402

# The Google outlined-field shape: an absolutely positioned wrapper whose border
# box is 2px larger than the input on every side, and an input lifted above it.
OUTLINED_FIELD = """
<html><body style="margin:0;padding:120px">
  <div style="position:absolute;left:118px;top:118px;width:380px;height:56px;
              background:rgba(0,0,0,0);border:1px solid #747775;z-index:auto">
    <input id="identifierId" name="identifier" type="text"
           style="position:relative;z-index:1;width:376px;height:52px;border:0;padding:8px">
  </div>
</body></html>
"""

# A real overlay that deliberately lets pointers through. Full width, 200px tall,
# painted above everything - and invisible to input.
POINTER_TRANSPARENT = """
<html><body style="margin:0;padding:120px">
  <div id="decor" style="position:fixed;top:0;left:0;right:0;height:400px;
       background:rgba(0,0,0,0.02);z-index:99999;pointer-events:none"></div>
  <input id="f" style="width:260px;padding:12px">
</body></html>
"""

# A genuine scrim: same geometry as above, but it takes the pointer.
POINTER_GRabbing = """
<html><body style="margin:0;padding:120px">
  <div id="scrim" style="position:fixed;top:0;left:0;right:0;height:400px;
       background:rgba(0,0,0,0.6);z-index:99999"></div>
  <input id="f" style="width:260px;padding:12px">
</body></html>
"""


@pytest.fixture(scope="module")
def ctl():
    with BrowserController(headless=True) as c:
        yield c


class TestOverlappingIsNotOccluding:
    """The distinction that broke Google: overlaps vs. intercepts."""

    def test_an_outlined_field_is_reachable(self, ctl):
        """The regression itself. Google refused to let orvima type here."""
        ctl.page.set_content(OUTLINED_FIELD)
        ctl.wait(200)

        # Confirm the geometry is what this test claims, so it cannot pass for
        # the wrong reason later.
        geometry = ctl.page.evaluate(
            """
            () => {
              const el = document.getElementById('identifierId');
              const r = el.getBoundingClientRect();
              const stack = (document.elementsFromPoint(
                r.x + r.width / 2, r.y + r.height / 2) || []);
              const wrapper = el.parentElement;
              return {
                topmostIsInput: stack[0] === el,
                inputStackIndex: stack.indexOf(el),
                wrapperStackIndex: stack.indexOf(wrapper),
                wrapperOverlaps: wrapper.getBoundingClientRect().top < r.top,
                wrapperZ: getComputedStyle(wrapper).zIndex,
                inputZ: getComputedStyle(el).zIndex,
              };
            }
            """
        )
        assert geometry["topmostIsInput"] is True, (
            f"the input is not topmost, so this fixture no longer reproduces the "
            f"bug: {geometry}"
        )
        assert geometry["wrapperOverlaps"] is True, (
            f"the wrapper does not overlap the input: {geometry}"
        )
        assert geometry["inputStackIndex"] < geometry["wrapperStackIndex"], geometry
        assert geometry["wrapperZ"] == "auto", (
            f"the wrapper needs z-index: auto for the NaN bug to bite: {geometry}"
        )

        result = uncover(ctl.page, "#identifierId")
        assert result["uncovered"] is True, (
            f"an outlined field was reported as occluded: {result}. This is the "
            "false refusal that blocked a real Google sign-in."
        )
        assert result.get("scrolled", 0) == 0, (
            "nothing is covering the field, so the page should not have moved"
        )

    def test_the_field_can_actually_be_filled(self, ctl):
        """Not occluded in the report, and not occluded in fact.

        The first assertion is about what orvima claims; this one is about what
        the page does. A probe that reports clear while the click still fails
        would be its own kind of lie.
        """
        ctl.page.set_content(OUTLINED_FIELD)
        ctl.wait(200)

        outcome = ctl.fill("#identifierId", "someone@example.invalid")

        assert outcome["verified"] is True
        assert (
            ctl.page.eval_on_selector("#identifierId", "el => el.value")
            == "someone@example.invalid"
        )

    def test_a_pointer_transparent_overlay_does_not_block(self, ctl):
        """Full width, painted above everything, and intercepts nothing.

        `pointer-events: none` makes an element transparent to input however
        large it is. Treating it as an obstacle would refuse actions on any page
        using that common technique for decorative layers and scroll-capture
        wrappers.
        """
        ctl.page.set_content(POINTER_TRANSPARENT)
        ctl.wait(200)

        above = ctl.page.evaluate(
            """
            () => {
              const el = document.getElementById('f');
              const decor = document.getElementById('decor');
              const r = el.getBoundingClientRect();
              const dr = decor.getBoundingClientRect();
              const stack = (document.elementsFromPoint(
                r.x + r.width / 2, r.y + r.height / 2) || []);
              return {
                decorCoversField: dr.top <= r.top && dr.bottom >= r.bottom
                  && dr.left <= r.left && dr.right >= r.right,
                decorZ: getComputedStyle(decor).zIndex,
                decorPointerEvents: getComputedStyle(decor).pointerEvents,
                decorInStack: stack.includes(decor),
                topmostIsField: stack[0] === el,
              };
            }
            """
        )
        assert above["decorCoversField"] is True, (
            f"the decorative overlay does not actually cover the field, so this "
            f"test is not measuring what it claims: {above}"
        )
        assert above["decorZ"] == "99999", (
            f"the overlay must be painted above the field for this to be the "
            f"hard case: {above}"
        )
        assert above["decorPointerEvents"] == "none", above
        # Chrome drops pointer-events:none elements from elementsFromPoint
        # altogether, so the walk never sees this one. The filter in the probe is
        # still needed - `elementsFromPoint` does return them in other engines
        # and for elements that only *inherit* the property - but recording it
        # here would pin an implementation detail of this browser, not a
        # property of the probe. What matters is asserted below: the overlay is
        # above everything and the field is still reachable.
        assert above["topmostIsField"] is True, above

        result = uncover(ctl.page, "#f")
        assert result["uncovered"] is True, (
            f"a pointer-events:none overlay was treated as an obstacle: {result}"
        )
        assert ctl.fill("#f", "visible@example.invalid")["verified"] is True

    def test_a_real_scrim_still_blocks(self, ctl):
        """The control. Without this, the two tests above prove nothing.

        Identical geometry to the transparent overlay; the only difference is
        `pointer-events`. If this ever stops blocking, the fix has been to
        ignore every overlay.
        """
        ctl.page.set_content(POINTER_GRabbing)
        ctl.wait(200)

        result = uncover(ctl.page, "#f")

        assert result["uncovered"] is False, (
            f"a real scrim was reported as clear: {result}. The fix for the Google "
            "false positive must not have become 'ignore all overlays'."
        )
        assert "scrim" in result.get("blockers", []), result
        with pytest.raises(BrowserError):
            ctl.fill("#f", "blocked@example.invalid")
        assert (
            ctl.page.eval_on_selector("#f", "el => el.value") == ""
        ), "the value was written into a field behind a scrim"
