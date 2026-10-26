"""Tests for orvima.api module."""

from orvima.api import create_app, app, configured_token, token_ok, gate_status


def test_create_app():
    app = create_app()
    assert app is not None


def test_app_instance():
    assert app is not None


def test_configured_token():
    result = configured_token()
    assert result is None or isinstance(result, str)


def test_token_ok():
    result = token_ok("test-token")
    assert isinstance(result, bool)


def test_gate_status():
    result = gate_status()
    assert isinstance(result, str)