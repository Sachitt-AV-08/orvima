"""Typing-latency tests.

`type()` used a hardcoded 24ms/character delay (human-pacing). For an agent
tool that is pure latency: a 1,500-character post cost ~50 seconds. Pacing
belongs in the product layer (parley), not in the browser driver.
"""

from __future__ import annotations

import pytest

from orvima.browser import BrowserController


class _StubKeyboard:
    def __init__(self):
        self.calls: list[tuple[str, int | None]] = []

    def type(self, text, delay=None):
        self.calls.append((text, delay))


class _StubPage:
    def __init__(self, value=""):
        self.keyboard = _StubKeyboard()
        self._value = value
        self.url = "about:blank"

    def click(self, selector, timeout=None):
        self.clicked = selector

    def input_value(self, selector):
        return self._value

    def title(self):
        return "stub"


def test_type_does_not_sleep_between_characters():
    """Default must be 0ms/char - an agent pays this latency on every message."""
    page = _StubPage(value="hi")
    bc = BrowserController()
    bc.page = page

    bc.type("input", "hi")

    assert page.keyboard.calls, "keyboard.type was never called"
    _, delay = page.keyboard.calls[0]
    assert delay == 0, f"typing still sleeps {delay}ms per character"


def test_type_delay_is_configurable_per_call():
    page = _StubPage(value="hi")
    bc = BrowserController()
    bc.page = page

    bc.type("input", "hi", delay_ms=24)

    _, delay = page.keyboard.calls[0]
    assert delay == 24


def test_type_delay_env_override(monkeypatch):
    monkeypatch.setenv("ORVIMA_TYPE_DELAY_MS", "15")
    page = _StubPage(value="hi")
    bc = BrowserController()
    bc.page = page

    bc.type("input", "hi")

    _, delay = page.keyboard.calls[0]
    assert delay == 15


def test_bulk_text_has_no_artificial_sleep():
    """A 1,500-char body must not add ~36s of scripted sleeping."""
    body = "x" * 1500
    page = _StubPage(value=body)
    bc = BrowserController()
    bc.page = page

    started = pytest.importorskip("time").monotonic()
    result = bc.type("body", body)
    elapsed = pytest.importorskip("time").monotonic() - started

    _, delay = page.keyboard.calls[0]
    assert delay == 0
    assert result["verified"] is True
    assert elapsed < 1.0, f"typing budget still too slow: {elapsed:.2f}s"
