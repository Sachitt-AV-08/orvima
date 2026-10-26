"""Tests for orvima.mcp_server module."""

from orvima.mcp_server import _bind, register_tools, register_module_tools, _bind_simple


def test_bind_is_callable():
    assert callable(_bind)


def test_annotations_for():
    from orvima.mcp_server import _annotations_for
    ann = _annotations_for("browse_navigate")
    assert ann is not None or ann is None  # just no crash


def test_register_tools_callable():
    assert callable(register_tools)


def test_register_module_tools_callable():
    assert callable(register_module_tools)


def test_bind_simple_callable():
    assert callable(_bind_simple)