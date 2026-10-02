"""Live gate test: the real app, the real policy, a real approval round trip.

Everything else mocks something. This drives the actual endpoints and checks
the two things that only show up when the pieces are connected - that a safe run
completes without a human, and that a risky run genuinely blocks and can be
approved through the HTTP API.

The planner is scripted so the test is deterministic; the browser is the demo
one, so no real page is touched.
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("sentinel", reason="sentinel not on path")

from fastapi.testclient import TestClient  # noqa: E402
from test_gate_integration import ScriptedPlanner  # noqa: E402

from orvima import api  # noqa: E402
from orvima.agent import AgentLoop  # noqa: E402
from orvima.sentinel_gate import make_gate  # noqa: E402


@pytest.fixture
def gate():
    """A real policy, classifier off (the deterministic layer is the gate)."""
    return make_gate(classifier_mode="off")


@pytest.fixture
def client(gate, monkeypatch):
    monkeypatch.setattr(api, "get_gate", lambda rebuild=False: gate)
    return TestClient(api.create_app())


def wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_gate_reports_itself_available(client, gate) -> None:
    body = client.get("/api/gate/stats").json()
    assert body["available"] is True
    assert body["mode"] == "off"


def test_safe_run_completes_with_no_human_involved(client, gate) -> None:
    """The promise of the whole thing: routine work stops being interrupted."""
    session = client.post(
        "/api/sessions", json={"mode": "demo", "goal": "products"}
    ).json()["session"]
    sid = session["id"]

    loop = AgentLoop(
        api.store.get(sid),
        planner=ScriptedPlanner([{"tool": "browse_navigate", "args": {"url": "https://acme.dev"}}]),
        gate=gate,
    )
    api.store.get(sid)._loop = loop

    import threading

    threading.Thread(target=lambda: loop.run("read the page"), daemon=True).start()

    assert wait_until(lambda: api.store.get(sid).status in ("done", "error"))
    assert client.get("/api/approvals").json()["approvals"] == []
    assert gate.snapshot_stats()["auto_approved"] >= 1
    assert gate.snapshot_stats()["prompted"] == 0


def test_risky_run_blocks_and_can_be_approved_over_http(client, gate) -> None:
    """A purchase-shaped click must stop until a human says yes, over HTTP."""
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    sid = session["id"]

    loop = AgentLoop(
        api.store.get(sid),
        planner=ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Delete account"}}]),
        gate=gate,
    )
    api.store.get(sid)._loop = loop

    import threading

    threading.Thread(target=lambda: loop.run("delete it"), daemon=True).start()

    assert wait_until(lambda: client.get("/api/approvals").json()["approvals"]), "no approval was queued"
    queued = client.get("/api/approvals").json()["approvals"]
    request = queued[0]
    assert request["tool"] == "browse_click"
    assert request["risk"] in ("outward", "destructive")
    assert request["reason"]

    response = client.post(f"/api/approvals/{request['id']}", json={"approved": True})
    assert response.status_code == 200
    assert response.json()["approved"] is True

    assert wait_until(lambda: api.store.get(sid).status in ("done", "error", "denied"))
    assert client.get("/api/approvals").json()["approvals"] == []


def test_denial_over_http_is_recorded(client, gate) -> None:
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    sid = session["id"]
    loop = AgentLoop(
        api.store.get(sid),
        planner=ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Delete account"}}]),
        gate=gate,
    )
    api.store.get(sid)._loop = loop

    import threading

    threading.Thread(target=lambda: loop.run("delete it"), daemon=True).start()
    assert wait_until(lambda: client.get("/api/approvals").json()["approvals"])
    request = client.get("/api/approvals").json()["approvals"][0]
    client.post(f"/api/approvals/{request['id']}", json={"approved": False, "note": "not today"})

    assert wait_until(lambda: api.store.get(sid).status in ("denied", "done", "error"))
    assert gate.snapshot_stats()["denied"] == 1

    kinds = [r["kind"] for r in api.store.get(sid).transcript]
    assert "approval_note" in kinds, "the human's note was not recorded"


def test_a_real_safeguard_holds_end_to_end(client, gate) -> None:
    """`browse_eval` is arbitrary JS; nothing about it should auto-run.

    Uses the fixture's gate, which the fixture also patches into `get_gate`, so
    the queue being polled is the one the loop writes to. A test that built its
    own gate here would poll a queue nobody writes to - which is exactly what
    the first version of this test did, and why it failed.
    """
    session = client.post("/api/sessions", json={"mode": "demo"}).json()["session"]
    sid = session["id"]
    loop = AgentLoop(
        api.store.get(sid),
        planner=ScriptedPlanner(
            [{"tool": "browse_eval", "args": {"expression": "document.cookie"}}]
        ),
        gate=gate,
    )
    api.store.get(sid)._loop = loop

    import threading

    threading.Thread(target=lambda: loop.run("exfiltrate"), daemon=True).start()
    assert wait_until(lambda: client.get("/api/approvals").json()["approvals"]), (
        "browse_eval was not gated"
    )
