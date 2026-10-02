"""hover, select and download under a covering header.

`click`, `type` and `fill` were fixed first. These three were then audited rather
than assumed, by grepping for every action that touches an element and checking
each one against a real page. The audit found all three exposed, in two
different ways:

  * `hover` and `download` *failed* after the full 10s Playwright timeout, with
    a call log naming no header. `download` is the worst of these: its message
    blames the link ("may be expired, or the site may be waiting on a
    permission prompt") when the cause is a header, and it burns 10s of click
    timeout plus 15s of download timeout before saying so.
  * `select` *succeeded* on a covered field, because `select_option` sets the
    value through the DOM. The same invisible-action problem `fill` had, and
    worse in one way: a form gets submitted with a value the user never chose.

So the assertions here are split by failure mode rather than by method, because
that is the distinction that decides what the caller is told.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima.browser import BrowserController  # noqa: E402
from orvima.errors import BrowserError  # noqa: E402

# A 300px sticky header over everything below it, and a document with no scroll
# room, so every element is permanently unreachable.
COVERED = """
<html><body style="margin:0;height:100vh;overflow:hidden">
  <div id="bar" style="position:sticky;top:0;left:0;right:0;height:300px;
       z-index:9999;background:#222;color:#fff;padding:20px">Very tall sticky header</div>
  <select id="pick" style="position:absolute;top:150px;left:40px;width:200px;padding:8px">
    <option value="a">Alpha</option>
    <option value="b">Beta</option>
  </select>
  <a id="dl" href="data:text/plain,hello" download="out.txt"
     style="position:absolute;top:210px;left:40px;display:inline-block;padding:8px">Download</a>
  <button id="hov" style="position:absolute;top:270px;left:40px;padding:8px">Hover me</button>
  <script>
    window.__log = [];
    for (const id of ['#pick', '#dl', '#hov']) {
      const el = document.querySelector(id);
      el.addEventListener('change', () => window.__log.push('change:' + id));
      el.addEventListener('mouseover', () => window.__log.push('over:' + id));
      el.addEventListener('click', () => window.__log.push('click:' + id));
    }
  </script>
</body></html>
"""

PLAIN = """
<html><body style="margin:0;padding:40px">
  <select id="pick" style="width:200px;padding:8px">
    <option value="a">Alpha</option>
    <option value="b">Beta</option>
  </select>
  <a id="dl" href="data:text/plain,hello" download="out.txt"
     style="display:inline-block;padding:8px;margin-left:20px">Download</a>
  <button id="hov" style="padding:8px">Hover me</button>
  <script>
    window.__log = [];
    for (const id of ['#pick', '#dl', '#hov']) {
      const el = document.querySelector(id);
      el.addEventListener('change', () => window.__log.push('change:' + id));
      el.addEventListener('mouseover', () => window.__log.push('over:' + id));
      el.addEventListener('click', () => window.__log.push('click:' + id));
    }
  </script>
</body></html>
"""


@pytest.fixture(scope="module")
def ctl():
    with BrowserController(headless=True) as c:
        yield c


def _under_header(ctl, selector: str) -> bool:
    return ctl.page.evaluate(
        """
        (sel) => {
          const el = document.querySelector(sel);
          const bar = document.getElementById('bar');
          if (!el || !bar) return false;
          return el.getBoundingClientRect().top < bar.getBoundingClientRect().bottom;
        }
        """,
        selector,
    )


class TestActionsOnUnreachableElements:
    """All three must refuse, promptly, and name the obstruction.

    The fast, named failure is the whole point. Each of these previously spent
    10 seconds - and `download` a further 15 - to report a cause that had nothing
    to do with what it named.
    """

    @pytest.mark.parametrize(
        ("label", "selector", "action"),
        [
            ("hover", "#hov", lambda c: c.hover("#hov")),
            ("select", "#pick", lambda c: c.select("#pick", "b")),
            ("download", "#dl", lambda c: c.download("#dl")),
        ],
    )
    def test_it_refuses_fast_and_names_the_header(self, ctl, label, selector, action):
        ctl.page.set_content(COVERED)
        ctl.wait(150)
        assert _under_header(ctl, selector) is True, (
            f"the fixture does not put {selector} under the header, so this test "
            "is not measuring what it claims"
        )

        started = time.monotonic()
        with pytest.raises(BrowserError) as excinfo:
            action(ctl)
        elapsed = time.monotonic() - started

        message = str(excinfo.value)
        assert "no scroll left" in message, (
            f"{label} did not name the obstruction: {message[:300]}"
        )
        assert elapsed < 5, (
            f"{label} took {elapsed:.1f}s to report a layout already measured. "
            "Playwright's click timeout alone is 10s, and download waits 15s more."
        )
        assert ctl.page.evaluate("() => window.__log") == [], (
            f"{label} acted on an element it had just reported as unreachable"
        )

    def test_select_does_not_change_an_invisible_dropdown(self, ctl):
        """The failure mode that is worse than an error.

        `select_option` works through the DOM, so before this change a covered
        `<select>` changed value and reported success. A form submitted afterwards
        carries a choice the user never made and cannot see.
        """
        """The failure mode that is worse than an error.

        `select_option` works through the DOM, so before this change a covered
        `<select>` changed value and reported success. A form submitted afterwards
        carries a choice the user never made and cannot see.
        """
        ctl.page.set_content(COVERED)
        ctl.wait(150)

        with pytest.raises(BrowserError):
            ctl.select("#pick", "b")

        assert ctl.page.eval_on_selector("#pick", "el => el.value") == "a", (
            "the dropdown was changed while hidden under the header"
        )


class TestTheRefusalNamesWhatItDidNotDo:
    """Each message must describe *its own* action.

    A single shared sentence covered every action. It was true of all of them -
    nothing had happened - and useless for all of them. The question a caller
    actually has after a refusal is "what state can I trust?", and for `type` and
    `fill` that means whether the field still holds its old value.
    """

    @pytest.mark.parametrize(
        ("action", "run", "must_say", "must_not_say"),
        [
            ("click", lambda c: c.click("#hov"), "clicked", "typed"),
            ("hover", lambda c: c.hover("#hov"), "hovered", "clicked"),
            ("select", lambda c: c.select("#pick", "b"), "selected", "filled"),
        ],
    )
    def test_the_message_matches_the_action(
        self, ctl, action, run, must_say, must_not_say
    ):
        ctl.page.set_content(COVERED)
        ctl.wait(150)

        with pytest.raises(BrowserError) as excinfo:
            run(ctl)
        message = str(excinfo.value)

        assert message.startswith(action), (
            f"the refusal does not name the action that failed: {message[:160]}"
        )
        assert must_say in message, (
            f"a {action} refusal does not say what {action} did not do: "
            f"{message[:200]}"
        )
        assert f"Nothing was {must_not_say}" not in message, (
            f"a {action} refusal describes a {must_not_say} instead: {message[:200]}"
        )

    def test_an_unknown_action_still_gets_a_truthful_message(self, ctl):
        """The fallback must not assert something it cannot know.

        An action added later should get a vague but accurate message, not one
        claiming it typed nothing - which is how the original shared sentence came
        to describe a click as a typing action.
        """
        with pytest.raises(BrowserError) as excinfo:
            ctl._refuse_if_unreachable(
                "#x",
                "an action nobody has written yet",
                {"uncovered": False, "reason": "covered by a bar"},
            )
        message = str(excinfo.value)
        assert "Nothing happened on the page" in message, message
        for verb in ("typed", "filled", "selected", "clicked", "hovered"):
            assert f"Nothing was {verb}" not in message, (
                f"the fallback asserts 'Nothing was {verb}' for an unknown "
                f"action: {message}"
            )


class TestActionsOnReachableElements:
    """The other half: a fix that only works in the broken case is a regression.

    Each of these runs on an ordinary page, and the page must not move.
    """

    def test_hover_select_and_download_still_work(self, ctl):
        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        assert ctl.page.evaluate("() => window.scrollY") == 0

        ctl.hover("#hov")
        ctl.select("#pick", "b")
        result = ctl.download("#dl")

        assert ctl.page.eval_on_selector("#pick", "el => el.value") == "b"
        assert "over:#hov" in ctl.page.evaluate("() => window.__log")
        assert result.get("savedTo"), result
        assert result.get("bytes") == 5, result
        assert ctl.page.evaluate("() => window.scrollY") == 0, (
            "the page was scrolled for elements that were already in view"
        )

    def test_a_missing_element_still_raises(self, ctl):
        ctl.page.set_content(PLAIN)
        ctl.wait(150)
        for action in (lambda: ctl.hover("#nope"), lambda: ctl.select("#nope", "a")):
            with pytest.raises(BrowserError):
                action()
