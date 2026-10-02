"""`type` and `fill` under a covering header.

`click` was fixed first, and the obvious question afterwards is whether the other
actions had the same exposure. Measured, they did - differently:

  * `type` focuses by clicking, so it hit the identical 10s Playwright timeout
    that never mentioned the header. This is the ordinary case in practice: a
    sign-in form under a sticky bar.
  * `fill` *succeeded* on a covered field, reporting `verified: true` for a box
    the user cannot see. That is worse than failing - a credential goes into an
    invisible field and the next click lands somewhere else.

So both are covered here, and the fill case gets an assertion that is about
visibility rather than about the value landing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402

RECOVERABLE = """
<html><body style="margin:0">
  <div id="bar" style="position:sticky;top:0;left:0;right:0;height:140px;
       z-index:9999;background:#222;color:#fff;padding:20px">Sticky header</div>
  <div style="height:600px"></div>
  <input id="email" style="display:block;margin:0 0 20px 40px;width:260px;padding:12px">
  <div style="height:1000px"></div>
</body></html>
"""

NO_ROOM = """
<html><body style="margin:0;height:100vh;overflow:hidden">
  <div id="bar" style="position:sticky;top:0;left:0;right:0;height:180px;
       z-index:9999;background:#222;color:#fff;padding:20px">Tall sticky header</div>
  <input id="email" style="position:absolute;top:100px;left:40px;width:260px;padding:12px">
</body></html>
"""

# A field that is simply on the page: in view at scrollY 0, nothing over it.
# `scrollY` stays 0 across a fill and a type, so any movement is attributable to
# the occlusion probe rather than to Playwright bringing a below-the-fold
# element into view.
PLAIN_FIELD = """
<html><body style="margin:0;padding:40px">
  <input id="email" style="width:260px;padding:12px">
</body></html>
"""


@pytest.fixture(scope="module")
def ctl():
    with BrowserController(headless=True) as c:
        yield c


def _park_under_header(ctl):
    ctl.page.evaluate(
        """
        () => {
          const el = document.getElementById('email');
          window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 100);
        }
        """
    )
    ctl.wait(150)


def _is_covered(ctl):
    """Is the field under a header? A page with no header is never covered.

    Written defensively because two of the fixtures have no `#bar` at all, and
    `getBoundingClientRect` on null throws inside the page - which surfaces as an
    opaque Playwright error rather than as "there was no header here".
    """
    return ctl.page.evaluate(
        """
        () => {
          const el = document.getElementById('email');
          if (!el) return false;
          const bar = document.getElementById('bar');
          if (!bar) return false;
          return el.getBoundingClientRect().top < bar.getBoundingClientRect().bottom;
        }
        """
    )


def _is_visible(ctl):
    """Is the field clear of the header, from the page's own point of view?"""
    return ctl.page.evaluate(
        """
        () => {
          const el = document.getElementById('email');
          const r = el.getBoundingClientRect();
          const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return hit === el;
        }
        """
    )


class TestTypeUnderACoveringHeader:
    def test_a_scrollable_occlusion_types_successfully(self, ctl):
        ctl.page.set_content(RECOVERABLE)
        ctl.wait(150)
        _park_under_header(ctl)
        assert _is_covered(ctl) is True, "the fixture is not exercising an occluded field"

        started = time.monotonic()
        result = ctl.type("#email", "someone@example.invalid")
        elapsed = time.monotonic() - started

        assert result["verified"] is True
        assert elapsed < 5, f"took {elapsed:.1f}s; a recoverable occlusion is fast"

    def test_an_unfixable_occlusion_fails_fast_and_leaves_the_field_untouched(self, ctl):
        """The pre-fix behaviour was a 10s timeout naming no header.

        Two things matter: it must be prompt, and it must say the field is
        unchanged - a caller that retries blindly after a timeout has no way to
        know whether half the text landed.
        """
        ctl.page.set_content(NO_ROOM)
        ctl.wait(150)
        assert _is_covered(ctl) is True

        started = time.monotonic()
        with pytest.raises(BrowserError) as excinfo:
            ctl.type("#email", "someone@example.invalid")
        elapsed = time.monotonic() - started

        message = str(excinfo.value)
        assert "no scroll left" in message, message[:300]
        assert elapsed < 5, f"took {elapsed:.1f}s to report a measured obstruction"
        assert (
            ctl.page.eval_on_selector("#email", "el => el.value") == ""
        ), "text landed in a field the click could not reach"


class TestFillUnderACoveringHeader:
    def test_a_scrollable_occlusion_fills_and_becomes_visible(self, ctl):
        """`fill` worked before this change - but into a field nobody could see.

        The assertion is about visibility, not about the value landing, because
        the value landing was never the problem.
        """
        ctl.page.set_content(RECOVERABLE)
        ctl.wait(150)
        _park_under_header(ctl)
        assert _is_covered(ctl) is True
        assert _is_visible(ctl) is False, "the fixture should start with a hidden field"

        ctl.fill("#email", "someone@example.invalid")

        assert _is_covered(ctl) is False, (
            "the value went into a field that is still under the header, so the "
            "user watching the live viewport cannot see what was entered"
        )
        assert _is_visible(ctl) is True

    def test_an_unfixable_occlusion_refuses_rather_than_filling_invisibly(self, ctl):
        """The case that made `fill` more dangerous than `type`.

        Before this change, `fill` on a covered field returned `verified: true` -
        a truthful statement about the value and a misleading one about the
        action, because nothing appeared anywhere the user could see. Refusing is
        the honest outcome: the field is not reachable, and the caller should know
        that before a credential disappears into an invisible box.
        """
        ctl.page.set_content(NO_ROOM)
        ctl.wait(150)
        assert _is_covered(ctl) is True

        with pytest.raises(BrowserError) as excinfo:
            ctl.fill("#email", "someone@example.invalid")

        assert "no scroll left" in str(excinfo.value)
        assert (
            ctl.page.eval_on_selector("#email", "el => el.value") == ""
        ), "the value was written into an unreachable field"


class TestUnaffectedCases:
    def test_a_plain_field_still_types_and_fills(self, ctl):
        """The occlusion probe must be inert on an ordinary page.

        The field has to be *in view* for this to measure the probe. An earlier
        version reused the recoverable layout and scrolled to the top, which put
        the field below the fold - and Playwright then scrolled it into view
        itself, which is correct behaviour and has nothing to do with occlusion.
        The page moved, and the test blamed the wrong thing.
        """
        ctl.page.set_content(PLAIN_FIELD)
        ctl.wait(150)
        assert ctl.page.evaluate("() => window.scrollY") == 0
        assert _is_covered(ctl) is False, "nothing is covering this field"
        before = ctl.page.evaluate("() => window.scrollY")

        assert ctl.fill("#email", "a@example.invalid")["verified"] is True
        # `type` clicks to focus and then types, so it *appends* to whatever is
        # already in the field. Clear it first, or `verified` is False because the
        # value is the concatenation - correct behaviour, confusing failure.
        ctl.page.eval_on_selector("#email", "el => { el.value = ''; }")
        assert ctl.type("#email", "b@example.invalid")["verified"] is True
        assert ctl.page.evaluate("() => window.scrollY") == before, (
            "the page was scrolled for a field that was already in view and "
            "uncovered - the probe moved it for no reason"
        )

    def test_a_missing_field_still_raises(self, ctl):
        ctl.page.set_content(PLAIN_FIELD)
        ctl.wait(150)
        with pytest.raises(BrowserError):
            ctl.type("#nope", "x")
        with pytest.raises(BrowserError):
            ctl.fill("#nope", "x")
