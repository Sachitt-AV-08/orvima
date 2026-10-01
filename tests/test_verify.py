"""Verification tests: `verified: False` must mean "no evidence", not "I couldn't tell".

Three real defects motivated these:

  1. `type`/`fill` on a contenteditable (or any non-<input>) target ALWAYS
     reported verified=False, because `input_value()` only works on
     input/textarea/select. Rich editors (LinkedIn, Notion, Slack, any ProseMirror
     or tiptap composer) are exactly where agents need this to work.
  2. The read error was swallowed into a bare `value = ""`, so a genuine read
     failure looked identical to "the field is empty".
  3. Click verification compared `document.querySelectorAll('*').length` before
     and after - a number that changes on any unrelated mutation, so it both
     "verified" no-op clicks and failed to verify real ones.

Runs against a local fixture with a real browser (no network, no login).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orvima.browser import BrowserController

FIXTURE = (Path(__file__).parent / "fixtures" / "editable_page.html").resolve().as_uri()


@pytest.fixture(scope="module")
def ctl():
    controller = BrowserController(headless=True)
    with controller:
        controller.navigate(FIXTURE)
        yield controller


class TestTypeVerification:
    def test_plain_input_verifies(self, ctl):
        result = ctl.type("#plain", "hello")
        assert result["verified"] is True, "normal input should verify"

    def test_contenteditable_verifies(self, ctl):
        """The big one: contenteditable targets must not report a false negative."""
        result = ctl.type("#rich", "typed into rich editor")
        assert result["verified"] is True, "contenteditable typing misreported as unverified"

    def test_contenteditable_text_is_actually_there(self, ctl):
        ctl.fill("#rich", "")  # shared module fixture - clear the previous test's text
        ctl.type("#rich", "confirmed in the DOM")
        assert ctl.page.eval_on_selector("#rich", "el => el.innerText") == "confirmed in the DOM"

    def test_cleared_value_reports_false(self, ctl):
        """A handler that wipes the field must report verified=False, honestly."""
        result = ctl.type("#cleared", "will be wiped")
        assert result["verified"] is False, "a cleared field is not a verified write"


class TestFillVerification:
    def test_plain_input_verifies(self, ctl):
        assert ctl.fill("#plain", "filled value")["verified"] is True

    def test_contenteditable_verifies(self, ctl):
        result = ctl.fill("#rich", "filled rich")
        assert result["verified"] is True, "contenteditable fill misreported as unverified"


class TestClickVerification:
    def test_click_with_dom_change_verifies(self, ctl):
        result = ctl.click("#touched")
        assert result["verified"] is True

    def test_click_on_static_element_does_not_claim_success(self, ctl):
        """Clicking something inert must not be reported as a verified change."""
        result = ctl.click("#plain")
        assert result["verified"] is False, "inert click should not verify"

    def test_no_op_click_is_not_verified(self, ctl):
        result = ctl.click("h1")
        assert result["verified"] is False


class TestReadErrorsAreVisible:
    def test_missing_selector_raises_actionable_error(self, ctl):
        from orvima.errors import BrowserError

        with pytest.raises(BrowserError) as exc:
            ctl.type("#does-not-exist", "hi")
        msg = str(exc.value).lower()
        assert "#does-not-exist" in msg, f"error should name the selector: {exc.value}"


class TestLifecycle:
    """A closed controller must say so, not leak Playwright internals.

    These need their own controller, which cannot coexist with the module-scoped
    one above (two Playwright sync loops in one thread is unsupported), so they
    live in their own file: test_lifecycle.py.
    """
