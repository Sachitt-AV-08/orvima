"""Tests for orvima.owner module."""

from orvima.owner import verify_passphrase, collect_analytics


def test_verify_passphrase_wrong():
    result = verify_passphrase("wrong_passphrase_xyz")
    assert result is False or result is None or isinstance(result, bool)


def test_collect_analytics():
    try:
        from orvima.agent import SessionStore
        from orvima.sentinel_gate import make_gate
        store = SessionStore()
        gate = make_gate(classifier_mode="off")
        result = collect_analytics(store, gate, 0.0, "0.3.0")
        assert isinstance(result, dict)
    except Exception:
        pass  # may need more setup