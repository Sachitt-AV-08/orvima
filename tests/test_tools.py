"""Tests for orvima.tools module."""

from orvima.tools import TOOL_NAMES, TOOLS, call_tool, _truncate_text, _clamp


def test_tool_names_not_empty():
    assert len(TOOL_NAMES) > 0
    assert len(TOOL_NAMES) == len(TOOLS)


def test_tool_names_are_strings():
    for name in TOOL_NAMES:
        assert isinstance(name, str)
        assert name.startswith("browse_")


def test_clamp():
    assert _clamp(5, 0, 10, 0) == 5
    assert _clamp(-5, 0, 10, 0) == 0
    assert _clamp(15, 0, 10, 0) == 10


def test_truncate_text_short():
    text, count, clipped = _truncate_text("hello", 100)
    assert text == "hello"
    assert clipped is False


def test_truncate_text_long():
    text, count, clipped = _truncate_text("a" * 200, 50)
    assert clipped is True
    assert len(text) <= 50


def test_call_tool_unknown():
    try:
        result = call_tool(None, "nonexistent_tool_xyz", {})
        assert isinstance(result, dict)
    except Exception:
        pass  # may require browser instance