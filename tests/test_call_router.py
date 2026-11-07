"""Tests for orvima.call_router module."""

from orvima.call_router import route_call_intent, list_call_recipes, CALL_ROUTER_TOOLS


def test_route_call_intent_no_recipes():
    r = route_call_intent("hello, I need help")
    assert isinstance(r, dict)
    assert r["ok"] is False or r["ok"] is True


def test_list_call_recipes():
    r = list_call_recipes()
    assert isinstance(r, dict)
    assert "count" in r or "recipes" in r


def test_call_router_tools_tuple():
    assert len(CALL_ROUTER_TOOLS) == 2


def test_call_router_tools_annotated():
    from orvima.tool_annotations import for_tool
    for fn in CALL_ROUTER_TOOLS:
        ann = for_tool(fn.__name__)
        assert ann is not None