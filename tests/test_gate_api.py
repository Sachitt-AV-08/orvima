"""API-level tests for the approval endpoints.

Exercised through the real FastAPI app with the TestClient, because the
interesting failures are in the wiring - a route that exists but is never
reached, a loop that blocks the server, an approval posted to the wrong place.
"""

from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient", reason="fastapi testclient unavailable")
pytest.importorskip("sentinel", reason="sentinel not on path")

from fastapi.testclient import TestClient  # noqa: E402

from orvima import api  # noqa: E402


@pytest.fixture
def client():
    return TestClient(api.create_app())


def test_health_and_tools_still_work(client) -> None:
    assert client.get("/api/health").json()["ok"] is True
    assert "browse_click" in client.get("/api/tools").json()["tools"]


def test_gate_stats_endpoint_reports_availability(client) -> None:
    body = client.get("/api/gate/stats").json()
    assert body["ok"] is True
    # Either the gate loaded, or it said so. Both are valid; a 500 is not.
    assert "available" in body or body.get("gate") == "unavailable"


def test_approvals_endpoint_lists_nothing_initially(client) -> None:
    body = client.get("/api/approvals").json()
    assert body["ok"] is True
    assert body["approvals"] == []


def test_answering_an_unknown_approval_is_404(client) -> None:
    response = client.post("/api/approvals/nope", json={"approved": True})
    assert response.status_code == 404


def test_unknown_session_is_rejected(client) -> None:
    """Pre-existing behaviour, pinned so the gate work does not change it.

    orvima's `OrvimaError` handler answers 400 for an unknown session id, not
    404. Asserting 404 here would be asserting a change nobody asked for, so
    this test records the actual contract instead.
    """
    response = client.get("/api/sessions/does-not-exist")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert "does-not-exist" in body["error"]


def test_control_rejects_an_unknown_action(client) -> None:
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    response = client.post(
        f"/api/sessions/{session['id']}/control", json={"action": "explode"}
    )
    assert response.status_code == 422


def test_control_cancel_sets_status(client) -> None:
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    body = client.post(
        f"/api/sessions/{session['id']}/control", json={"action": "cancel"}
    ).json()
    assert body["status"] == "cancelled"


def test_run_goal_dispatches_without_blocking_the_server(client) -> None:
    """Default mode returns as soon as the run is under way.

    A gated run blocks waiting for a human, so the request must not hold the
    connection open - otherwise the very thing the gate is for makes the API
    unreachable at the moment it is needed.
    """
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    response = client.post(f"/api/sessions/{session['id']}/goal", json={"goal": "look around"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["dispatched"] is True


def test_run_goal_wait_returns_the_outcome(client) -> None:
    """Opt-in synchronous mode keeps the original one-call contract working."""
    session = client.post(
        "/api/sessions", json={"mode": "demo", "goal": "products"}
    ).json()["session"]
    response = client.post(
        f"/api/sessions/{session['id']}/goal",
        json={"goal": "list products"},
        params={"wait": True, "timeout": 30},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"], f"wait mode returned no summary: {body}"


def test_run_goal_wait_is_bounded_but_not_triggered_by_fast_runs(client) -> None:
    """A short timeout must not spuriously fail a run that finishes quickly.

    The demo run completes in well under a second, so `timeout=5` comfortably
    returns a real result. This asserts the *bound exists and is honoured* -
    the interesting failure being a request that never returns, which is what an
    unbounded wait on a gated run would look like from the caller's side.
    """
    session = client.post(
        "/api/sessions", json={"mode": "demo", "goal": "products"}
    ).json()["session"]
    response = client.post(
        f"/api/sessions/{session['id']}/goal",
        json={"goal": "list products"},
        params={"wait": True, "timeout": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("timed_out") is not True
    assert body["ok"] is True and body["summary"]


def test_run_goal_rejects_a_nonsensical_timeout(client) -> None:
    """The bound is enforced by validation, not by hope."""
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    for bad in (0, -1, 99999):
        response = client.post(
            f"/api/sessions/{session['id']}/goal",
            json={"goal": "list products"},
            params={"wait": True, "timeout": bad},
        )
        assert response.status_code == 422, f"timeout={bad} was accepted"


def test_result_endpoint_reports_progress(client) -> None:
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    body = client.get(f"/api/sessions/{session['id']}/result").json()
    assert body["ok"] is True
    assert "done" in body


def test_empty_goal_is_rejected(client) -> None:
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    response = client.post(f"/api/sessions/{session['id']}/goal", json={"goal": ""})
    assert response.status_code == 422
