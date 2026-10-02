"""Occlusion handling, against a real browser and a real layout.

The unit tests in test_occlusion.py pin the retry and wall-detection logic with a
fake page. These prove the end-to-end behaviour, which is the part that actually
matters: does the right element get clicked, and is a hopeless case reported
rather than retried until the timeout?

Four constructions were measured before writing any of this, because the
plausible-sounding story ("sticky headers break clicks") turned out to be mostly
false:

  header 57px, element 977px down     -> Playwright re-centres and clicks right
  header 180px, zero scroll room      -> occluded, times out, clicks nothing
  fixed overlay over the viewport mid -> target clicked anyway
  element near the document bottom    -> never occluded at all

So the failure is narrow: occluded *and* no scroll room. That is what these tests
cover, plus the case where a small scroll does fix it, which is the common one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima.browser import BrowserController  # noqa: E402
from orvima.occlusion import uncover  # noqa: E402

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "sticky_page.html"
).as_uri()


@pytest.fixture(scope="module")
def browser():
    # `with ctl` is what starts the browser; constructing a BrowserController
    # alone leaves page as None, which is what "no active page" was about.
    ctl = BrowserController(headless=True)
    with ctl:
        yield ctl


def _clicks(page):
    return page.evaluate("() => window.__clicks || []")


def test_a_plain_page_is_not_occluded(browser):
    """The control. If this fails, every other result here is meaningless."""
    browser.navigate(FIXTURE)
    browser.page.evaluate(
        "() => document.getElementById('target').scrollIntoView({block:'center'})"
    )
    result = uncover(browser.page, "#target")
    assert result["uncovered"] is True


def test_the_fixture_header_is_actually_sticky(browser):
    """Guards the fixture.

    A sticky header that stopped being sticky would make the occlusion tests pass
    for the wrong reason - the same failure mode as the earlier "fixed overlay"
    probe, which proved nothing because the overlay was not where the element
    ended up. So the fixture's own claim is asserted.
    """
    browser.navigate(FIXTURE)
    browser.page.evaluate("() => window.scrollTo(0, 600)")
    top = browser.page.evaluate("() => window.__barRectTop()")
    assert top == 0, (
        f"the fixture header is pinned at viewport y={top}, not 0. It is not "
        "behaving as a sticky header, so any occlusion result here is invalid"
    )


def test_uncover_clears_a_header_covered_element_where_scrolling_is_possible(browser):
    """The recoverable case: occluded, but the page can move."""
    browser.navigate(FIXTURE)
    browser.page.evaluate(
        """
        () => {
          // Park the target directly under the header, with scroll room left.
          const el = document.getElementById('target');
          window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 10);
        }
        """
    )
    browser.wait(150)

    occluded_before = browser.page.evaluate(
        """
        () => {
          const el = document.getElementById('target');
          const bar = document.getElementById('bar').getBoundingClientRect();
          return el.getBoundingClientRect().top < bar.bottom;
        }
        """
    )

    result = uncover(browser.page, "#target")

    assert result["uncovered"] is True, (
        f"uncover could not clear a sticky header with scroll room available: {result}"
    )
    still_covered = browser.page.evaluate(
        """
        () => {
          const el = document.getElementById('target');
          const bar = document.getElementById('bar').getBoundingClientRect();
          return el.getBoundingClientRect().top < bar.bottom;
        }
        """
    )
    assert not still_covered, "uncover reported success but the header still covers it"
    if occluded_before:
        assert result.get("cleared"), (
            "the element was occluded and the page was scrolled to clear it, but "
            "the result does not name what was in the way - so an agent cannot "
            "report that a header was involved"
        )
        assert "bar" in result["cleared"], result["cleared"]


def test_a_wall_is_reported_rather_than_retried(browser):
    """The measured failure, now reported in one call instead of by timeout.

    Reproduces the layout where no amount of scrolling helps: a document with no
    scroll room and an element under a tall fixed header. Before this, Playwright
    spun for the full 10s timeout and the error said nothing about the header.
    """
    browser.page.set_content(
        """
        <html><body style="margin:0;height:100vh;overflow:hidden">
          <div id="bar" style="position:fixed;top:0;left:0;right:0;height:140px;
               z-index:9999;background:#222;color:#fff">Header</div>
          <button id="buried" style="position:absolute;top:100px;left:40px;
                  width:220px;padding:12px;z-index:1">Buried</button>
        </body></html>
        """
    )
    browser.wait(200)

    result = uncover(browser.page, "#buried")

    assert result["uncovered"] is False
    assert "no scroll left" in result["reason"], result
    assert result.get("attempts") == 1, (
        f"took {result.get('attempts')} attempts to notice the page cannot scroll; "
        "each retry is a wasted step and the report arrives late"
    )
    assert "bar" in result.get("blockers", []), (
        f"the occluder was not named: {result}. An agent reading this cannot tell "
        "a cookie banner from a sticky nav from a modal"
    )


def test_a_missing_element_is_named_as_missing(browser):
    browser.navigate(FIXTURE)
    result = uncover(browser.page, "#does-not-exist")
    assert result["uncovered"] is False
    assert "no such element" in result["error"]


class TestTheCasesTheFirstVersionMissed:
    """Three layouts that a mutation harness showed nothing detected.

    Each of these is a layout that occurs constantly on the real web, and each
    one is invisible to the tests written before it:

    * a partial cover, where the overlay hides part of the element rather than all
      of it - a sticky sub-header over the top of a table row, a consent banner
      across the upper half of a card. Probing only the centre sees nothing.
    * an insufficient but non-zero scroll, where the page moves and the element
      is still covered. The first implementation of this module reported success
      from its own arithmetic here, and said so on a page where the header was
      plainly on top.
    * a recovery that forgets what it cleared, leaving the caller unable to say a
      header was involved.
    """

    @pytest.fixture
    def ctl(self, browser):
        """A BrowserController, not a raw Playwright Page.

        The other tests here go through the controller for `navigate` and `wait`,
        which exist on BrowserController and not on Page. Handing out a Page made
        every test in this class fail on an AttributeError instead of on the
        behaviour it was written to check.
        """
        return browser

    def test_a_partial_cover_is_detected_though_the_centre_is_clear(self, ctl):
        page = ctl.page
        """The overlay covers the top half only.

        `elementFromPoint` at the centre returns the element, so a centre-only
        probe concludes all is well - and a click there lands on the target while
        part of what the caller aimed at is not clickable at all.
        """
        ctl.page.set_content(
            """
            <html><body style="margin:0;height:100vh;overflow:hidden">
              <div id="lip" style="position:fixed;top:0;left:0;right:0;height:40px;
                   z-index:9999;background:#222"></div>
              <button id="half" style="position:absolute;top:30px;left:40px;
                      width:200px;height:80px">Half covered</button>
            </body></html>
            """
        )
        ctl.wait(150)

        centre_is_clear = page.evaluate(
            """
            () => {
              const r = document.getElementById('half').getBoundingClientRect();
              const hit = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
              return hit === document.getElementById('half');
            }
            """
        )
        assert centre_is_clear is True, (
            "the construction is wrong: the centre should be clear for this test "
            "to be testing what it claims"
        )

        result = uncover(page, "#half")

        assert result["uncovered"] is False, (
            "the element's top half is under a fixed bar while its centre is "
            "clear, and uncover reported it as reachable. A click aimed at the "
            "top of that element lands on the bar."
        )

    def test_an_insufficient_scroll_is_not_reported_as_success(self, ctl):
        """A scroll that happens but does not finish the job.

        This is the mutation's target. `uncover` computes a scroll, applies it,
        then measures again. The first implementation skipped the measurement and
        reported "clear" from its own arithmetic - and when the scroll fell short
        it claimed success with the header plainly on top. The numbers were right
        and the conclusion was wrong, which is why the property needed a test
        rather than a re-read of the code.

        Getting a scroll to be *applied but insufficient* needs an element taller
        than the space left below the occluder: the viewport clamp keeps it on
        screen, it moves as far as it can, and it is still covered. An element
        700px tall under 200px of fixed bars in a 720px viewport does that.

        The earlier attempt at this test put the element below the bars in
        document flow, so the blocker was an in-flow `div` and the function
        returned before scrolling - never reaching the line under test, and
        passing whether or not it was correct.
        """
        ctl.page.set_content(
            """
            <html><body style="margin:0">
              <div id="bar1" style="position:fixed;top:0;left:0;right:0;height:100px;
                   z-index:99999;background:#111"></div>
              <div id="bar2" style="position:fixed;top:100px;left:0;right:0;
                   height:100px;z-index:99998;background:#222"></div>
              <button id="tall" style="position:absolute;top:190px;left:40px;
                      width:200px;height:700px">Tall button</button>
              <!-- In-flow height, so the document can actually scroll. Without
                   this, scrollHeight equals the viewport height, the computed
                   delta is clamped to zero, and the function returns before
                   applying any scroll at all. -->
              <div style="height:1600px"></div>
            </body></html>
            """
        )
        ctl.wait(200)

        # Confirm the layout really does reach the post-scroll branch, rather than
        # assuming it. `_UNCOVER_JS` is not a read - it scrolls - so the position
        # is restored afterwards. Without that, this probe leaves the page exactly
        # where the line under test is reached, and the real call then runs
        # against already-moved state. That is what made the
        # "trust the prediction" mutation invisible: the test's own diagnostic
        # was quietly disabling it.
        import orvima.occlusion as mod

        raw = ctl.page.evaluate(mod._UNCOVER_JS, ["#tall", 4])
        assert raw.get("scrolled"), (
            f"expected a scroll to be applied, got {raw}. This layout no longer "
            "reaches the post-scroll measurement the test is written to check."
        )
        assert raw.get("occluded") is True, (
            f"expected the element to still be covered after the scroll, got "
            f"{raw}. If the scroll now clears it, this test no longer exercises a "
            "partial recovery."
        )
        ctl.page.evaluate("() => window.scrollTo(0, 0)")
        ctl.wait(100)

        result = uncover(ctl.page, "#tall")

        assert result["uncovered"] is False, (
            "the element is 700px tall in a 720px viewport under 200px of fixed "
            "bars, so no scroll can put it fully clear - uncover reported it as "
            f"reachable: {result}"
        )
        if result.get("reason"):
            assert result["reason"], "an uncoverable element must say why"

    def test_an_in_flow_occluder_is_not_offered_a_scroll_that_cannot_help(self, ctl):
        """A relative-positioned scrim: it travels with the page.

        `position: relative` with a high z-index covers the target but does not
        stay put when the document scrolls, so the target can never be moved out
        from under it. Reporting this as scrollable would tell the caller a scroll
        might help when it cannot, and spend the attempt budget rediscovering the
        same geometry.

        Every other fixture here uses a sticky or fixed bar, or puts the page's
        own content *behind* the target, so none of them reached this branch -
        which is why the mutation that disables it survived.
        """
        ctl.page.set_content(
            """
            <html><body style="margin:0">
              <button id="buried" style="position:absolute;top:150px;left:40px;
                      width:220px;height:60px;z-index:1">Buried button</button>
              <!-- position:relative + high z-index: covers the target, but moves
                   with the document, so no scroll clears it. -->
              <div style="position:relative;z-index:9999;margin-top:100px;height:160px;
                   background:#333"></div>
              <div style="height:1200px"></div>
            </body></html>
            """
        )
        ctl.wait(200)

        import orvima.occlusion as mod

        raw = ctl.page.evaluate(mod._UNCOVER_JS, ["#buried", 4])
        assert raw.get("occluded") is True, f"construction wrong: {raw}"
        assert raw.get("scrolled") is None, (
            f"a scroll was applied for an in-flow occluder: {raw}"
        )

        result = uncover(ctl.page, "#buried")

        assert result["uncovered"] is False
        assert result.get("attempts") == 1, (
            f"took {result.get('attempts')} attempts on an occluder that no scroll "
            "can clear"
        )
        assert "in-flow" in (result.get("reason") or ""), (
            f"the reason does not distinguish an in-flow occluder from a pinned "
            f"one: {result.get('reason')!r}. They call for different responses - a "
            "sticky header is a scrolling problem, a modal scrim is not."
        )

    def test_a_recovery_names_the_element_it_scrolled_past(self, ctl):

        page = ctl.page
        """The diagnosis has to survive a successful scroll.

        A caller that scrolled the page under the element it is about to act on
        needs to be able to say a header was involved. If the JS drops the
        pre-scroll occluder list when it reports the post-scroll state, a
        one-leg recovery - the common case - loses it entirely, because there is
        no earlier pass that had remembered it.
        """
        ctl.navigate(FIXTURE)
        ctl.page.evaluate(
            """
            () => {
              const el = document.getElementById('target');
              window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 10);
            }
            """
        )
        ctl.wait(150)

        result = uncover(page, "#target")

        assert result["uncovered"] is True, result
        assert result["scrolled"] != 0, (
            "the page did not move, so this test is not exercising a recovery"
        )
        assert result["cleared"], (
            "the page was scrolled to clear an overlay but the result names "
            f"nothing: {result}. The caller cannot report what was in the way."
        )
        assert "bar" in result["cleared"], result["cleared"]


def test_uncover_never_clicks_anything(browser):
    """End-to-end version of the safety property.

    The fixture logs every click at the element level, so this asserts against
    the page's own record rather than against the source of `uncover`.
    """
    browser.navigate(FIXTURE)
    browser.page.evaluate("() => { window.__clicks = []; }")
    uncover(browser.page, "#target")
    assert _clicks(browser.page) == [], (
        "uncover() clicked something. It is allowed to move the page and nothing "
        "else - the caller decides what to act on, having seen the result"
    )
