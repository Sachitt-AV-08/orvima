"""Pins the invariants in trace.py. Each test names the rule it protects.

Run:  python -m pytest tests/test_trace.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orvima import trace as T


def _writer(tmp: Path) -> T.TraceWriter:
    return T.TraceWriter(tmp)


def _gate(decision: str, *levels: str) -> dict:
    return {
        "decision": decision,
        "signals": [
            {"signal": f"s{i}", "kind": "deterministic", "level": lv, "why": "x"}
            for i, lv in enumerate(levels)
        ],
    }


def _run(w: T.TraceWriter, *, decision="allow", effect="none", approve=False) -> None:
    w.emit("run.start", {"goal": "g", "mode": "freeform", "versions": {}, "policy_hash": "p"})
    w.emit("step.proposed", {"tool": "browse_click", "args": {}, "source": "client"}, span="s1")
    w.emit("gate.decision", _gate(decision, decision), span="s1")
    if approve:
        w.emit("approval.requested",
               {"risk": "payment", "reason": "r", "page_url": "u", "ttl_s": 120}, span="s1")
        w.emit("approval.resolved", {"outcome": "approved", "latency_ms": 5}, span="s1")
    w.emit("effect.observed",
           {"effect_class": effect, "capture_ok": effect != "unknown",
            "requests": [], "filtered": []}, span="s1")
    w.emit("step.result", {"ok": True, "verified": True}, span="s1")
    w.emit("run.end", {"outcome": "done"})


def test_unknown_keys_and_types_are_errors(tmp_path):
    w = _writer(tmp_path)
    with pytest.raises(ValueError):
        w.emit("step.result", {"ok": True, "verified": True, "verifed_typo": 1}, span="s")
    with pytest.raises(ValueError):
        w.emit("made.up", {}, span="s")
    with pytest.raises(ValueError):
        w.emit("step.result", {"ok": True}, span="s")  # missing 'verified'
    assert not w.path.exists() or w.path.read_text() == ""  # nothing half-written


def test_gate_decision_can_never_be_lower_than_its_strongest_signal(tmp_path):
    w = _writer(tmp_path)
    with pytest.raises(ValueError, match="lower than"):
        w.emit("gate.decision", _gate("allow", "allow", "needs_human"), span="s")
    w.emit("gate.decision", _gate("refuse", "allow", "needs_human"), span="s")  # raising is fine


def test_failed_capture_cannot_claim_no_effect(tmp_path):
    w = _writer(tmp_path)
    with pytest.raises(ValueError, match="unknown"):
        w.emit("effect.observed",
               {"effect_class": "none", "capture_ok": False, "requests": [], "filtered": []},
               span="s")


def test_refusal_needs_a_machine_readable_reason(tmp_path):
    w = _writer(tmp_path)
    with pytest.raises(ValueError):
        w.emit("route.decision", {"route": "refused"})
    w.emit("route.decision", {"route": "refused", "refusal": "no_match"})


def test_chain_detects_edit_gap_and_reorder(tmp_path):
    w = _writer(tmp_path)
    _run(w)
    events = T.read_trace(w.path)
    assert T.verify_chain(events) == []

    edited = json.loads(json.dumps(events))
    edited[2]["data"]["decision"] = "refuse"  # tamper with an existing key (gate.decision)
    assert any("hash mismatch" in p for p in T.verify_chain(edited))

    gap = events[:2] + events[3:]
    assert any("gap" in p or "prev hash" in p for p in T.verify_chain(gap))

    swapped = events[:]
    swapped[1], swapped[2] = swapped[2], swapped[1]
    assert T.verify_chain(swapped)


def test_effect_ignores_beacons_but_reports_that_it_did(tmp_path):
    eff = T.classify_effect(
        [{"method": "POST", "url": "https://stats.example.com/c?id=1", "resource_type": "ping"},
         {"method": "POST", "url": "https://metrics.cdn.example/e", "resource_type": "fetch"},
         {"method": "GET", "url": "https://shop.test/cart", "resource_type": "document"}],
        "https://shop.test/cart", "https://shop.test/cart",
        beacon_hosts=["metrics.cdn.example"],
    )
    assert eff["effect_class"] == "read"
    assert {f["why"] for f in eff["filtered"]} == {"beacon", "allowlisted_host"}
    assert "?id" not in json.dumps(eff)  # query strings never reach the log


def test_post_is_a_mutation_and_failed_capture_is_unknown_not_none():
    post = T.classify_effect(
        [{"method": "post", "url": "https://shop.test/order", "resource_type": "fetch"}],
        "https://shop.test/pay", "https://shop.test/pay")
    assert post["effect_class"] == "mutation"
    lost = T.classify_effect([], "https://a.test/", "https://a.test/", capture_ok=False)
    assert lost["effect_class"] == "unknown"


def test_get_that_looks_like_a_side_effect_is_flagged_not_waved_through():
    eff = T.classify_effect(
        [{"method": "GET", "url": "https://a.test/account/logout", "resource_type": "document"}],
        "https://a.test/account", "https://a.test/")
    assert eff["effect_class"] == "possible_mutation"


def test_navigation_and_none():
    nav = T.classify_effect([], "https://a.test/x", "https://a.test/y")
    assert nav["effect_class"] == "navigation"
    assert T.classify_effect([], "https://a.test/x", "https://a.test/x")["effect_class"] == "none"


def test_typed_values_are_never_logged_but_recipe_variables_keep_their_name():
    red = T.redact_args("browse_fill", {"selector": "#cc", "text": "4242424242424242"})
    assert "4242" not in json.dumps(red) and red["text"] == {"redacted": True, "len": 16}
    assert T.redact_args("browse_fill", {"selector": "#e", "text": "{email}"})["text"] == "{email}"
    assert T.redact_args("browse_navigate", {"url": "https://a.test/p?token=abc#x"})["url"] \
        == "https://a.test/p?..."


def test_audit_counts_interruptions_and_flags_ungated_mutation(tmp_path):
    w = _writer(tmp_path)
    _run(w, decision="needs_human", effect="mutation", approve=True)
    a = T.audit(T.read_trace(w.path))
    assert a["prompts"] == 1 and a["ungated_effects"] == [] and a["ordering_violations"] == []

    w2 = _writer(tmp_path)
    _run(w2, decision="allow", effect="mutation")  # a POST went out under 'allow'
    a2 = T.audit(T.read_trace(w2.path))
    assert a2["ungated_effects"] == ["s1"]


def test_audit_catches_acting_without_a_gate_decision_or_approval(tmp_path):
    w = _writer(tmp_path)
    w.emit("step.result", {"ok": True, "verified": True}, span="s9")
    a = T.audit(T.read_trace(w.path))
    assert any("no prior gate.decision" in v for v in a["ordering_violations"])

    w2 = _writer(tmp_path)
    w2.emit("gate.decision", _gate("needs_human", "needs_human"), span="s2")
    w2.emit("step.result", {"ok": True, "verified": True}, span="s2")  # ran unapproved
    a2 = T.audit(T.read_trace(w2.path))
    assert any("no approval preceded" in v for v in a2["ordering_violations"])


def test_llm_usage_sums_so_replay_tokens_can_be_asserted_zero(tmp_path):
    w = _writer(tmp_path)
    w.emit("llm.usage", {"calls": 3, "input_tokens": 900, "output_tokens": 120})
    a = T.audit(T.read_trace(w.path))
    assert (a["llm_calls"], a["llm_input_tokens"], a["llm_output_tokens"]) == (3, 900, 120)
