"""End-to-end tests for the gated agent loop.

The unit tests cover the gate in isolation. These cover the part that actually
matters in production: that a run *proceeds* on safe actions, *blocks* on risky
ones, and *stops cleanly* when refused - and that a broken gate never turns into
an unattended purchase.
"""

from __future__ import annotations

import threading
import time

import pytest

from orvima.agent import AgentLoop, Session

pytest.importorskip("sentinel", reason="sentinel not on path")

from orvima.sentinel_gate import SentinelGate, make_gate  # noqa: E402


class FakeBrowser:
    """Just enough browser for the loop. Records what ran."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._snapshot = {"url": "https://example.com", "title": "Example", "items": []}

    def navigate(self, url: str) -> dict:
        self._snapshot["url"] = url
        return {"url": url, "title": "Example"}

    def snapshot(self) -> dict:
        return dict(self._snapshot)

    def click(self, selector: str) -> dict:
        self.calls.append(("click", {"selector": selector}))
        return {"ok": True, "verified": True}

    def screenshot(self) -> dict:
        return {"png_b64": ""}

    def close(self) -> None:
        pass


class ScriptedPlanner:
    """Replays a fixed list of decisions, then reports done."""

    def __init__(self, script: list[dict]) -> None:
        self.script = list(script)
        self.index = 0

    def decide(self, goal: str, history: list[dict]) -> dict:
        if self.index >= len(self.script):
            return {"done": True, "summary": "script exhausted"}
        decision = self.script[self.index]
        self.index += 1
        return decision


def make_session() -> Session:
    return Session(id="s1", mode="demo", browser=FakeBrowser())


def run_async(loop: AgentLoop, goal: str) -> tuple[dict, threading.Thread]:
    """Run the loop on a thread so a blocked approval can be answered."""
    result: dict = {}
    thread = threading.Thread(target=lambda: result.update(loop.run(goal)), daemon=True)
    thread.start()
    return result, thread


def wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ------------------------------------------------------- ungated behaviour ----


def test_without_a_gate_every_step_still_runs() -> None:
    """The gate is optional; absence must not change the loop's behaviour."""
    session = make_session()
    planner = ScriptedPlanner([{"tool": "browse_navigate", "args": {"url": "https://example.com"}}])
    loop = AgentLoop(session, planner=planner)
    result = loop.run("do a thing")
    assert result["ok"] is True


# ------------------------------------------------------------- safe actions ----


def test_safe_actions_run_without_asking() -> None:
    session = make_session()
    gate = make_gate(classifier_mode="off")
    planner = ScriptedPlanner([{"tool": "browse_navigate", "args": {"url": "https://example.com"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "read the page")
    thread.join(timeout=5)
    assert result.get("ok") is True, f"safe run did not complete: {result}"
    assert gate.snapshot_stats()["prompted"] == 0, "a read-only action asked a human"


# ------------------------------------------------------------ risky actions ----


def test_risky_action_blocks_until_approved() -> None:
    session = make_session()
    gate = make_gate(classifier_mode="off")
    planner = ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Delete account"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "delete the account")

    assert wait_for(lambda: gate.pending("s1")), "no approval was requested"
    request = gate.pending("s1")[0]
    assert request.risk in ("outward", "destructive")
    assert thread.is_alive(), "the run proceeded without approval"

    loop.resolve_approval(request.id, approved=True)
    thread.join(timeout=5)
    assert result.get("ok") is True


def test_denied_action_ends_the_run_cleanly() -> None:
    """A refusal is a complete answer, not a crash.

    The loop returns a structured `denied` result rather than raising, because
    "I will not do that" is a legitimate outcome and the caller should be able
    to show it to a user.
    """
    session = make_session()
    gate = make_gate(classifier_mode="off")
    planner = ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Delete account"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "delete the account")
    assert wait_for(lambda: gate.pending("s1"))
    loop.resolve_approval(gate.pending("s1")[0].id, approved=False)
    thread.join(timeout=5)

    assert result.get("denied") is True
    assert result.get("ok") is False
    assert "not approved" in result.get("summary", "")
    assert session.browser.calls == [], "a denied action was executed anyway"


def test_broken_gate_does_not_execute_the_action() -> None:
    """The single most important property in this file.

    A gate that has lost its classifier must block, never wave through. If this
    ever passes with `executed == True`, a purchase can happen with nobody
    watching.
    """

    class ExplodingPolicy:
        def evaluate(self, *a, **kw):
            raise RuntimeError("model backend is gone")

    session = make_session()
    gate = SentinelGate(ExplodingPolicy())
    planner = ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Buy now"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "buy it")
    assert wait_for(lambda: gate.pending("s1")), "a broken gate let the action through"
    loop.resolve_approval(gate.pending("s1")[0].id, approved=False)
    thread.join(timeout=5)
    assert session.browser.calls == []


def test_gate_with_no_policy_blocks_everything() -> None:
    session = make_session()
    gate = SentinelGate(policy=None)
    planner = ScriptedPlanner([{"tool": "browse_navigate", "args": {"url": "https://example.com"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "read a page")
    assert wait_for(lambda: gate.pending("s1")), "a policy-less gate allowed a read"
    loop.resolve_approval(gate.pending("s1")[0].id, approved=True)
    thread.join(timeout=5)


# ---------------------------------------------------------------- audit trail ----


def test_every_decision_is_logged_with_its_reason() -> None:
    """A gate nobody can audit is a gate nobody can trust."""
    session = make_session()
    gate = make_gate(classifier_mode="off")
    planner = ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Place your order"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "order it")
    assert wait_for(lambda: gate.pending("s1"))
    loop.resolve_approval(gate.pending("s1")[0].id, approved=True)
    thread.join(timeout=5)

    kinds = [row["kind"] for row in session.transcript]
    assert "gate" in kinds, "the gate verdict was not logged"
    assert "approval_requested" in kinds
    assert "approval_resolved" in kinds

    gate_row = next(r for r in session.transcript if r["kind"] == "gate")
    assert gate_row["reason"], "a logged decision with no reason"
    assert "risk" in gate_row


def test_approval_request_carries_what_a_human_needs() -> None:
    """The dialog must say what is being clicked, or approval is a coin flip."""
    session = make_session()
    gate = make_gate(classifier_mode="off")
    planner = ScriptedPlanner([{"tool": "browse_click", "args": {"selector": "Delete account"}}])
    loop = AgentLoop(session, planner=planner, gate=gate)

    result, thread = run_async(loop, "delete")
    assert wait_for(lambda: gate.pending("s1"))
    request = gate.pending("s1")[0]
    assert request.tool == "browse_click"
    assert request.detail["page_title"] == "Example"
    loop.resolve_approval(request.id, approved=False)
    thread.join(timeout=5)


# ------------------------------------------------------------------- repeats ----


def test_repeating_the_same_safe_run_asks_nothing_each_time() -> None:
    """The whole point: routine work stops being interrupted."""
    gate = make_gate(classifier_mode="off")
    script = [{"tool": "browse_navigate", "args": {"url": "https://example.com"}}]

    # A fresh session and planner per run: replaying one AgentLoop would exhaust
    # the planner's script on the first pass and make later runs no-ops, so the
    # gate would only ever be consulted once.
    for _ in range(5):
        loop = AgentLoop(make_session(), planner=ScriptedPlanner(script), gate=gate)
        result, thread = run_async(loop, "read")
        thread.join(timeout=5)
        assert result.get("ok") is True

    stats = gate.snapshot_stats()
    assert stats["prompted"] == 0
    assert stats["auto_approved"] == 5, f"expected 5 auto-approvals, got {stats}"


def test_resolving_an_unknown_request_is_harmless() -> None:
    session = make_session()
    loop = AgentLoop(session, planner=ScriptedPlanner([]))
    loop.resolve_approval("does-not-exist", approved=True)
    assert loop.resolve_approval("does-not-exist", approved=False) is True
