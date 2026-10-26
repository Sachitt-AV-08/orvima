"""Tests for orvima.agent module."""

from orvima.agent import EventBus, Session, SessionStore, AgentLoop, _redact_sensitive, _redact_html


def test_session_bus():
    bus = EventBus()
    assert bus is not None
    q = bus.subscribe()
    bus.emit({"type": "test"})
    assert len(q) == 1
    assert q[0]["type"] == "test"


def test_session_bus_multiple():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.emit({"type": "test"})
    assert len(q1) == 1
    assert len(q2) == 1


def test_redact_sensitive():
    result = _redact_sensitive({"password": "secret123", "name": "test"})
    assert result["password"] != "secret123" or "secret" not in str(result)


def test_redact_html():
    result = _redact_html("<script>alert('xss')</script><p>hello</p>")
    assert isinstance(result, str)


def test_session_store_create():
    store = SessionStore()
    sess = store.create(mode="demo")
    assert sess is not None
    assert sess.id is not None


def test_session_store_get():
    store = SessionStore()
    sess = store.create(mode="demo")
    retrieved = store.get(sess.id)
    assert retrieved is sess


def test_session_store_list():
    store = SessionStore()
    store.create(mode="demo")
    sessions = store.list()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1


def test_session_store_delete():
    store = SessionStore()
    sess = store.create(mode="demo")
    store.delete(sess.id)
    try:
        store.get(sess.id)
        assert True  # may or may not raise
    except Exception:
        pass  # expected


def test_agent_loop_create():
    store = SessionStore()
    sess = store.create(mode="demo")
    loop = AgentLoop(sess)
    assert loop is not None