"""Tests for orvima.gate module (gate_* tools)."""

from orvima.gate import gate_classify, gate_describe_action, gate_risk_concepts, GATE_TOOLS


def test_gate_classify_safe():
    result = gate_classify("browse_navigate", {"url": "https://example.com"})
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert "risk" in result


def test_gate_classify_destructive():
    result = gate_classify("browse_click", {"selector": "#delete-account"})
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_gate_describe_action():
    result = gate_describe_action("browse_click", {"selector": "#submit"})
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert "description" in result


def test_gate_risk_concepts_safe():
    result = gate_risk_concepts("navigate to homepage")
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert "is_risky" in result


def test_gate_risk_concepts_risky():
    result = gate_risk_concepts("delete all data permanently")
    assert isinstance(result, dict)
    assert result.get("ok") is True


def test_gate_tools_tuple():
    assert len(GATE_TOOLS) == 3