"""The control dashboard, rendered in a real browser against an in-memory stub.

The dashboard's promise is the README's: `orvima serve` really is a local UI at
`http://127.0.0.1:8301`. The claims worth proving in a rendered page are:

1. **The judged page cannot inject.** The transcript is streamed live from the
   agent loop, and its rows can carry text from whichever page the agent was
   browsing - attacker-controlled by definition. A hostile row must render as
   text, never parse.
2. **The acting controls are absent without a token.** Pause, resume, cancel
   and approve all drive a real browser. Absent, not disabled.
3. **Nothing is fetched from anywhere but orvima.** A control surface for a
   logged-in browser should not call home.
4. **The live stream actually reaches the page.** The dashboard is the "watch
   the agent live" surface; if the SSE viewport never renders a frame, the
   page is a list of buttons with nothing to watch.

Run: pytest tests/test_dashboard_dom.py -q
"""

from __future__ import annotations

import json

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

from orvima.dashboard import PAGE  # noqa: E402

ORIGIN = "http://localhost"
TOKEN = "hunter2"

#: A transcript row the way it would arrive from the agent loop after the agent
#: browsed a hostile page: the result is an object carrying page text the page
#: must show verbatim, without parsing.
HOSTILE_ROW = {
    "kind": "tool_result",
    "step": 1,
    "tool": "browse_extract",
    "result": {"text": '<img src=x onerror="window.__pwned=1">Acme</img>'},
}

SESSIONS = [
    {"id": "s1", "mode": "real", "status": "running", "steps": 3, "goal": "hostile"},
]

#: A tiny valid 1x1 PNG so the viewport img loads without error noise.
TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def dash(browser):
    """A phone-sized dashboard with every request routed in memory."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},  # iPhone-ish
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    offsite: list[str] = []

    def handler(route):
        request = route.request
        url = request.url
        if url.startswith(ORIGIN):
            if url == f"{ORIGIN}/" or url == f"{ORIGIN}/dashboard":
                route.fulfill(
                    status=200, content_type="text/html; charset=utf-8", body=PAGE
                )
            elif url.endswith("/api/health"):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "version": "0.1.6", "sessions": 1}),
                )
            elif url.endswith("/api/sessions") and request.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "sessions": SESSIONS}),
                )
            elif "/api/sessions/" in url and url.endswith("/events"):
                # The events stream is read-only (frames + transcript), so it is
                # not token-gated - the interface mirrors the API.
                body = (
                    'data: {"type":"log","row":'
                    + json.dumps(HOSTILE_ROW)
                    + "}\n\n"
                    'data: {"type":"frame","png_b64":"'
                    + TINY_PNG
                    + '"}\n\n'
                    'data: {"type":"status","status":"running"}\n\n'
                )
                route.fulfill(
                    status=200,
                    content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache"},
                    body=body,
                )
            elif "/api/sessions/" in url and url.endswith("/control"):
                expected = page.evaluate("window.__orvima_test_server_token || null")
                offered = request.headers.get("x-orvima-token") or None
                if offered != expected:
                    route.fulfill(
                        status=401,
                        content_type="application/json",
                        body='{"detail":"token required"}',
                    )
                    return
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"ok": true, "status": "paused"}',
                )
            elif url.endswith("/api/approvals?gate=1"):
                expected = page.evaluate("window.__orvima_test_server_token || null")
                offered = request.headers.get("x-orvima-token") or None
                readonly = expected is None and offered is None
                if not readonly and offered != expected:
                    route.fulfill(
                        status=401,
                        content_type="application/json",
                        body='{"detail":"token required"}',
                    )
                    return
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "approvals": [],
                            "gate": "on",
                            "available": True,
                            "mode": "hybrid",
                        }
                    ),
                )
            elif "/api/approvals/" in url and request.method == "POST":
                expected = page.evaluate("window.__orvima_test_server_token || null")
                offered = request.headers.get("x-orvima-token") or None
                if offered != expected:
                    route.fulfill(
                        status=401,
                        content_type="application/json",
                        body='{"detail":"token required"}',
                    )
                    return
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"ok": true, "approved": true}',
                )
            else:
                route.fulfill(status=404, content_type="application/json", body="{}")
            return
        offsite.append(url)
        route.fulfill(status=404, body="{}")

    page.route("**/*", handler)
    page.offsite = offsite
    yield page
    context.close()


def _open(dash, *, token=TOKEN, server_token=None, settle=0):
    """Load the dashboard holding `token`, with the server expecting
    `server_token` (defaults to `token`; the rejected cases pass it explicitly).
    """
    dash.add_init_script(
        "try {"
        f" localStorage.setItem('orvima.token', {json.dumps(token or '')});"
        "} catch (e) {}"
    )
    dash.add_init_script(
        f"window.__orvima_test_server_token = "
        f"{json.dumps(token if server_token is None else server_token)};"
    )
    dash.goto(f"{ORIGIN}/")
    if settle:
        dash.wait_for_timeout(settle)


def _watch(dash):
    """Select the session so the live stream opens."""
    dash.wait_for_selector("#sessions li.session", timeout=8000)
    dash.click("#sessions li.session")
    dash.wait_for_selector("#transcript li:not(.empty)", timeout=8000)


class TestTheLiveStreamReachesThePage:
    def test_a_session_can_be_selected_and_watched(self, dash):
        _open(dash, settle=400)
        assert dash.eval_on_selector_all("#sessions li.session", "ns => ns.length") >= 1
        _watch(dash)
        dash.wait_for_timeout(300)
        status = dash.inner_text("#status").strip()
        assert "running" in status, f"the live status is not shown: {status!r}"

    def test_the_live_frame_is_rendered(self, dash):
        """The dashboard is the 'watch it work' surface: a frame must arrive."""
        _open(dash, settle=400)
        _watch(dash)
        dash.wait_for_selector("#frame[src]", timeout=8000)
        src = dash.eval_on_selector("#frame", "n => n.getAttribute('src')")
        assert src.startswith("data:image/png;base64,"), (
            f"the viewport did not render the streamed frame: {src[:40]!r}"
        )

    def test_the_transcript_shows_the_hostile_row_as_text(self, dash):
        _open(dash, settle=400)
        _watch(dash)
        text = dash.inner_text("#transcript")
        assert "Acme" in text and "<img src=x" in text, (
            f"the transcript did not show the row verbatim: {text!r}"
        )


class TestTheJudgedPageCannotExecute:
    def test_no_script_from_a_hostile_row_runs(self, dash):
        _open(dash, settle=400)
        _watch(dash)
        dash.wait_for_timeout(300)
        assert dash.evaluate("window.__pwned === undefined"), (
            "a transcript row from the judged page executed as script"
        )

    def test_no_img_was_created_by_the_hostile_row(self, dash):
        _open(dash, settle=400)
        _watch(dash)
        assert dash.eval_on_selector_all("#transcript img", "ns => ns.length") == 0, (
            "the hostile transcript row was parsed into an img element"
        )

    def test_the_row_is_escaped_in_the_markup(self, dash):
        _open(dash, settle=400)
        _watch(dash)
        html = dash.eval_on_selector("#transcript", "n => n.innerHTML")
        assert "<img" not in html, f"a hostile row became live markup: {html[:200]!r}"
        assert "&lt;img" in html, (
            "the hostile row is not escaped as text, so a viewer cannot see the "
            f"raw claim the page made: {html[:200]!r}"
        )


class TestTheControlsRequireAToken:
    def test_no_controls_without_a_token(self, dash):
        """The read works, the driving does not."""
        _open(dash, token=None, settle=900)
        assert dash.eval_on_selector("#controls", "n => n.hidden") is True, (
            "pause/resume/cancel are offered with no token"
        )
        assert dash.eval_on_selector_all("#controls button", "ns => ns.length") == 0

    def test_a_rejected_token_is_reported_not_silent(self, dash):
        """A token the server refuses must surface as an error line, else a
        broken control looks like a hung server."""
        _open(dash, token="wrong", server_token=TOKEN, settle=900)
        dash.wait_for_timeout(800)
        err = dash.eval_on_selector("#err", "n => n.textContent")
        assert "rejected" in err, f"a rejected token is not reported: {err!r}"

    def test_controls_appear_with_a_token(self, dash):
        _open(dash, settle=900)
        labels = dash.eval_on_selector_all(
            "#controls button", "ns => ns.map(n => n.textContent.trim())"
        )
        assert {"Pause", "Resume", "Cancel"} <= set(labels), labels

    def test_pause_is_sent_with_the_token_header(self, dash):
        """The control must arrive with the token, or the server refuses it."""
        sent: list[str] = []
        dash.on(
            "request",
            lambda r: sent.append(
                r.url + " " + (r.headers.get("x-orvima-token") or "")
            ),
        )
        _open(dash, settle=900)
        _watch(dash)  # a session must be selected before the control can act
        dash.click("#pause")
        dash.wait_for_timeout(500)
        acted = [u for u in sent if "/api/sessions/" in u and "/control" in u]
        assert acted, "the pause control never reached the server"
        assert all(u.endswith(TOKEN) for u in acted), (
            f"the pause control was sent without the token: {acted}"
        )

    def test_the_no_token_state_is_explained(self, dash):
        _open(dash, token=None, settle=900)
        locked = dash.inner_text("#locked")
        assert "no API token" in locked, f"the loopback state is not explained: {locked!r}"


class TestItIsUsableOneHanded:
    def test_the_start_button_meets_the_tap_target_minimum(self, dash):
        _open(dash, settle=300)
        height = dash.eval_on_selector(
            "form#create button", "n => n.getBoundingClientRect().height"
        )
        assert height >= 44, f"the start button is {height}px tall"

    def test_the_page_does_not_scroll_sideways(self, dash):
        _open(dash, settle=300)
        overflow = dash.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"the layout overflows the viewport by {overflow}px"


class TestNoNetworkBeyondThisMachine:
    def test_nothing_is_requested_from_a_third_party(self, dash):
        _open(dash, token=TOKEN, settle=900)
        dash.wait_for_timeout(600)
        assert dash.offsite == [], f"the dashboard contacted: {dash.offsite}"
