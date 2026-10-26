"""Tests for orvima.sentinel_gate module."""

from orvima.sentinel_gate import make_gate, GateResult


def test_make_gate_off():
    gate = make_gate(classifier_mode="off")
    assert gate is not None
    assert gate.available is True or gate.available is False


def test_gate_check_safe():
    gate = make_gate(classifier_mode="off")
    result = gate.check("browse_navigate", {"url": "https://example.com"}, session_id="test")
    assert isinstance(result, GateResult)
    assert result.allowed is True
    assert result.probability >= 0.0


def test_gate_check_destructive():
    gate = make_gate(classifier_mode="off")
    result = gate.check("browse_click", {"selector": "#delete"}, session_id="test")
    assert isinstance(result, GateResult)


def test_gate_result_as_log():
    gr = GateResult(allowed=True, risk="safe", reason="ok", probability=0.9)
    log = gr.as_log()
    assert isinstance(log, dict)
    assert "probability" in log
    assert log["probability"] == 0.9


def test_gate_result_defaults():
    gr = GateResult(allowed=False)
    assert gr.probability == 0.0
    assert gr.risk == "unknown"


def test_make_gate_advisory():
    gate = make_gate(classifier_mode="advisory")
    assert gate is not None