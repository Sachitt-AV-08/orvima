"""The owner page, rendered in a real browser against an in-memory stub.

The owner analytics claim three safety properties that only a rendered page can
prove: the passphrase never leaves the machine except in a request header
(never a URL), the numbers are rendered as text so a hostile value cannot
execute, and nothing is fetched from anywhere but orvima itself. Each is
asserted the way it would actually present itself: as injected nodes in the
DOM, as a `window.__pwned` flag, as a recorded offsite URL.

The analytics payload is not attacker-controlled in the real system - it is the
owner's own measured state - but the version string and gateway numbers are
still text being interpolated into a document, and the page's own rule is
"values come in via textContent". A hostile value in the stub proves the rule
is code, not habit.

Run: pytest tests/test_owner_dom.py -q
"""

from __future__ import annotations

import json

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

from orvima.owner import PAGE  # noqa: E402

ORIGIN = "http://localhost"
KEY = "test-owner-key"

#: A hostile value for a field the page renders. The real server would never
#: send this (the version is orvima's own), but the rule being tested is that
#: the page treats every value as text it must not parse.
HOSTILE_VERSION = '<img src=x onerror="window.__pwned=1">0.1.6'
HOSTILE_MODE = "<b>demo</b>"

PAYLOAD = {
    "ok": True,
    "version": HOSTILE_VERSION,
    "uptime_seconds": 3661,
    "sessions": {
        "total": 2,
        "by_mode": {HOSTILE_MODE: 1, "real": 1},
        "by_status": {"idle": 1, "running": 1},
    },
    "steps": 17,
    "transcript_rows": 84,
    "api_token_configured": True,
    "gate": {
        "available": True,
        "pending": 1,
        "stats": {"evaluated": 40, "auto_approved": 12, "prompted": 2,
                  "approved": 1, "denied": 0, "degraded": 0, "expired": 0},
    },
}


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def owner(browser):
    """A phone-sized owner page with every request routed in memory."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
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
            if url.startswith(f"{ORIGIN}/owner"):
                route.fulfill(
                    status=200, content_type="text/html; charset=utf-8", body=PAGE
                )
            elif url.endswith("/api/owner/analytics"):
                expected = page.evaluate("window.__orvima_test_key || null")
                offered = request.headers.get("x-orvima-owner") or None
                if offered != expected:
                    route.fulfill(
                        status=403,
                        content_type="application/json",
                        body='{"detail":"wrong or missing owner passphrase"}',
                    )
                    return
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(PAYLOAD),
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


def _open(owner, *, key=None, settle=0):
    """Load the owner page; the server expects the passphrase `key`."""
    owner.add_init_script(f"window.__orvima_test_key = {json.dumps(key)};")
    owner.goto(f"{ORIGIN}/owner")
    if settle:
        owner.wait_for_timeout(settle)


def _unlock(owner, with_key=KEY):
    """Submit the passphrase field, as the human would."""
    owner.fill("#key", with_key)
    owner.click("form#auth button")


class TestThePassphraseTravelsInAHeader:
    def test_the_passphrase_is_sent_not_kept_in_a_url(self, owner):
        requests: list[str] = []
        owner.on("request", lambda r: requests.append(r.url))
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        analytics = [u for u in requests if "/api/owner/analytics" in u]
        assert analytics, "the page never asked for the analytics"
        for url in analytics:
            assert KEY not in url, f"the passphrase is in a URL: {url}"

    def test_the_header_is_presented_without_a_query_string(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        assert owner.url.endswith("/owner"), owner.url


class TestTheGateActuallyGates:
    def test_a_wrong_passphrase_is_rejected_and_says_so(self, owner):
        _open(owner, key=KEY)
        _unlock(owner, with_key="wrong-key")
        owner.wait_for_function(
            "document.getElementById('err').textContent.length > 0", timeout=8000
        )
        assert "wrong passphrase" in owner.inner_text("#err"), owner.inner_text("#err")
        assert owner.eval_on_selector("#stats", "n => n.hidden") is True

    def test_the_right_passphrase_unlocks_the_numbers(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        text = owner.inner_text("#stats")
        lowered = text.lower()
        assert "17" in text and "2" in text and "uptime" in lowered, text

    def test_an_empty_passphrase_does_nothing(self, owner):
        _open(owner, key=KEY)
        owner.click("form#auth button")  # empty field
        owner.wait_for_timeout(600)
        assert owner.eval_on_selector("#stats", "n => n.hidden") is True


class TestTheJudgedValueCannotExecute:
    """The page's values are inert text, even when they look like markup."""

    def test_no_script_from_a_hostile_value_runs(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        assert owner.evaluate("window.__pwned === undefined"), (
            "a value from the analytics payload executed as script"
        )

    def test_hostile_values_are_not_parsed_as_html(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        assert owner.eval_on_selector_all("#stats img", "ns => ns.length") == 0, (
            "a hostile value was parsed into an img element"
        )
        assert owner.eval_on_selector_all("#stats script", "ns => ns.length") == 0

    def test_hostile_text_is_shown_verbatim_instead(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        text = owner.inner_text("#stats")
        assert "<b>demo</b>" in text, (
            "the hostile mode name is not shown as text, so the owner cannot see "
            f"what the server actually sent: {text!r}"
        )

    def test_the_injected_markup_is_escaped_in_the_markup(self, owner):
        _open(owner, key=KEY)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        html = owner.eval_on_selector("#stats", "n => n.innerHTML")
        assert "<img" not in html, "a hostile value was parsed into live markup"
        assert "&lt;img" in html, (
            "the hostile value is escaped as text, so the owner cannot see the "
            f"raw value the server sent: {html[:200]!r}"
        )


class TestItIsUsableOneHanded:
    def test_the_unlock_button_meets_the_tap_target_minimum(self, owner):
        _open(owner, settle=300)
        height = owner.eval_on_selector(
            "form#auth button", "n => n.getBoundingClientRect().height"
        )
        assert height >= 44, f"the unlock button is {height}px tall"

    def test_the_page_does_not_scroll_sideways(self, owner):
        _open(owner, settle=300)
        overflow = owner.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"the layout overflows the viewport by {overflow}px"


class TestNoNetworkBeyondThisMachine:
    def test_nothing_is_requested_from_a_third_party(self, owner):
        _open(owner, key=KEY, settle=600)
        _unlock(owner)
        owner.wait_for_selector("#stats", state="visible", timeout=8000)
        owner.wait_for_timeout(600)
        assert owner.offsite == [], f"the owner page contacted: {owner.offsite}"
