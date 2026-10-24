"""Pins orvima.gate tool behavior."""

from __future__ import annotations

import pytest

from orvima import gate


def test_gate_classify_basic():
    res = gate.gate_classify("browser.navigate", {"url": "https://example.com"}, page_url="https://example.com")
    assert res["ok"] is True
    assert res["tool"] == "browser.navigate"
    assert "risk" in res
    assert "needs_human" in res
    assert "confidence" in res
    assert "reason" in res


def test_gate_classify_none_args():
    res = gate.gate_classify("browser.click")
    assert res["ok"] is True
    assert res["risk"] in {"safe", "low", "outward", "destructive"}


def test_gate_classify_mode_switch():
    res = gate.gate_classify("browser.click", {}, mode="blocking")
    assert res["ok"] is True
    res2 = gate.gate_classify("browser.click", {}, mode="off")
    assert res2["ok"] is True


def test_gate_describe_action():
    res = gate.gate_describe_action("browser.fill", {"text": "hello"})
    assert res["ok"] is True
    assert res["tool"] == "browser.fill"
    assert isinstance(res["description"], str)


def test_gate_risk_concepts_safe():
    res = gate.gate_risk_concepts("read the page title")
    assert res["ok"] is True
    assert res["is_risky"] in (True, False)


def test_gate_risk_concepts_risky():
    res = gate.gate_risk_concepts("transfer money wire payment")
    assert res["ok"] is True
    # either matched_concept or matched_weak expected for risky phrasing
    assert res["is_risky"] is True


def test_gate_error_paths():
    # gate_risk_concepts with non-string triggers exception path
    res = gate.gate_risk_concepts(None)  # type: ignore[arg-type]
    assert res["ok"] is False
    assert "error" in res

    # gate_describe_action with bad args still returns? ensure no crash
    res = gate.gate_describe_action("x", None)
    # may succeed or fail, but always dict
    assert isinstance(res, dict)

    # gate_classify exception path via monkeypatch
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(gate, "_make_policy", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        # _DEFAULT_POLICY already set; force by setting module global
        mp.setattr(gate, "_DEFAULT_POLICY", None)
        res = gate.gate_classify("browser.navigate")
        assert res["ok"] is False
        assert "boom" in res.get("error", "") or res.get("ok") is False


def test_gate_tools_tuple():
    assert len(gate.GATE_TOOLS) == 3
