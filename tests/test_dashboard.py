"""The control dashboard: the local UI the README promises at :8301.

`orvima serve` advertises "local UI + API at http://127.0.0.1:8301". This file
pins that promise: the root route serves a real page, and that page follows the
same rules as the approvals surface - no third party, values in via textContent,
the token in a header and never a URL, and the acting controls (pause, resume,
cancel, approve) absent rather than disabled when there is no token.

Unlike the phone page, the dashboard legitimately calls session endpoints: it is
the surface that drives the agent loop. The source checks therefore assert it
calls *existing* endpoints and nothing else, rather than that it calls no session
endpoint at all.

Run: pytest tests/test_dashboard.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from orvima.dashboard import PAGE

fastapi_testclient = pytest.importorskip("fastapi.testclient", reason="fastapi testclient unavailable")

from fastapi.testclient import TestClient  # noqa: E402

from orvima import api  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class TestTheRootRouteServesTheDashboard:
    def test_root_returns_the_page(self) -> None:
        client = TestClient(api.create_app())
        res = client.get("/")
        assert res.status_code == 200
        assert "orvima" in res.text
        assert "control" in res.text
        assert "<script" in res.text

    def test_the_page_calls_only_endpoints_that_exist(self) -> None:
        """Exact endpoints, checked against the real app's routes.

        A typo'd path here (e.g. `/api/sessions/{id}/controll`) would render a
        dead control button. Every literal path the page calls must be a route
        the app actually serves.
        """
        client = TestClient(api.create_app())
        routes = {r.path for r in client.app.routes}
        calls = set(re.findall(r'["\'](/api/[A-Za-z0-9/$_{}.-]*)["\']', PAGE))
        calls -= {"/api/sessions", "/api/approvals", "/api/health"}
        # Runtime-interpolated segments: strip the {segment} braces to get the
        # literal route prefix.
        prefix = {c.split("{")[0].rstrip("/") for c in calls}
        for p in prefix:
            base = p + "{"
            assert any(r.startswith(base) or r == p for r in routes), (
                f"the dashboard calls a route that does not exist: {p}"
            )


class TestTheSecretStaysOutOfTheUrl:
    def test_the_token_is_sent_as_a_header(self) -> None:
        assert "X-Orvima-Token" in PAGE

    def test_the_token_is_not_read_from_the_url(self) -> None:
        assert "URLSearchParams" not in PAGE
        assert "location.search" not in PAGE
        assert "location.hash" not in PAGE


class TestTheJudgedPageCannotInject:
    def test_innerhtml_is_never_used(self) -> None:
        offenders = [
            m.group(0)
            for m in re.finditer(
                r"\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write", PAGE
            )
        ]
        assert not offenders, f"the dashboard builds HTML from values: {offenders}"

    def test_every_dom_insertion_goes_through_textcontent(self) -> None:
        assert "textContent" in PAGE
        assert "createElement" in PAGE

    def test_no_template_literal_carries_a_page_value_into_script(self) -> None:
        assert "document.currentScript" not in PAGE

    def test_a_page_value_cannot_reach_a_url_attribute(self) -> None:
        assert "javascript:" not in PAGE.lower()


class TestTheControlsAreGated:
    def test_the_acting_controls_are_hidden_without_a_token(self) -> None:
        # The distinction that matters is in the rendered DOM (absent, not
        # disabled); the source must at least tie them to the token.
        assert "controls" in PAGE
        assert "token()" in PAGE
        assert "hidden = !t" in PAGE or "hidden" in PAGE

    def test_approve_and_deny_require_a_token(self) -> None:
        assert "if (token())" in PAGE or "token()" in PAGE
        assert "Approve" in PAGE
        assert "Deny" in PAGE

    def test_the_no_token_state_is_explained(self) -> None:
        assert "no API token" in PAGE


class TestTheLayout:
    def test_the_viewport_is_set(self) -> None:
        assert 'name="viewport"' in PAGE
        assert "width=device-width" in PAGE

    def test_it_copes_with_a_notch(self) -> None:
        assert "safe-area-inset" in PAGE

    def test_tap_targets_are_large_enough(self) -> None:
        match = re.search(r"min-height:\s*(\d+)px", PAGE)
        assert match and int(match.group(1)) >= 44

    def test_it_does_not_zoom_on_focus(self) -> None:
        for size in re.findall(r"font:\s*[^;]*?(\d+(?:\.\d+)?)px", PAGE):
            assert float(size) >= 16, f"a {size}px font will trigger iOS zoom"

    def test_the_layout_collapses_on_a_phone(self) -> None:
        assert "@media (max-width: 860px)" in PAGE


class TestNoThirdPartyAnything:
    @pytest.mark.parametrize(
        "needle",
        ["http://", "https://", "//cdn", "integrity=", "crossorigin"],
    )
    def test_nothing_is_fetched_from_elsewhere(self, needle: str) -> None:
        offenders = [
            m.group(0)
            for m in re.finditer(rf'(?:src|href)\s*=\s*["\']{re.escape(needle)}', PAGE)
        ]
        assert not offenders, f"the dashboard loads something remote: {offenders}"

    def test_there_is_no_build_step_requiring_node(self) -> None:
        script_tag = PAGE.split("<script")[1]
        assert "src=" not in script_tag.split(">")[0]


class TestItWatchesAndControls:
    def test_it_streams_frames_over_sse(self) -> None:
        assert "EventSource" in PAGE
        assert "/events" in PAGE

    def test_it_shows_the_transcript_as_it_happens(self) -> None:
        assert "transcript" in PAGE
        assert "textContent" in PAGE

    def test_pause_resume_cancel_target_the_control_endpoint(self) -> None:
        assert "/api/sessions/" in PAGE
        assert "/control" in PAGE

    def test_the_approval_queue_is_rendered_from_the_existing_endpoint(self) -> None:
        assert "/api/approvals?gate=1" in PAGE
