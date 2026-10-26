"""Tests for orvima.router module."""

import os
import tempfile

from orvima.router import goal_list_recipes, goal_route, _load_recipes


def test_load_recipes_empty_dir():
    # Non-existent directory returns empty list
    result = _load_recipes("/nonexistent/path/that/does/not/exist")
    assert result == []


def test_load_recipes_empty_string():
    # Empty string with no default locations returns empty list
    result = _load_recipes("")
    # May return [] or recipes if default locations exist
    assert isinstance(result, list)


def test_goal_list_recipes_no_recipes():
    result = goal_list_recipes("/nonexistent/path")
    assert result["ok"] is True
    assert result["count"] == 0
    assert result["recipes"] == []


def test_goal_route_no_recipes():
    result = goal_route("send a message", "/nonexistent/path")
    assert result["ok"] is False
    assert result["refused"] is True
    assert "no recipes loaded" in result["reason"]
    assert result["goal"] == "send a message"


def test_goal_route_returns_dict():
    result = goal_route("test goal", "/nonexistent/path")
    assert isinstance(result, dict)
    assert "goal" in result


def test_router_tools_tuple():
    from orvima.router import ROUTER_TOOLS
    assert len(ROUTER_TOOLS) == 2
    assert goal_list_recipes in ROUTER_TOOLS
    assert goal_route in ROUTER_TOOLS