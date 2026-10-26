"""Tests for orvima.planner module."""

from orvima.planner import DemoPlanner, planner_for


def test_demo_planner():
    planner = DemoPlanner()
    result = planner.decide("send a message to Acme support", [])
    assert isinstance(result, dict)


def test_demo_planner_done():
    planner = DemoPlanner()
    # After enough steps, should return done
    history = [{"kind": "tool"} for _ in range(10)]
    result = planner.decide("test", history)
    assert isinstance(result, dict)


def test_planner_for_demo():
    planner = planner_for("demo")
    assert planner is not None


def test_planner_toolset():
    from orvima.planner import Planner
    ts = Planner.toolset()
    assert isinstance(ts, str)
    assert len(ts) > 0


def test_ollama_available():
    from orvima.planner import _ollama_available
    base, model = _ollama_available()
    assert isinstance(base, str)
    assert isinstance(model, str)