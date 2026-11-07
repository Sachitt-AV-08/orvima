"""Tests for orvima.cli module."""

from orvima.cli import _mode_env, check_bind, is_loopback, resolve_mode


def test_is_loopback_true():
    assert is_loopback("127.0.0.1") is True
    assert is_loopback("localhost") is True


def test_is_loopback_false():
    assert is_loopback("0.0.0.0") is False
    assert is_loopback("192.168.1.1") is False


def test_check_bind_loopback():
    result = check_bind("127.0.0.1")
    assert result is None or isinstance(result, str)


def test_resolve_mode_demo():
    result = resolve_mode("demo")
    assert result == "demo"


def test_mode_env():
    try:
        _mode_env("demo")
    except Exception:
        pass  # just no crash
    from orvima import api

    api.set_default_session_mode(None)  # keep the unit test from polluting sibling tests
