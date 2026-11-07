"""Tests for orvima.tools module."""

from orvima.tools import TOOL_NAMES, TOOLS, _clamp, _truncate_text, call_tool


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


def test_call_tool_unknown_raises_tool_not_found():
    from orvima.errors import ToolNotFoundError

    try:
        call_tool(None, "nonexistent_tool_xyz", {})
    except ToolNotFoundError:
        return
    raise AssertionError("unknown tools must raise ToolNotFoundError")


def test_call_tool_does_not_swallow_browser_errors():
    from orvima import demo

    browser = demo.DemoBrowser()
    try:
        call_tool(browser, "does_not_exist", {})
    except Exception as exc:
        assert "nonexistent" in str(exc).lower() or "unknown" in str(exc).lower()
        return
    raise AssertionError("unhandled unknown tool should raise")


def test_clamp_boundaries():
    assert _clamp(None, 1, 5, 3) == 3
    assert _clamp("garbage", 1, 5, 3) == 3
    assert _clamp("-3", 1, 5, 3) == 0
    assert _clamp("99", 1, 5, 3) == 5
    assert _clamp("0", 0, 10, 99) == 0
    assert _clamp(10, 0, 10, 99) == 10


def test_truncate_text_returns_total():
    text, total, clipped = _truncate_text("abcdef", 3)
    assert text == "abc"
    assert total == 6
    assert clipped is True
    text, total, clipped = _truncate_text("a" * 200, 50)
    assert clipped is True
    assert len(text) == 50
    assert total == 200
    text, total, clipped = _truncate_text(None, 50)
    assert (text, total, clipped) == ("", 0, False)
    text, total, clipped = _truncate_text("abc", 0)
    assert text == ""
    assert total == 3
    assert clipped is True
