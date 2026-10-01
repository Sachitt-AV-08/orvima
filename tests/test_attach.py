"""Attach-path tests: a CDP attach must fail fast and say why.

Regression guard for the 180-second stall: `connect_over_cdp` hangs when
another client is already attached to the same browser, and Playwright's
default 180s timeout turned that into a silent three-minute freeze followed
by a generic "could not start a browser".
"""

from __future__ import annotations

import time

import pytest

from orvima.browser import BrowserController
from orvima.errors import BrowserError

DEAD_ENDPOINT = "http://127.0.0.1:9"  # nothing listens here


class _FakeChromium:
    def __init__(self, calls):
        self._calls = calls

    def connect_over_cdp(self, url, **kwargs):
        self._calls.append({"url": url, **kwargs})
        raise TimeoutError("BrowserType.connect_over_cdp: Timeout 180000ms exceeded.")


class _FakePW:
    def __init__(self, calls):
        self.chromium = _FakeChromium(calls)

    def stop(self):
        pass


def test_attach_to_dead_endpoint_fails_fast_with_actionable_hint(monkeypatch):
    """No browser listening -> immediate, explicit error (not a raw Playwright dump)."""
    bc = BrowserController(attach=DEAD_ENDPOINT)
    t0 = time.monotonic()
    with pytest.raises(BrowserError) as exc:
        bc.start()
    elapsed = time.monotonic() - t0

    assert elapsed < 10, f"attach should fail fast, took {elapsed:.1f}s"
    msg = str(exc.value).lower()
    assert "no browser" in msg and "listening" in msg, f"unhelpful hint: {exc.value}"


def test_attach_timeout_is_bounded_not_playwright_default(monkeypatch):
    """The stalled-attach path must carry a short, explicit timeout."""
    calls: list[dict] = []

    class _FakeSync:
        def start(self):
            return _FakePW(calls)

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: _FakeSync())
    monkeypatch.setattr("orvima.browser._cdp_endpoint_alive", lambda url: True, raising=False)
    # Pin this to the browser-level path: no page-socket shortcut, so the
    # browser-level error and its timeout are what is under test here.
    monkeypatch.setattr("orvima.browser._page_socket_for", lambda url, hint: "", raising=False)

    bc = BrowserController(attach="http://127.0.0.1:9335")
    t0 = time.monotonic()
    with pytest.raises(BrowserError) as exc:
        bc.start()
    elapsed = time.monotonic() - t0

    assert calls, "connect_over_cdp was never called"
    timeout_ms = calls[0].get("timeout")
    assert timeout_ms is not None, "connect_over_cdp must receive an explicit timeout"
    assert timeout_ms <= 30_000, f"timeout too long: {timeout_ms}ms (was 180000 = the 3-min stall)"
    assert elapsed < 10, f"should not wait on the full timeout, took {elapsed:.1f}s"

    msg = str(exc.value).lower()
    # Must name the real mechanism, not a guess. Measured: connect_over_cdp stalls
    # indefinitely on a busy profile (recaptcha iframes / extension service
    # workers) even with no other client attached - see issue notes in browser.py.
    assert "handshake never completed" in msg, f"must describe the stall: {exc.value}"
    assert "every target" in msg, f"must name target enumeration: {exc.value}"
    assert "orvima launch its own browser" in msg, f"must offer a way out: {exc.value}"


def test_failed_start_does_not_leak_the_playwright_loop(monkeypatch):
    """A failed start must stop the driver.

    Otherwise the leaked asyncio loop makes the *next* sync_playwright() start in
    the same process fail with "you are using Playwright Sync API inside the
    asyncio loop", turning one error into a cascade of unrelated ones.
    """
    stopped = {"n": 0}

    class _FakePW:
        def stop(self):
            stopped["n"] += 1

    class _FakeSync:
        def start(self):
            return _FakePW()

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: _FakeSync())
    monkeypatch.setattr("orvima.browser._cdp_endpoint_alive", lambda url: False, raising=False)

    bc = BrowserController(attach="http://127.0.0.1:9335")
    with pytest.raises(BrowserError):
        bc.start()

    assert stopped["n"] == 1, "driver leaked after a failed start"
    assert bc._pw is None


def test_attach_timeout_env_override(monkeypatch):
    calls: list[dict] = []

    class _FakeSync:
        def start(self):
            return _FakePW(calls)

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: _FakeSync())
    monkeypatch.setattr("orvima.browser._cdp_endpoint_alive", lambda url: True, raising=False)
    monkeypatch.setenv("ORVIMA_ATTACH_TIMEOUT", "3")

    with pytest.raises(BrowserError):
        BrowserController(attach="http://127.0.0.1:9335").start()

    assert calls[0].get("timeout") == 3000
