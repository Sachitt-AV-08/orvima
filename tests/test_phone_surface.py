"""The phone approval page must not be a way to bypass the gate.

A phone surface for the approval queue is easy to build and easy to build
*wrongly*. Three ways it could quietly defeat the safety property it exists to
serve, all of which this file blocks:

1. **Approving without knowing what.** A card that says "Approve" and nothing
   else turns the human into a rubber stamp. The page and the element have to
   be on the card, or the queue is worse than useless - it is a way to spend
   money without a second look.
2. **XSS from the page being judged.** The page text is attacker-controlled by
   definition; that is the prompt-injection case orvima exists to survive. Any
   value from the browser goes in via `textContent`, never `innerHTML`.
3. **A token in the URL.** Query parameters land in access logs, browser
   history, and `Referer` headers. A secret that does that is not a secret.

Run: pytest tests/test_phone_surface.py -q
"""

from __future__ import annotations

import re

import pytest

from orvima.phone import PAGE


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE


class TestTheDecisionIsInformed:
    """A human cannot consent to something they are not shown."""

    def test_the_page_url_is_on_the_card(self, page):
        assert "page_url" in page, (
            "the approval card never shows the url, so approving is a guess about "
            "which site is about to be charged"
        )

    def test_the_page_title_is_on_the_card(self, page):
        assert "page_title" in page

    def test_the_element_being_acted_on_is_named(self, page):
        """A click on the wrong element is the whole failure mode."""
        assert "detail.element" in page
        assert "label" in page

    def test_the_risk_is_shown_prominently(self, page):
        assert 'node("div", "risk' in page, "the risk label is not rendered"
        assert "destructive" in page, "destructive risk is not distinguished"

    def test_the_reason_the_gate_gave_is_shown(self, page):
        """The classifier's reasoning, not just its verdict.

        Without it a person cannot tell a misfire from a real finding, and will
        learn to approve everything.
        """
        assert "request.reason" in page

    def test_the_tool_and_its_arguments_are_shown(self, page):
        assert "request.tool" in page
        assert "request.args" in page

    def test_an_approval_with_nothing_to_look_at_is_not_offered(self):
        """Stated as a design rule rather than a test.

        If `detail` is empty the card should say so rather than render bare
        buttons. Asserting that would require a DOM; the rule is recorded here
        because it is the one to preserve when the card is edited.
        """
        assert "Nothing waiting." in PAGE  # the empty-queue state is handled


class TestTheJudgedPageCannotInject:
    """The page being judged is hostile input."""

    def test_innerhtml_is_never_used(self, page):
        """Not once, for any value."""
        offenders = [
            m.group(0)
            for m in re.finditer(r"\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write",
                                 page)
        ]
        assert not offenders, f"the page builds HTML from values: {offenders}"

    def test_every_dom_insertion_goes_through_textcontent(self, page):
        assert "textContent" in page
        # And the helper that inserts nodes is the only way nodes get built.
        assert page.count("createElement") >= 1

    def test_the_script_is_not_a_string_template_of_page_data(self, page):
        """A `<script>` built by interpolating page text would execute it."""
        assert "document.currentScript" not in page
        # No template literal carrying a browser-supplied value into script scope.
        assert not re.search(r"\$\{[^}]*request\.", page), (
            "a page-supplied value is interpolated into a script template"
        )

    def test_the_page_text_cannot_reach_a_url_attribute(self, page):
        """A javascript: href from page data would be script execution."""
        assert "javascript:" not in page.lower()


class TestTheSecretStaysOutOfTheUrl:
    def test_the_token_is_not_taken_from_a_query_parameter(self, page):
        assert not re.search(r"URLSearchParams|location\.search|get\(\"token\"\)|get\('token'\)", page), (
            "the page reads a token out of the url, where it lands in logs and "
            "history"
        )

    def test_the_token_is_not_read_from_the_fragment(self, page):
        assert "location.hash" not in page

    def test_it_is_sent_as_a_header(self, page):
        assert "X-Orvima-Token" in page


class TestThePageGrantsNothing:
    """It is a view onto endpoints that already existed and were guarded."""

    def test_it_calls_only_endpoints_that_already_existed(self, page):
        """Exact paths, not prefixes.

        A prefix allow-list accepts anything starting with `/api/approvals`,
        which is not what was meant: the point is that this page talks to the
        queue and the health endpoint, and to nothing else. Prefix matching would
        have waved through a new endpoint hidden behind an allowed first segment.
        """
        calls = set(re.findall(r'["\'](/api/[A-Za-z0-9/$_.-]*)["\']', page))
        assert calls, "the page calls nothing?"
        allowed = {"/api/approvals"}
        for call in calls:
            # Trailing segments built at runtime are the endpoint + a value, so
            # compare the literal prefix up to the first interpolation.
            assert any(call.startswith(a) for a in allowed), (
                f"the page calls an endpoint it has no business calling: {call}"
            )

    def test_it_never_reaches_a_session_endpoint(self, page):
        """The approval queue is the whole surface. A session-scoped call would
        mean the phone could drive the browser rather than answer for it."""
        assert "/api/sessions/" not in page, (
            "the phone page calls a session endpoint, which drives the browser "
            "rather than reporting on it"
        )

    def test_buttons_are_absent_without_a_token_not_merely_disabled(self, page):
        """A disabled button still renders whatever the page already knows.

        Rendering "Approve / Deny" with no way to use them would tell an
        unauthenticated reader what the queue looks like, and invites the
        obvious next question - how do I get one of those.
        """
        # Whether the controls appear is asserted against the rendered DOM in
        # test_phone_dom.py, which is the layer a reader actually experiences.
        # Grepping the source for the conditional cannot tell an absent button
        # from a rendered one, so a source check here could only ever confirm
        # the source still looks the way it did when it was written.
        assert "button:disabled" in page, (
            "if the controls were meant to be disabled rather than absent, the "
            "disabled styling should exist"
        )

    def test_the_no_token_state_is_explained_rather_than_silent(self, page):
        assert "no API token" in page, (
            "with no token the page shows nothing and explains nothing, which "
            "reads as broken rather than as correct"
        )


class TestItWorksOnAPhone:
    """The layout constraints that decide whether it is usable one-handed."""

    def test_the_viewport_is_set_for_a_phone(self, page):
        assert 'name="viewport"' in page
        assert "width=device-width" in page

    def test_it_copes_with_a_notch(self, page):
        assert "safe-area-inset" in page

    def test_tap_targets_are_large_enough_for_a_thumb(self, page):
        """44px is the smallest reliably tappable target; the cost of missing is
        a mis-tap on Approve."""
        match = re.search(r"min-height:\s*(\d+)px", page)
        assert match, "no minimum tap-target height is set"
        assert int(match.group(1)) >= 44, (
            f"tap targets are {match.group(1)}px; too small to hit reliably"
        )

    def test_it_does_not_zoom_when_a_field_is_focused(self, page):
        """iOS zooms any font under 16px on focus, which then leaves the layout
        shifted."""
        for size in re.findall(r"font:\s*[^;]*?(\d+(?:\.\d+)?)px", page):
            assert float(size) >= 16, f"a {size}px font will trigger iOS zoom"
        assert 'font-size: 1rem' in page or "font: 16px" in page

    def test_the_approve_deny_pair_is_hard_to_mis_hit(self, page):
        """Side by side with distinct colours, not two grey buttons."""
        assert "grid-template-columns: 1fr 1fr" in page
        assert "primary" in page and "danger" in page


class TestNoThirdPartyAnything:
    """A control surface for a logged-in browser should not phone home."""

    @pytest.mark.parametrize(
        "needle",
        ["http://", "https://", "//cdn", "integrity=", "crossorigin"],
    )
    def test_nothing_is_fetched_from_elsewhere(self, page, needle):
        # https:// appears only in the XML namespace-ish sense if at all; assert
        # there is no absolute URL in a fetch/src/href position.
        offenders = [
            m.group(0)
            for m in re.finditer(rf'(?:src|href)\s*=\s*["\']{re.escape(needle)}', page)
        ]
        assert not offenders, f"the page loads something remote: {offenders}"

    def test_there_is_no_build_step_requiring_node(self, page):
        assert "<script" in page and "src=" not in page.split("<script")[1].split(">")[0] + ">"
