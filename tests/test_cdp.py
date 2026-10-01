"""Tests for the page-level CDP client.

The module exists because Playwright cannot attach to a busy real browser
(browser-level connect_over_cdp enumerates every target and stalls), so the
behaviours that matter are: it reaches a page the hard way, it reports what it
actually observed, and it refuses to invent success.

These run against a real Chromium launched with a debugging port - a clean
profile, so the client is exercised without the busy-profile stall.
"""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest

from orvima.cdp import CDPError, CDPPage, PageSocket, find_page_socket, list_page_targets

PORT = 9455
PAGE = (Path(__file__).parent / "fixtures" / "cdp_page.html").resolve().as_uri()


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="module")
def browser():
    """A real Chromium with a debugging port, torn down afterwards."""
    from playwright.sync_api import sync_playwright

    profile = Path(__file__).parent / ".cdp-test-profile"
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        str(profile),
        headless=True,
        args=[f"--remote-debugging-port={PORT}", "--no-first-run"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(PAGE, wait_until="domcontentloaded")
    for _ in range(40):
        if not _free(PORT):
            break
        time.sleep(0.25)
    else:
        pw.stop()
        pytest.skip("chromium never opened its debugging port")
    yield f"http://127.0.0.1:{PORT}"
    ctx.close()
    pw.stop()


@pytest.fixture()
def page(browser):
    with CDPPage(browser) as p:
        p.goto(PAGE)
        yield p


# ---------------------------------------------------------------- discovery --
def test_lists_page_targets(browser):
    targets = list_page_targets(browser)
    assert targets, "no page targets found"
    assert all(t["webSocketDebuggerUrl"].startswith("ws://") for t in targets)


def test_find_page_socket_matches_url_substring(browser):
    ws = find_page_socket(browser, "cdp_page.html")
    assert ws.startswith("ws://127.0.0.1")


def test_find_page_socket_without_hint_returns_a_page(browser):
    assert find_page_socket(browser, "").startswith("ws://")


def test_unknown_tab_hint_is_actionable(browser):
    with pytest.raises(CDPError, match="no open tab matches"):
        find_page_socket(browser, "definitely-not-a-real-tab-xyz")


def test_dead_endpoint_is_reported(browser):
    with pytest.raises(CDPError, match="could not list targets"):
        find_page_socket("http://127.0.0.1:9", "")


def test_non_loopback_socket_is_refused():
    with pytest.raises(CDPError, match="non-loopback"):
        PageSocket("ws://evil.example.com:9222/devtools/page/x")


# -------------------------------------------------------------------- reads --
def test_eval_returns_real_values(page):
    assert page.eval("1 + 1") == 2
    assert page.eval("document.title") == "CDP Fixture"


def test_eval_raises_on_js_exception(page):
    with pytest.raises(CDPError, match="JS threw"):
        page.eval("throw new Error('boom')")


def test_url_and_title_reflect_the_page(page):
    assert page.url().startswith("file://")
    assert page.title() == "CDP Fixture"


# ------------------------------------------------------------------- waits --
def test_wait_for_finds_present_element(page):
    assert page.wait_for("#target", timeout_s=5) is True


def test_wait_for_times_out_on_absent_element(page):
    assert page.wait_for("#not-here", timeout_s=1) is False


def test_wait_for_requires_visibility_by_default(page):
    assert page.wait_for("#hidden-box", timeout_s=1) is False


# ----------------------------------------------------------------- actions --
def test_click_reports_missing_element(page):
    assert page.click("#nope") is False


def test_click_fires_handler(page):
    page.click("#btn")
    time.sleep(0.3)
    assert page.eval("document.querySelector('#out').innerText") == "clicked"


def test_focus_and_insert_text_land_in_contenteditable(page):
    assert page.focus("#editor") is True
    page.insert_text("typed by orvima")
    assert page.eval("document.querySelector('#editor').innerText") == "typed by orvima"


def test_insert_text_handles_a_long_body_in_one_call(page):
    long_text = "x" * 5000
    page.focus("#editor")
    page.insert_text(long_text)
    assert page.eval("document.querySelector('#editor').innerText.length") == 5000


def test_set_file_input_attaches_a_file(page):
    png = Path(__file__).parent / "fixtures" / "pixel.png"
    page.set_file_input("#file", [str(png)])
    assert page.eval("document.querySelector('#file').files[0].name") == "pixel.png"


def test_set_file_input_missing_selector_raises(page):
    with pytest.raises(CDPError, match="no file input matched"):
        page.set_file_input("#no-input", ["x.png"])


def test_screenshot_returns_bytes(page):
    data = page.screenshot()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"


def test_close_is_idempotent(browser):
    p = CDPPage(browser)
    p.open()
    p.close()
    p.close()


def test_use_after_close_is_actionable(browser):
    p = CDPPage(browser)
    p.open()
    p.close()
    with pytest.raises(CDPError, match="not open"):
        p.eval("1")


def test_json_protocol_uses_expected_shape(page):
    """Guards the framing: a reply must be matched to its own id, not assumed."""
    result = page.socket.call("Runtime.evaluate", {"expression": "6*7", "returnByValue": True})
    assert json.dumps(result)  # result is JSON-serialisable, i.e. really parsed
    assert result["result"]["value"] == 42
