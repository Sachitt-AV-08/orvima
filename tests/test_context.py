"""Tests for orvima.context module."""

from orvima.context import _clip, compact_row, full_row, render_transcript, measure, ContextBudget


def test_clip_short():
    result = _clip("hello", 10)
    assert result == ("hello", False)


def test_clip_long():
    text, clipped = _clip("a" * 20, 10)
    assert clipped is True
    assert len(text) <= 10


def test_compact_row():
    cb = ContextBudget()
    result = compact_row({"url": "https://example.com", "title": "Example"}, cb)
    assert isinstance(result, str)


def test_full_row():
    cb = ContextBudget()
    result = full_row({"url": "https://example.com", "title": "Example"}, cb)
    assert isinstance(result, str)


def test_render_transcript_empty():
    result = render_transcript([])
    assert isinstance(result, str)


def test_render_transcript_with_history():
    history = [{"kind": "tool", "tool": "browse_navigate", "args": {"url": "https://example.com"}, "result": {"ok": True}}]
    result = render_transcript(history)
    assert isinstance(result, str)


def test_context_budget():
    cb = ContextBudget()
    assert cb is not None


def test_measure():
    result = measure("some text")
    assert isinstance(result, (int, float, dict))