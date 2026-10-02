"""The click path, end to end, through the public API.

`uncover` is unit-tested and the geometry is tested in a real browser, but the
thing that matters to a caller is `click`. Three cases:

  * a header-covered element that can be scrolled clear - should work, fast
  * a header-covered element that cannot - should fail *fast*, naming the cause,
    and must not click anything
  * a normal element - must be entirely unaffected, including not scrolling

The middle case is the one that was previously a 10-second timeout mentioning
nothing. It is also the one where a wrong fix is dangerous: "recovered" by
clicking through the overlay would be worse than failing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402

STUCK_HEADER = """
<html><body style="margin:0">
  <div id="bar" style="position:sticky;top:0;left:0;right:0;height:140px;
       z-index:9999;background:#222;color:#fff;padding:20px">Sticky header</div>
  <div style="height:600px"></div>
  <button id="deep" style="display:block;margin:0 0 40px 40px;width:240px;padding:14px">
    Deep button
  </button>
  <div style="height:1000px"></div>
  <script>
    window.__clicks = [];
    for (const [id, name] of [['#bar','header'], ['#deep','target']]) {
      document.querySelector(id).addEventListener('click', () => window.__clicks.push(name));
    }
  </script>
</body></html>
"""

NO_ROOM = """
<html><body style="margin:0;height:100vh;overflow:hidden">
  <div id="bar" style="position:sticky;top:0;left:0;right:0;height:180px;
       z-index:9999;background:#222;color:#fff;padding:20px">Tall sticky header</div>
  <button id="buried" style="position:absolute;top:100px;left:40px;
          width:220px;padding:12px">Buried</button>
  <script>
    window.__clicks = [];
    document.getElementById('bar').addEventListener('click', () => window.__clicks.push('header'));
    document.getElementById('buried').addEventListener('click', () => window.__clicks.push('buried'));
  </script>
</body></html>
"""

PLAIN = """
<html><body style="margin:0;padding:40px">
  <button id="ok" style="width:200px;padding:14px">Plain button</button>
  <script>
    window.__clicks = [];
    document.getElementById('ok').addEventListener('click', () => window.__clicks.push('ok'));
  </script>
</body></html>
"""


@pytest.fixture(scope="module")
def ctl():
    with BrowserController(headless=True) as c:
        yield c


class TestClickRecoversFromAStickyHeader:
    def test_a_scrollable_occlusion_is_clicked_correctly(self, ctl):
        """The element is under the header and there is room to scroll.

        Before this change Playwright still managed this one by re-centring, so
        this test is partly a guard against a fix that makes things worse.
        """
        ctl.page.set_content(STUCK_HEADER)
        ctl.wait(150)
        ctl.page.evaluate(
            """
            () => {
              const el = document.getElementById('deep');
              window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 100);
            }
            """
        )
        ctl.wait(150)

        covered = ctl.page.evaluate(
            """
            () => {
              const el = document.getElementById('deep');
              const bar = document.getElementById('bar').getBoundingClientRect();
              return el.getBoundingClientRect().top < bar.bottom;
            }
            """
        )
        assert covered is True, "the fixture is not exercising an occluded element"

        started = time.monotonic()
        ctl.click("#deep")
        elapsed = time.monotonic() - started

        assert ctl.page.evaluate("() => window.__clicks") == ["target"], (
            "the wrong element was clicked - a recovery must not mean acting on "
            "whatever happens to be on top"
        )
        assert elapsed < 5, f"took {elapsed:.1f}s; recovery should be near-instant"

    def test_an_unfixable_occlusion_fails_fast_and_names_the_cause(self, ctl):
        """No scroll room, so the element is unreachable.

        Two properties, and the second matters more than the first: the failure
        must name the obstruction, and it must do so *promptly*. A 10s timeout
        that eventually mentions a header still reads as a hang.
        """
        ctl.page.set_content(NO_ROOM)
        ctl.wait(150)

        started = time.monotonic()
        with pytest.raises(BrowserError) as excinfo:
            ctl.click("#buried")
        elapsed = time.monotonic() - started

        message = str(excinfo.value)
        assert "no scroll left" in message, (
            f"the failure does not say what is in the way: {message[:300]}"
        )
        assert elapsed < 5, (
            f"took {elapsed:.1f}s to report a layout it had already measured. "
            "Playwright's timeout is 10s; waiting it out after uncovering "
            "reported the obstruction is pure delay."
        )
        assert ctl.page.evaluate("() => window.__clicks") == [], (
            "something was clicked on an unreachable element"
        )

    def test_a_plain_page_is_not_scrolled(self, ctl):
        """Nothing is covering anything, so the page must not move.

        The occlusion probe runs on every click. A page that was fine and gets
        scrolled anyway would move things under the cursor - so this guards the
        optimisation, not the feature.
        """
        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        before = ctl.page.evaluate("() => window.scrollY")

        ctl.click("#ok")

        after = ctl.page.evaluate("() => window.scrollY")
        assert after == before == 0, (
            f"the page scrolled from {before} to {after} for a click on a "
            "fully visible element"
        )
        assert ctl.page.evaluate("() => window.__clicks") == ["ok"]

    def test_a_missing_element_still_raises(self, ctl):
        """The occlusion probe must not swallow Playwright's own errors."""
        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        with pytest.raises(BrowserError):
            ctl.click("#no-such-thing")


class TestTheOptimisationCannotBreakAClick:
    """Uncovering is a courtesy, not a precondition.

    `click` now runs an occlusion probe before every click. If that probe itself
    throws - a page that navigated mid-call, a frame that went away, a selector
    Playwright's evaluate rejects - the click must still proceed. Playwright's own
    actionability check remains the backstop, and it is the authority on whether a
    click is possible.

    Getting this backwards is not a cosmetic bug: propagating the probe's error
    would turn a working click into a hard failure, on every page, whenever the
    probe tripped.
    """

    def test_a_click_still_works_when_the_probe_throws(self, ctl, monkeypatch):
        import orvima.browser as browser_mod

        def exploding(*a, **k):
            raise RuntimeError("probe failed")

        monkeypatch.setattr(browser_mod, "uncover", exploding)

        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        ctl.click("#ok")

        assert ctl.page.evaluate("() => window.__clicks") == ["ok"], (
            "a failure in the occlusion probe stopped a click that would have "
            "worked. The probe is an optimisation; Playwright's actionability "
            "check is the real gate."
        )

    def test_the_probe_failure_is_not_silently_swallowed_from_the_result(
        self, ctl, monkeypatch
    ):
        """It should be recorded, not just survived.

        A probe that fails on every click is a bug in its own right, and the only
        trace of it is the skip note on the result.
        """
        import orvima.browser as browser_mod

        calls: list = []

        def exploding(*a, **k):
            calls.append(1)
            raise RuntimeError("probe failed")

        monkeypatch.setattr(browser_mod, "uncover", exploding)

        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        outcome = ctl._uncover_if_occluded("#ok", ctl.page)

        assert calls, "the probe was not called"
        assert outcome.get("uncovered") is True, (
            "a failed probe must not be reported as an occlusion failure, or the "
            "caller would refuse a click on an unoccluded element"
        )
        assert outcome.get("skipped"), (
            "the probe failure was dropped entirely, so a permanently broken "
            "probe would be invisible"
        )
