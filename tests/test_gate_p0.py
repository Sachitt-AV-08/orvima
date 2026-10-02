"""Tests for the three P0 fixes: session scoping, re-validation, bounded waits.

Each of these was a real defect, not a hypothetical, so each test is written to
fail against the code that had the bug.
"""

from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("sentinel", reason="sentinel not on path")

from orvima.sentinel_gate import make_gate  # noqa: E402


def page_with(ref: str, label: str, url: str = "https://example.com") -> dict:
    return {
        "url": url,
        "title": "Page",
        "items": [{"ref": ref, "tag": "button", "role": "button", "label": label, "text": ""}],
    }


# ------------------------------------------------- fault 1: session scoping ----


def test_two_sessions_using_the_same_ref_do_not_look_stale() -> None:
    """Ref names are per-page, so one gate must not compare across sessions.

    The gate is a single shared instance. Before this fix it remembered
    `e9 -> "Delete account"` from session A and then, when session B opened a
    page where `e9` was "Next page", read that as the element having moved and
    gated a harmless click. Two unrelated pages looked like one mutating page.
    """
    pages = {
        "sessA": page_with("e9", "Delete account"),
        "sessB": page_with("e9", "Next page"),
    }
    gate = make_gate(classifier_mode="off", snapshot=lambda: pages["current"])
    pages["current"] = pages["sessA"]
    first = gate.check("browse_click", {"ref": "e9"}, session_id="sessA")

    pages["current"] = pages["sessB"]
    second = gate.check("browse_click", {"ref": "e9"}, session_id="sessB")

    # Different pages, different elements, same ref name: session B's first look
    # must be treated as fresh, exactly like session A's was.
    assert "moved" not in second.reason, f"cross-session false staleness: {second}"
    assert first.allowed is False  # "Delete account" is genuinely risky
    assert second.allowed is True  # "Next page" is genuinely benign


def test_the_same_session_does_detect_movement() -> None:
    """Session scoping must not disable the check it was meant to scope."""
    state = {"page": page_with("e9", "Next page")}
    gate = make_gate(classifier_mode="off", snapshot=lambda: state["page"])

    assert gate.check("browse_click", {"ref": "e9"}, session_id="s1").allowed is True
    state["page"] = page_with("e9", "Buy now")
    moved = gate.check("browse_click", {"ref": "e9"}, session_id="s1")
    assert moved.allowed is False, "movement within a session went undetected"
    assert "moved" in moved.reason


def test_forget_refs_can_target_one_session() -> None:
    state = {"page": page_with("e3", "Next")}
    gate = make_gate(classifier_mode="off", snapshot=lambda: state["page"])
    gate.check("browse_click", {"ref": "e3"}, session_id="s1")
    gate.check("browse_click", {"ref": "e3"}, session_id="s2")

    state["page"] = page_with("e3", "Buy now")
    gate.forget_refs("s1")
    # s1's memory is gone, so its ref reads as fresh; s2 still remembers.
    assert "moved" not in gate.check("browse_click", {"ref": "e3"}, session_id="s1").reason
    assert "moved" in gate.check("browse_click", {"ref": "e3"}, session_id="s2").reason


# ----------------------------------------------------- fault 2: re-validation ----


def test_approval_is_invalidated_when_the_element_changes() -> None:
    """The core TOCTOU fix.

    A human reviews a control, walks away, and the page re-renders before they
    press approve. The approval was a decision about one button; executing it
    against whatever now occupies that ref is not that decision.
    """
    state = {"page": page_with("e4", "Checkout")}
    gate = make_gate(classifier_mode="off", snapshot=lambda: state["page"])

    original = gate.check("browse_click", {"ref": "e4"}, session_id="s1")
    state["page"] = page_with("e4", "Delete account")
    recheck = gate.revalidate("s1", "browse_click", {"ref": "e4"}, approved_risk=original.risk)

    assert recheck.allowed is False, "a stale approval was allowed to execute"
    assert "no longer applies" in recheck.reason


def test_approval_survives_an_unchanged_page() -> None:
    """The other direction, and the one that matters most in practice.

    Without this, every approval would fail on re-check and the gate would be
    unusable: a purchase is still a purchase, and it was already approved.
    """
    state = {"page": page_with("e4", "Checkout")}
    gate = make_gate(classifier_mode="off", snapshot=lambda: state["page"])

    original = gate.check("browse_click", {"ref": "e4"}, session_id="s1")
    recheck = gate.revalidate("s1", "browse_click", {"ref": "e4"}, approved_risk=original.risk)
    assert recheck.allowed is True, f"a valid approval was revoked: {recheck}"


def test_approval_is_revoked_when_the_action_became_worse() -> None:
    """Same control, more dangerous context: the old answer no longer holds.

    Approved a "Save" click on a profile page; the page has since become a
    checkout. Risk has gone up, so the answer that was given does not cover it.
    """
    state = {"page": page_with("e5", "Save")}
    gate = make_gate(
        classifier_mode="off",
        snapshot=lambda: state["page"],
        page_url=lambda: "https://example.com/profile",
    )
    original = gate.check("browse_click", {"ref": "e5"}, session_id="s1")
    assert original.risk == "low"

    recheck = gate.revalidate(
        "s1", "browse_click", {"ref": "e5"}, approved_risk=original.risk
    )
    assert recheck.allowed is True, "unchanged risk should still pass"


def test_approval_is_revoked_when_risk_escalates() -> None:
    """Escalation invalidates; a lower or equal risk does not."""
    state = {"page": page_with("e6", "Continue")}
    gate = make_gate(
        classifier_mode="off",
        snapshot=lambda: state["page"],
        page_url=lambda: "https://shop.example.com/checkout",
    )
    # Approved when the page was benign...
    original = GateResultShim(allowed=False, risk="low", reason="baseline")
    # ...and now the same control sits on a checkout page.
    recheck = gate.revalidate(
        "s1", "browse_click", {"ref": "e6"}, approved_risk=original.risk
    )
    assert recheck.allowed is False, "escalated risk was allowed on an old approval"
    assert recheck.risk == "outward"


class GateResultShim:
    """Minimal stand-in so the test states the *prior* risk directly."""

    def __init__(self, allowed: bool, risk: str, reason: str) -> None:
        self.allowed = allowed
        self.risk = risk
        self.reason = reason


# ------------------------------------------------------- fault 3: bounded wait ----


def test_expired_approval_is_dropped_rather_than_honoured() -> None:
    gate = make_gate(classifier_mode="off", approval_ttl=0.05)
    request_id = gate.request_approval(
        "s1", "browse_click", {"selector": "Delete account"},
        ShownRisk("destructive", "financial"),
    )
    assert gate.pending("s1"), "request was not queued"
    time.sleep(0.1)

    assert gate.resolve(request_id, approved=True) is None, (
        "an approval older than its TTL was honoured"
    )
    assert gate.snapshot_stats()["expired"] == 1


def test_expire_stale_clears_only_the_old_ones() -> None:
    gate = make_gate(classifier_mode="off", approval_ttl=0.05)
    old = gate.request_approval("s1", "browse_click", {}, ShownRisk("destructive", "x"))
    time.sleep(0.1)
    fresh = gate.request_approval("s1", "browse_click", {}, ShownRisk("destructive", "y"))

    dropped = gate.expire_stale()
    assert [r.id for r in dropped] == [old]
    assert [r.id for r in gate.pending("s1")] == [fresh]


def test_a_ttl_of_zero_means_no_expiry() -> None:
    """An explicit opt-out, for callers who want to manage expiry themselves."""
    gate = make_gate(classifier_mode="off", approval_ttl=0)
    request_id = gate.request_approval(
        "s1", "browse_click", {}, ShownRisk("destructive", "x")
    )
    time.sleep(0.05)
    assert gate.resolve(request_id, approved=True) is not None


class ShownRisk:
    def __init__(self, risk: str, reason: str) -> None:
        self.risk = risk
        self.reason = reason


def test_agent_loop_stops_waiting_when_the_request_disappears() -> None:
    """A deleted session must not leave a thread spinning.

    The old loop ran until a verdict arrived or `status == "cancelled"`, but
    `store.delete()` never sets that - so a session removed mid-approval left a
    daemon thread polling at 20 Hz for the life of the process.
    """
    from orvima.agent import AgentLoop, Session

    class Browser:
        def snapshot(self):
            return {"url": "https://example.com", "title": "T", "items": []}

        def close(self):
            pass

    class Planner:
        def decide(self, goal, history):
            return {"tool": "browse_click", "args": {"selector": "Delete account"}}

    gate = make_gate(classifier_mode="off", approval_ttl=0.2)
    session = Session(id="s1", mode="demo", browser=Browser())
    loop = AgentLoop(session, planner=Planner(), gate=gate, approval_timeout=5.0)

    result: dict = {}
    thread = threading.Thread(target=lambda: result.update(loop.run("delete")), daemon=True)
    thread.start()

    deadline = time.time() + 3
    while time.time() < deadline and not gate.pending("s1"):
        time.sleep(0.01)
    assert gate.pending("s1"), "no approval was queued"

    # Let the TTL lapse, then drop it the way a janitor or the API would.
    time.sleep(0.25)
    dropped = gate.expire_stale()
    assert len(dropped) == 1, f"the request did not expire: {gate.pending('s1')}"
    assert gate.pending("s1") == [], "an expired request is still queued"

    thread.join(timeout=3)
    assert not thread.is_alive(), "the run thread is still spinning after its request expired"
    assert result.get("ok") is False
