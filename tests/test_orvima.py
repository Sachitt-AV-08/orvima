"""Core behavior tests for Orvima — offline (demo browser), no Chrome needed."""

from __future__ import annotations

import pytest

from orvima.demo import DemoBrowser
from orvima.planner import DemoPlanner, LLMPlanner
from orvima.tools import TOOL_NAMES, TOOLS, call_tool


@pytest.fixture()
def browser():
    return DemoBrowser()


TOOL_ARGS = {
    "navigate": {"url": "https://acme.dev/contact"},
    "click": {"selector": "btn"},
    "hover": {"selector": "btn"},
    "select": {"selector": "sort", "value": "price"},
    "wait_for": {"selector": ".ready"},
    "type": {"selector": "input", "text": "hi"},
    "fill": {"selector": "input", "text": "hi"},
    "press": {"key": "Enter"},
    "go_back": {},
    "wait": {"ms": 50},
    "scroll": {"direction": "down"},
    "snapshot": {},
    "screenshot": {},
    "extract": {"selector": "body"},
    "eval": {"expression": "1 + 1"},
    "open_tab": {"url": "https://acme.dev"},
    "list_tabs": {},
    "switch_tab": {"index": 0},
    "close_tab": {"index": 0},
}


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_contract(browser, name):
    if name == "close_tab":  # needs a second tab to be allowed to close one
        assert call_tool(browser, "open_tab", {"url": "https://acme.dev"})["ok"] is True
    result = call_tool(browser, name, TOOL_ARGS[name])
    assert result["ok"] is True, result
    assert "error" not in result


def test_unknown_tool_raises(browser):
    from orvima.errors import OrvimaError

    with pytest.raises(OrvimaError):
        call_tool(browser, "definitely_not_a_tool", {})


def test_all_tools_are_mcp_bindable():
    from orvima.agent import SessionStore
    from orvima.mcp_server import _bind

    sess = SessionStore().create(mode="demo")
    for fn in TOOLS:
        bound = _bind(sess, fn)
        assert bound.__name__ == fn.__name__
        assert callable(bound)


# ------------------------------------------------------------------ agent loop


def test_run_contact_goal_reaches_done():
    from orvima.agent import AgentLoop, SessionStore

    sess = SessionStore().create(mode="demo")
    try:
        result = AgentLoop(sess).run("message Acme support")
        assert result["ok"] is True
        assert result["summary"]
        kinds = [t["kind"] for t in sess.transcript]
        assert "summary" in kinds
        tools = [t["tool"] for t in sess.transcript if t["kind"] == "tool_call"]
        assert "navigate" in tools and "click" in tools and "list_tabs" in tools or "open_tab" in tools
    finally:
        sess.close()


def test_bad_tool_aborts_loop():
    from orvima.agent import AgentLoop, SessionStore

    class BoomPlanner:
        toolset = staticmethod(lambda: ", ".join(sorted(TOOL_NAMES)))

        def decide(self, goal, history):
            return {"tool": "not_a_real_tool", "args": {}}

    sess = SessionStore().create(mode="demo")
    try:
        result = AgentLoop(sess, planner=BoomPlanner()).run("anything")
        assert result["ok"] is False
        assert "not_a_real_tool" in result["error"]
    finally:
        sess.close()


def test_max_steps_limits_loop():
    from orvima.agent import AgentLoop, SessionStore

    class StubbornPlanner:
        toolset = staticmethod(lambda: ", ".join(sorted(TOOL_NAMES)))

        def decide(self, goal, history):
            return {"tool": "snapshot", "args": {}}

    sess = SessionStore().create(mode="demo")
    try:
        result = AgentLoop(sess, planner=StubbornPlanner(), max_steps=3).run("loop forever")
        assert result["ok"] is False
        assert "3 steps" in result["error"]
    finally:
        sess.close()


def test_demo_planner_terminates():
    planner = DemoPlanner()
    history: list[dict] = []
    for _ in range(30):  # would hang if the planner never said done
        decision = planner.decide("summarize products", history)
        if decision.get("done"):
            break
        history.append({"kind": "tool", "tool": decision["tool"], "args": {}, "result": {"ok": True}})
    else:
        pytest.fail("demo planner did not terminate")


# ------------------------------------------------------------- LLM planner


def test_llm_parse_handles_fenced_json():
    assert LLMPlanner._parse('```json\n{"tool": "click", "args": {"selector": "#x"}}\n```') == {
        "tool": "click",
        "args": {"selector": "#x"},
    }
    assert LLMPlanner._parse('{"done": true, "summary": "ok"}') == {"done": True, "summary": "ok"}


def test_llm_parse_rejects_unknown_tool():
    with pytest.raises(RuntimeError):
        LLMPlanner._parse('{"tool": "teleport", "args": {}}')


def test_llm_planner_decide_uses_mock_endpoint(monkeypatch):
    import httpx

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"tool": "snapshot", "args": {}}'}}]}

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["auth"] = kwargs["headers"]["Authorization"]
        captured["model"] = kwargs["json"]["model"]
        return FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    planner = LLMPlanner(base="http://local.test/v1", key="k", model="m")
    decision = planner.decide("look around", [{"kind": "tool", "tool": "navigate", "result": {"ok": True}}])
    assert decision == {"tool": "snapshot", "args": {}}
    assert captured["url"] == "http://local.test/v1/chat/completions"
    assert captured["model"] == "m"


def test_real_mode_without_llm_is_a_grid_error():
    from orvima.planner import planner_for

    with pytest.raises(RuntimeError):
        planner_for("real")


# ---------------------------------------------------- browser/API glue


def test_channel_detection(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("ORVIMA_BROWSER", raising=False)
    from orvima.browser import detect_channel

    assert detect_channel() is None  # no bundle path match on non-windows
    monkeypatch.setenv("ORVIMA_BROWSER", "msedge")
    assert detect_channel() == "msedge"


def test_api_sessions_and_goal(monkeypatch):
    from fastapi.testclient import TestClient

    from orvima import __version__
    from orvima.api import app

    client = TestClient(app)
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["version"] == __version__
    tools = client.get("/api/tools").json()
    assert len(tools["tools"]) >= 19

    created = client.post("/api/sessions", json={"mode": "demo", "goal": "products"}).json()
    sid = created["session"]["id"]
    ran = client.post(f"/api/sessions/{sid}/goal", json={"goal": "list products"}).json()
    assert ran["ok"] is True and ran["summary"]
    # cleanup handled per-process; no real browser is ever launched here
