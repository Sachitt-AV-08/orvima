"""The phone page, rendered in a real browser, fed hostile data.

The companion file (`test_phone_surface.py`) asserts things about the page's
*source text*. That is a weak instrument, and one of the traps this project
keeps hitting: a substring check on source passes whenever the string survives
anywhere in the file, whether or not it reaches a rendered element. So "the page
shows the url" was asserted by finding the word `page_url` in the source - which
stays true if the line that uses it is deleted, and which passed against six
separate mutations that had dropped the element label, the reason, the arguments
and the risk distinction from the rendered card.

These tests render the page. The stubbed approvals endpoint returns an approval
whose page title, url and element label are all hostile strings, and the
assertions are about what a person would actually see. The stub reads the real
`X-Orvima-Token` header rather than being told what to expect, so the token
behaviour is exercised end to end instead of at two halves that can drift.

Needs a browser; skips if one is not installed.

Run: pytest tests/test_phone_dom.py -q
"""

from __future__ import annotations

import json
import time

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

from orvima.phone import PAGE  # noqa: E402

TOKEN = "hunter2"
ORIGIN = "http://localhost"

#: An approval a real site might produce, with every human-facing field replaced
#: by something an attacker would want on screen.
HOSTILE = {
    "id": "req123",
    "session_id": "s1",
    "tool": "browse_click",
    "args": {"ref": "e4", "note": "totally fine"},
    "risk": "destructive",
    "reason": "clicking this deletes the account",
    "detail": {
        "tool": "browse_click",
        "page_title": '<img src=x onerror="window.__pwned=1">Acme</img>',
        "page_url": 'https://shop.test/checkout"><script>window.__pwned=2</script>',
        "element": {
            "ref": "e4",
            "tag": "button",
            "role": "button",
            "label": "<b>Delete everything</b>",
            "text": "<b>Delete everything</b>",
        },
    },
    "created": 0,
}


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def phone(browser):
    """A phone-sized page, with every network request routed in memory."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},  # iPhone 14-ish
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()

    # Anything not explicitly served below is recorded and refused, so a test can
    # assert nothing reached a third party. Routing rather than blocking, so a
    # stray request surfaces as a recorded URL instead of an opaque timeout.
    offsite: list[str] = []

    def handler(route):
        request = route.request
        url = request.url
        if url.startswith(ORIGIN):
            if url.startswith(f"{ORIGIN}/phone"):
                route.fulfill(
                    status=200, content_type="text/html; charset=utf-8", body=PAGE
                )
            elif url.endswith("/api/approvals?gate=1"):
                state = page.evaluate("window.__orvima_test_token || null")
                payload = page.evaluate("window.__orvima_test_payload || null")
                # Read here, not at the top of the handler: evaluating on the
                # page while it is still navigating deadlocks the load, and
                # only this response shape needs the value anyway.
                ttl = page.evaluate("window.__orvima_test_ttl ?? null")
                available = page.evaluate("window.__orvima_test_available ?? true")
                if state != (request.headers.get("x-orvima-token") or None):
                    route.fulfill(
                        status=401,
                        content_type="application/json",
                        body='{"detail":"this endpoint acts on a real browser"}',
                    )
                    return
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "approvals": [payload or HOSTILE],
                            # Gate health is a sibling of `approvals`, not nested
                            # under `gate`: `gate` is the status string. Matches
                            # what `_gate_health` actually merges into the body.
                            "gate": "on",
                            "available": available,
                            "mode": "hybrid",
                            # The page works out each card's deadline from this
                            # and `created`. Omitting it is a real state, so the
                            # stub must be able to send a payload without it.
                            **({"approval_ttl": ttl} if ttl is not None else {}),
                        }
                    ),
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


def _open(phone, *, token=TOKEN, server_token=None, payload=None, ttl=None,
          available=True, settle=0):
    """Load the page holding `token`, with the server expecting `server_token`.

    `server_token` defaults to `token` because the happy path is the common case,
    and the rejected cases pass it explicitly. Two separate values rather than
    one: collapsing them would make every rejected-token test pass for the wrong
    reason, since the stub would accept whatever the page held and the server's
    refusal would never actually be exercised.

    The token is planted with an init script rather than by evaluating on the
    page, so it is in place before the page's own script runs - which is the
    ordering that decides whether the buttons appear.

    `add_init_script` takes a script string rather than a callable plus an
    argument, so values are embedded as JSON. Passing the callable instead fails
    with a TypeError that reads like a bug in the page under test.
    """
    phone.add_init_script(
        "try {"
        f" localStorage.setItem('orvima.token', {json.dumps(token or '')});"
        "} catch (e) {}"
    )
    phone.add_init_script(
        f"window.__orvima_test_token = "
        f"{json.dumps(token if server_token is None else server_token)};"
    )
    if payload is not None:
        phone.add_init_script(
            f"window.__orvima_test_payload = {json.dumps(payload)};"
        )
    if ttl is not None:
        phone.add_init_script(f"window.__orvima_test_ttl = {json.dumps(ttl)};")
    if available is not True:
        phone.add_init_script(f"window.__orvima_test_available = {json.dumps(available)};")
    phone.goto(f"{ORIGIN}/phone")
    if settle:
        phone.wait_for_timeout(settle)


def _render(phone, ttl=None, **kwargs):
    """Open the page and wait for the queue to hold a card."""
    _open(phone, ttl=ttl, **kwargs)
    phone.wait_for_selector("#queue .card", timeout=8000)


class TestTheGateStatusIsActuallyRead:
    """`gate` in the payload is the status string, not an object of settings.

    `_gate_health` merges its fields as siblings of `approvals`. A page that
    reads `payload.gate` as an object therefore gets undefined for every field
    it cares about, and cannot tell a working gate from a dead one. The symptom
    is not a crash: it is a page that looks healthy while reporting nothing.
    """

    def test_the_status_line_names_the_real_mode(self, phone):
        _open(phone, settle=900)
        line = phone.inner_text("#gate").strip()
        assert "hybrid" in line and "on" in line, (
            f"the gate status line does not reflect the mode and status the "
            f"server reported, so gate health is invisible on the page: {line!r}"
        )

    def test_an_unavailable_gate_is_stated_rather_than_hidden(self, phone):
        """Every action needs a human - the page has to say so loudly."""
        _open(phone, available=False, settle=900)
        gate = phone.inner_text("#gate")
        assert "unavailable" in gate, (
            f"the gate reports available=false and the page does not say so, so "
            f"a fully-hand-gated orvima looks like a working one: {gate!r}"
        )
        assert phone.eval_on_selector("#gate", "n => n.className") == "bad", (
            "an unavailable gate is not styled as a problem"
        )

    def test_a_healthy_gate_is_not_styled_as_a_problem(self, phone):
        _open(phone, settle=900)
        assert phone.eval_on_selector("#gate", "n => n.className") == "", (
            "a working gate is styled as bad"
        )


def _card_text(phone) -> str:
    return phone.inner_text("#queue")


def _buttons(phone) -> list[str]:
    return phone.eval_on_selector_all(
        "#queue button", "ns => ns.map(n => n.textContent.trim())"
    )


class TestTheCardShowsEnoughToDecide:
    """An approve button with nothing to look at is a rubber stamp."""

    def test_the_page_title_is_visible_as_text(self, phone):
        _render(phone)
        assert "Acme" in _card_text(phone), _card_text(phone)

    def test_the_url_is_visible(self, phone):
        _render(phone)
        assert "shop.test/checkout" in _card_text(phone), (
            "the url is not on the card, so approving is a guess about which "
            f"site is about to be charged: {_card_text(phone)!r}"
        )

    def test_the_element_being_clicked_is_named(self, phone):
        """The single most important thing on the card."""
        _render(phone)
        assert "Delete everything" in _card_text(phone), (
            f"the card does not say what is about to be clicked: {_card_text(phone)!r}"
        )

    def test_the_elements_tag_and_role_are_shown(self, phone):
        _render(phone)
        assert "button" in _card_text(phone), _card_text(phone)

    def test_the_gate_reason_is_shown(self, phone):
        """Not just the verdict. Without the reasoning a person cannot tell a
        misfire from a real finding, and learns to approve everything."""
        _render(phone)
        assert "deletes the account" in _card_text(phone)

    def test_the_arguments_are_shown(self, phone):
        _render(phone)
        assert "e4" in _card_text(phone)

    def test_the_risk_is_shown(self, phone):
        _render(phone)
        assert "destructive" in _card_text(phone).lower()


class TestTheRiskIsDistinguishableAtAGlance:
    """Two risk levels that look the same are one risk level."""

    def _background(self, phone, risk):
        _render(phone, payload={**HOSTILE, "risk": risk})
        return phone.eval_on_selector(
            "#queue .risk", "n => getComputedStyle(n).backgroundColor"
        )

    def test_destructive_looks_different_from_outward(self, phone):
        destructive = self._background(phone, "destructive")
        outward = self._background(phone, "outward")
        assert destructive != outward, (
            "a destructive action and an outward-facing one are rendered "
            f"identically ({destructive}); the badge carries no information"
        )

    @pytest.mark.parametrize("risk", ["destructive", "outward"])
    def test_the_badge_is_readable_against_its_own_background(self, phone, risk):
        """Both variants. Checking only the destructive one leaves the plain
        badge free to be unreadable, which is the variant most requests use."""
        _render(phone, payload={**HOSTILE, "risk": risk})
        colours = phone.eval_on_selector(
            "#queue .risk",
            "n => { const s = getComputedStyle(n);"
            " return [s.color, s.backgroundColor]; }",
        )

        def luminance(rgb: str) -> float:
            parts = [float(x) for x in rgb.replace("rgba", "rgb").strip("rgb() ").split(",")[:3]]
            return (0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]) / 255

        ratio = abs(luminance(colours[0]) - luminance(colours[1]))
        assert ratio > 0.4, (
            f"a {risk} badge is {colours[0]} on {colours[1]} - a luminance "
            f"difference of {ratio:.2f}, which is unreadable on a phone"
        )

    def test_the_badge_meets_the_wcag_aa_contrast_ratio(self, phone):
        """Stated as the real threshold rather than a made-up one.

        AA for normal text is 4.5:1. The badge is small bold uppercase text, so
        it is treated as normal text rather than large - which is the stricter
        reading and the one to hold it to.
        """
        _render(phone)
        colours = phone.eval_on_selector(
            "#queue .risk",
            "n => { const s = getComputedStyle(n);"
            " return [s.color, s.backgroundColor]; }",
        )

        def channel(value: float) -> float:
            value /= 255
            return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

        def relative_luminance(rgb: str) -> float:
            parts = [float(x) for x in rgb.replace("rgba", "rgb").strip("rgb() ").split(",")[:3]]
            r, g, b = (channel(p) for p in parts)
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        fg, bg = (relative_luminance(c) for c in colours)
        lighter, darker = max(fg, bg), min(fg, bg)
        ratio = (lighter + 0.05) / (darker + 0.05)
        assert ratio >= 4.5, (
            f"the risk badge is {colours[0]} on {colours[1]}: contrast ratio "
            f"{ratio:.2f}:1, below the 4.5:1 needed to read it"
        )


class TestTheJudgedPageCannotExecute:
    """The page being judged is hostile input. This is the prompt-injection case
    orvima exists to survive, arriving through the approval UI instead."""

    def test_no_script_from_the_page_runs(self, phone):
        _render(phone)
        assert phone.evaluate("window.__pwned === undefined"), (
            "content from the page under judgement executed as script"
        )

    def test_an_injected_img_tag_is_not_created(self, phone):
        _render(phone)
        assert phone.eval_on_selector_all("#queue img", "ns => ns.length") == 0, (
            "the page title was parsed as HTML: an injected element was created"
        )

    def test_no_script_element_was_injected(self, phone):
        _render(phone)
        assert phone.eval_on_selector_all("#queue script", "ns => ns.length") == 0

    def test_hostile_text_is_shown_verbatim_instead(self, phone):
        """Escaped, not dropped. Silently removing it would mean the approver
        cannot see what the page is actually claiming."""
        _render(phone)
        assert "<img src=x" in _card_text(phone), (
            "the raw title is not shown as text, so an approver cannot see the "
            f"page's real claim: {_card_text(phone)!r}"
        )

    def test_nothing_is_injected_outside_the_queue(self, phone):
        """The page has its own <script>, so this counts injected nodes rather
        than asserting there are none anywhere in the document.

        Scoped to `#queue` and its ancestors' direct children, which is where an
        unescaped value would land if one escaped.
        """
        _render(phone)
        before = phone.eval_on_selector_all(
            "body > img, body > iframe, body > object, body > embed", "ns => ns.length"
        )
        assert before == 0, (
            f"{before} element(s) were injected as direct children of <body> by "
            "page content"
        )

    def test_the_injected_markup_is_escaped_in_the_rendered_text(self, phone):
        """Readable to a human, inert to the parser."""
        _render(phone)
        html = phone.eval_on_selector("#queue", "n => n.innerHTML")
        assert "&lt;img" in html, (
            f"the page title was not escaped in the markup: {html[:200]!r}"
        )
        assert "<img" not in html


class TestButtonsRequireAToken:
    """The server decides; the page's conditional is belt and braces.

    The stub answers 401 whenever the presented token is not the expected one, so
    these are testing the page's behaviour against the server's actual answer.
    """

    def test_no_buttons_without_a_token(self, phone):
        """The read works, the decision does not."""
        _open(phone, token=None, server_token=None, settle=900)
        assert _buttons(phone) == [], (
            f"approval buttons are rendered with no token, so an unauthorised "
            f"reader can see the shape of the queue: {_buttons(phone)}"
        )

    def test_the_queue_is_readable_without_a_token(self, phone):
        """Deliberate, and worth being explicit about.

        A phone that has not been given a token still shows what the agent is
        waiting on - you cannot decide whether to go and fetch a token if you
        cannot see the request. Reading is safe here for a concrete reason:
        `create_app` refuses to build an app bound off loopback unless a token
        is set, so the only reader in the no-token state is someone already
        sitting at the machine, who could read the same data from `/api/approvals`
        or `/docs` directly.

        What is *not* safe is rendering the decision, which is the assertion
        above. Keeping those two separate is the whole design.

        `server_token=None` here reproduces the real no-token server: nothing is
        required, so the read succeeds and only the buttons are withheld.
        """
        _open(phone, token=None, server_token=None, settle=900)
        assert phone.eval_on_selector_all("#queue .card", "ns => ns.length") == 1, (
            "the queue is unreadable without a token, so there is no way to tell "
            "whether a token is worth fetching"
        )

    def test_buttons_appear_with_a_valid_token(self, phone):
        _render(phone)
        assert len(_buttons(phone)) == 2, (
            f"with a valid token there are no buttons, so the page cannot be "
            f"used at all: {_buttons(phone)}"
        )

    def test_the_buttons_are_labelled_approve_and_deny(self, phone):
        _render(phone)
        labels = _buttons(phone)
        assert "Approve" in labels and "Deny" in labels, labels

    def test_a_rejected_token_says_so_rather_than_looking_broken(self, phone):
        """The server refuses, so the page has to account for it.

        A page that just stops updating looks like an orvima that has hung.
        """
        _open(phone, token="wrong", server_token=TOKEN, settle=1200)
        gate = phone.inner_text("#gate").strip()
        assert gate and gate != "connecting…", (
            f"a rejected token leaves the page silently blank; gate line: {gate!r}"
        )

    def test_a_rejected_token_shows_no_buttons(self, phone):
        """The page holds a token the server will not accept, so it must not
        offer the decision. The server refuses anyway; this is about not
        rendering a button that cannot work."""
        _open(phone, token="wrong", server_token=TOKEN, settle=1200)
        assert _buttons(phone) == [], (
            f"buttons are shown for a token the server rejects: {_buttons(phone)}"
        )


class TestItIsUsableOneHanded:
    def test_the_decision_buttons_meet_the_tap_target_minimum(self, phone):
        _render(phone)
        heights = phone.eval_on_selector_all(
            "#queue button", "ns => ns.map(n => n.getBoundingClientRect().height)"
        )
        assert heights and min(heights) >= 44, (
            f"decision buttons are {heights}px tall; below 44px a mis-tap lands "
            "on Approve instead of Deny"
        )

    def test_approve_and_deny_are_visually_different(self, phone):
        _render(phone)
        colours = phone.eval_on_selector_all(
            "#queue button", "ns => ns.map(n => getComputedStyle(n).backgroundColor)"
        )
        assert len(set(colours)) == 2, (
            f"both decision buttons are {colours}; the most expensive mis-tap "
            "in the product is between them"
        )

    def test_the_page_does_not_scroll_sideways(self, phone):
        _render(phone)
        overflow = phone.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"the layout overflows the viewport by {overflow}px"

    def test_a_very_long_url_does_not_break_the_layout(self, phone):
        _render(
            phone,
            payload={
                **HOSTILE,
                "detail": {
                    **HOSTILE["detail"],
                    "page_url": "https://shop.test/" + "a" * 600 + "/checkout",
                },
            },
        )
        overflow = phone.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, (
            f"a long url pushed the layout {overflow}px wide; it has to break "
            "within its own box"
        )


class TestAnExpiredDecisionCannotBeApproved:
    """The queue can outlive the TTL, and a queued approval is irreversible.

    A human who walks away for ten minutes comes back to a card they no longer
    have the context to judge. The gate will refuse the answer regardless - it
    drops anything past its deadline - so the danger is not that a stale tap
    succeeds, it is that the page offers a control which silently does nothing.
    That reads as a broken queue, and the human's next move is to keep tapping.
    """

    def _card(self, phone, *, ttl, age_seconds):
        """Render one card created `age_seconds` in the past."""
        created = time.time() - age_seconds
        _render(
            phone,
            ttl=ttl,
            payload={**HOSTILE, "created": created},
        )
        return phone.query_selector("#queue .card")

    def test_a_fresh_decision_offers_both_buttons(self, phone):
        self._card(phone, ttl=300, age_seconds=5)
        assert len(_buttons(phone)) == 2, _buttons(phone)

    def test_a_live_decision_says_how_long_is_left(self, phone):
        card = self._card(phone, ttl=300, age_seconds=60)
        text = card.query_selector(".ttl").inner_text()
        assert "expires in" in text, (
            f"a queued decision does not say when it stops being answerable, so "
            f"the human cannot tell a live card from a dead one: {text!r}"
        )

    def test_a_decision_past_its_deadline_has_no_buttons(self, phone):
        self._card(phone, ttl=300, age_seconds=900)
        assert _buttons(phone) == [], (
            "buttons are offered on a decision the gate will refuse: "
            f"{_buttons(phone)}"
        )

    def test_an_expired_decision_says_so(self, phone):
        card = self._card(phone, ttl=300, age_seconds=900)
        text = card.query_selector(".ttl").inner_text()
        assert "expired" in text.lower(), (
            f"the card vanishes its controls with no explanation, so the human "
            f"thinks the queue is broken rather than that the deadline passed: {text!r}"
        )

    def test_the_expiry_notice_is_distinguishable_from_a_live_one(self, phone):
        """Colour alone must not carry it, but the wording has to differ."""
        live = self._card(phone, ttl=300, age_seconds=5).query_selector(".ttl")
        live_text, live_class = live.inner_text(), live.get_attribute("class")
        dead = self._card(phone, ttl=300, age_seconds=900).query_selector(".ttl")
        dead_text, dead_class = dead.inner_text(), dead.get_attribute("class")
        assert live_text != dead_text, (live_text, dead_text)
        assert live_class != dead_class, (live_class, dead_class)

    def test_no_deadline_means_the_buttons_stay(self, phone):
        """No TTL is not the same as an expired decision.

        A gate with no deadline is a real configuration, and removing the
        control because information was missing would be the same error as
        removing it because the action was unsafe.
        """
        _render(phone, ttl=None, payload={**HOSTILE, "created": 0})
        assert len(_buttons(phone)) == 2, (
            f"a gate reporting no deadline must leave the decision to the human: "
            f"{_buttons(phone)}"
        )

    def test_a_missing_created_timestamp_does_not_hide_the_buttons(self, phone):
        """Absent data is not evidence of expiry.

        `created` is what the countdown is computed from. If its absence were
        read as "long past the deadline", a server that stopped sending it would
        silently make every decision unanswerable - the safe-looking outcome
        being the one that quietly breaks the tool.
        """
        payload = {k: v for k, v in HOSTILE.items() if k != "created"}
        _render(phone, ttl=300, payload=payload)
        assert len(_buttons(phone)) == 2, _buttons(phone)

    def test_a_later_poll_reporting_no_ttl_clears_the_countdown(self, phone):
        """The page reuses the last TTL it saw, so a poll that reports none has
        to clear it.

        The page polls every 2.5s. If a poll arrives with no deadline and the
        cached value is left alone, every card goes on counting down against a
        gate that no longer declares one - so a live decision would have its
        controls removed on a timer nothing ever re-declared.
        """
        _render(phone, ttl=300, payload={**HOSTILE, "created": time.time() - 5})
        assert phone.query_selector("#queue .ttl") is not None, "no countdown to start with"

        phone.evaluate("window.__orvima_test_ttl = null")
        phone.wait_for_timeout(3200)  # one poll interval plus slack
        assert phone.query_selector("#queue .ttl") is None, (
            "the countdown is still on screen after the server stopped reporting "
            "a deadline, so a card expires against a TTL nothing re-declared"
        )
        assert len(_buttons(phone)) == 2, (
            f"controls were removed after the deadline went away: {_buttons(phone)}"
        )

    def test_a_missing_created_timestamp_says_nothing_about_the_deadline(self, phone):
        """No countdown is better than a fabricated one."""
        payload = {k: v for k, v in HOSTILE.items() if k != "created"}
        _render(phone, ttl=300, payload=payload)
        assert phone.query_selector("#queue .ttl") is None, (
            "a countdown is shown for a card with no creation time, so the number "
            "on screen cannot be derived from anything the server sent"
        )


class TestNoNetworkBeyondThisMachine:
    def test_nothing_is_requested_from_a_third_party(self, phone):
        """A control surface for a logged-in browser should not call home."""
        _render(phone)
        phone.wait_for_timeout(600)
        assert phone.offsite == [], f"the phone page contacted: {phone.offsite}"
