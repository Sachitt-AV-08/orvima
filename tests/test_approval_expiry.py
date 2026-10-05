"""The approval queue must never offer a decision the gate will refuse.

Split from the gate's own TTL tests because this is a different claim. Those
prove the gate expires a request; these prove the *surface a human reads* agrees
with the gate. The phone page (tests/test_phone_dom.py) covers the rendering.

The endpoint is exercised through the real FastAPI app, because the bug being
guarded here was a mismatch between the endpoint's response shape and what the
page read. A test that stubbed the endpoint could not have caught it.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from orvima import api
from orvima.sentinel_gate import make_gate


class ShownRisk:
    def __init__(self, risk: str = "destructive", reason: str = "x") -> None:
        self.risk = risk
        self.reason = reason


@pytest.fixture
def gate():
    return make_gate(classifier_mode="off", approval_ttl=0.05)


@pytest.fixture
def client(gate, monkeypatch):
    monkeypatch.setattr(api, "get_gate", lambda rebuild=False: gate)
    return TestClient(api.create_app())


class TestTheEndpointDoesNotListUnanswerableDecisions:
    """An expired request is dropped by `resolve()`, which returns None.

    So listing one shows a human a live-looking decision whose tap silently
    does nothing. The card vanishes on the next poll and the human's reasonable
    conclusion is that the queue is broken.
    """

    def test_a_live_decision_is_listed(self, client, gate):
        gate.request_approval("s1", "browse_click", {}, ShownRisk())
        body = client.get("/api/approvals").json()
        assert len(body["approvals"]) == 1, body

    def test_a_decision_past_its_ttl_is_not_listed(self, client, gate):
        gate.request_approval("s1", "browse_click", {}, ShownRisk())
        time.sleep(0.15)
        body = client.get("/api/approvals").json()
        assert body["approvals"] == [], (
            f"the queue still offers a decision the gate will refuse: {body}"
        )

    def test_reading_the_queue_records_the_expiry(self, client, gate):
        """Otherwise the waiting agent loop cannot tell expiry from a drop.

        `Agent._await_approval` needs `lapsed()` to be true for an expired
        request, because `resolve()` pops an answered one too and absence
        alone is ambiguous.
        """
        request_id = gate.request_approval("s1", "browse_click", {}, ShownRisk())
        time.sleep(0.15)
        client.get("/api/approvals")
        assert gate.lapsed(request_id), (
            "the request was removed without being marked lapsed, so a waiting "
            "agent cannot distinguish an expiry from an answered request"
        )

    def test_a_fresh_decision_is_not_marked_lapsed(self, client, gate):
        request_id = gate.request_approval("s1", "browse_click", {}, ShownRisk())
        client.get("/api/approvals")
        assert not gate.lapsed(request_id), (
            "a live decision was marked lapsed, which would abort a run that is "
            "still legitimately waiting for a human"
        )

    def test_session_filtering_still_works_alongside_expiry(self, client, gate):
        gate.request_approval("s1", "browse_click", {}, ShownRisk())
        gate.request_approval("s2", "browse_click", {}, ShownRisk())
        assert len(client.get("/api/approvals", params={"session_id": "s1"}).json()["approvals"]) == 1


class TestTheEndpointReportsItsDeadline:
    """The page computes each card's countdown from the TTL and `created`.

    Age alone cannot say whether a decision is still answerable, so the TTL has
    to be on the wire. Its absence is a legitimate state (a gate configured with
    no expiry) and must be distinguishable from the field being missing.
    """

    def test_the_ttl_is_reported(self, client):
        body = client.get("/api/approvals", params={"gate": 1}).json()
        assert body["approval_ttl"] == 0.05, body

    def test_the_ttl_is_absent_unless_asked_for(self, client):
        """A parameter that changes the response shape is asked for, not imposed."""
        assert "approval_ttl" not in client.get("/api/approvals").json()

    def test_gate_health_is_a_sibling_of_approvals_not_nested(self, client):
        """`gate` is the status string.

        Reading health from `body["gate"]` yields undefined for every field,
        which is how the page's "gate unavailable" warning came to never fire.
        """
        body = client.get("/api/approvals", params={"gate": 1}).json()
        assert isinstance(body["gate"], str), (
            f"gate is not a status string, so a reader treating it as a settings "
            f"object silently sees undefined for every field: {body!r}"
        )
        assert body["available"] is True
        assert isinstance(body["mode"], str)

    def test_a_gate_with_no_expiry_reports_none(self, monkeypatch):
        """"No deadline" and "field missing" must not look the same."""
        opt_out = make_gate(classifier_mode="off", approval_ttl=0)
        monkeypatch.setattr(api, "get_gate", lambda rebuild=False: opt_out)
        body = TestClient(api.create_app()).get("/api/approvals", params={"gate": 1}).json()
        assert "approval_ttl" in body, (
            f"a gate with no expiry must still report the field, set to null: {body!r}"
        )
        assert body["approval_ttl"] is None

    def test_a_gate_that_stops_reporting_a_ttl_does_not_keep_the_last_one(self, monkeypatch):
        """The cached value must be cleared, not merely not-updated.

        The phone page polls every 2.5s and reuses the last TTL it saw. If a
        poll reports no deadline and the page keeps counting down against the
        previous one, cards carry a deadline from a gate that no longer exists -
        so a card expires on a timer that was never re-declared.
        """
        expiring = make_gate(classifier_mode="off", approval_ttl=60.0)
        monkeypatch.setattr(api, "get_gate", lambda rebuild=False: expiring)
        client = TestClient(api.create_app())
        first = client.get("/api/approvals", params={"gate": 1}).json()
        assert first["approval_ttl"] == 60.0, first

        monkeypatch.setattr(
            api, "get_gate", lambda rebuild=False: make_gate(classifier_mode="off", approval_ttl=0)
        )
        second = client.get("/api/approvals", params={"gate": 1}).json()
        assert "approval_ttl" in second, second
        assert second["approval_ttl"] is None, (
            f"a gate with no expiry still reports the previous gate's deadline, "
            f"so a client reuses a deadline nothing re-declared: {second!r}"
        )

    def test_health_and_the_queue_agree_on_the_same_gate(self, client, gate):
        """`gate=1` and `/api/gate/stats` cannot drift apart.

        The phone page and the desktop UI read these two separately, so a
        divergence is a page disagreeing with itself.
        """
        gate.request_approval("s1", "browse_click", {}, ShownRisk())
        listed = client.get("/api/approvals", params={"gate": 1}).json()
        stats = client.get("/api/gate/stats").json()
        for key in ("available", "mode", "approval_ttl"):
            assert listed[key] == stats[key], (
                f"{key} differs between /api/approvals?gate=1 and /api/gate/stats: "
                f"{listed[key]!r} vs {stats[key]!r}"
            )
