"""Controller lifecycle: using a closed controller must be an obvious error.

Playwright's own message here is "Event loop is closed! Is Playwright already
stopped?" - which reads like an internal bug. These tests pin the clearer
message. Lives in its own file because each test needs its own controller, and
two Playwright sync loops cannot coexist in one thread.
"""

from __future__ import annotations

from pathlib import Path

from orvima.browser import BrowserController
from orvima.errors import BrowserError

FIXTURE = (Path(__file__).parent / "fixtures" / "editable_page.html").resolve().as_uri()


def test_actions_after_close_raise_a_clear_error():
    controller = BrowserController(base_url=FIXTURE, headless=True)
    controller.start()
    controller.close()

    try:
        controller.click("#touched")
    except BrowserError as exc:
        msg = str(exc).lower()
        assert "closed" in msg, f"should say the controller is closed: {exc}"
        assert "event loop" not in msg, "must not leak Playwright's internal wording"
    else:
        raise AssertionError("expected BrowserError when using a closed controller")


def test_type_after_close_raises_clearly():
    controller = BrowserController(base_url=FIXTURE, headless=True)
    controller.start()
    controller.close()

    try:
        controller.type("#rich", "hi")
    except BrowserError as exc:
        assert "closed" in str(exc).lower()
    else:
        raise AssertionError("expected BrowserError when typing on a closed controller")


def test_close_is_idempotent():
    controller = BrowserController(base_url=FIXTURE, headless=True)
    controller.start()
    controller.close()
    controller.close()  # must not raise


def test_context_manager_closes_cleanly():
    controller = BrowserController(base_url=FIXTURE, headless=True)
    with controller:
        assert controller.page is not None
    assert controller._closed is True
