"""Tests for orvima.saas_api module."""

from orvima.saas_api import (
    DeployRequest,
    DeployResponse,
    DeployedSession,
    health,
    list_sessions,
    BASE_PORT,
    MAX_SESSIONS,
    SESSION_TTL_MINUTES,
)


def test_deploy_request_model():
    req = DeployRequest(start_url="https://example.com")
    assert req.start_url == "https://example.com"


def test_deployed_session_defaults():
    sess = DeployedSession(id="test", port=8302, pid=1234, created=0.0, expires=100.0, cdp_url="http://x", ws_url="ws://x", status="running")
    assert sess.id == "test"
    assert sess.port == 8302


def test_health():
    result = health()
    assert isinstance(result, dict)


def test_list_sessions():
    result = list_sessions()
    assert isinstance(result, (list, dict))


def test_constants():
    assert isinstance(BASE_PORT, int)
    assert isinstance(MAX_SESSIONS, int)
    assert isinstance(SESSION_TTL_MINUTES, int)
    assert MAX_SESSIONS > 0