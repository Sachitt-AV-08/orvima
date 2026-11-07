"""Unit tests for orvima.tool_annotations module."""

from orvima.tool_annotations import all_names, for_tool


def test_for_tool_known():
    ann = for_tool("browse_navigate")
    assert ann is not None


def test_for_tool_unknown():
    try:
        for_tool("nonexistent_tool_xyz")
    except KeyError:
        pass  # expected


def test_all_names():
    names = all_names()
    assert isinstance(names, (list, set, tuple))
    assert len(names) > 0
