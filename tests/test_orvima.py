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
    "browse_navigate": {"url": "https://acme.dev/contact"},
    "browse_click": {"selector": "btn"},
    "browse_hover": {"selector": "btn"},
    "browse_select": {"selector": "sort", "value": "price"},
    "browse_wait_for": {"selector": ".ready"},
    "browse_type": {"selector": "input", "text": "hi"},
    "browse_fill": {"selector": "input", "text": "hi"},
    "browse_press": {"key": "Enter"},
    "browse_go_back": {},
    "browse_wait": {"ms": 50},
    "browse_scroll": {"direction": "down"},
    "browse_snapshot": {},
    "browse_screenshot": {},
    "browse_extract": {"selector": "body"},
    "browse_eval": {"expression": "1 + 1"},
    "browse_eval_audit": {},
    "browse_open_tab": {"url": "https://acme.dev"},
    "browse_list_tabs": {},
    "browse_switch_tab": {"index": 0},
    "browse_close_tab": {"index": 0},
}

#: Tools that need a real browser and therefore cannot work in demo mode. They
#: must fail with an honest message naming the limitation - not succeed, and not
#: fail with a generic error either. A tool that pretends to have downloaded a
#: file is worse than one that admits it cannot.
DEMO_UNAVAILABLE = {
    "browse_download": {"selector": "btn"},
    "browse_set_files": {"selector": "btn", "paths": ["nothing-here.txt"]},
}


@pytest.mark.parametrize("name", sorted(set(TOOL_NAMES) - set(DEMO_UNAVAILABLE)))
def test_tool_contract(browser, name):
    if name == "browse_close_tab":  # needs a second tab to be allowed to close one
        assert call_tool(browser, "browse_open_tab", {"url": "https://acme.dev"})["ok"] is True
    result = call_tool(browser, name, TOOL_ARGS[name])
    assert result["ok"] is True, result
    assert "error" not in result


@pytest.mark.parametrize("name", sorted(DEMO_UNAVAILABLE))
def test_a_tool_that_needs_a_real_browser_says_so_plainly(browser, name):
    """Degrade honestly: the plan's gate for a capability that is absent.

    Three things must hold, and each has failed in this codebase before in some
    other form - a tool that reports success for work it did not do is the worst
    outcome available here.
    """
    result = call_tool(browser, name, DEMO_UNAVAILABLE[name])
    assert result["ok"] is False, f"{name} claimed success in demo mode"
    message = result.get("error", "")
    assert "demo mode" in message, (
        f"{name} failed without saying it is a demo-mode limitation: {message!r}"
    )
    assert "no real browser" in message, (
        f"{name} did not explain what is actually missing: {message!r}"
    )
    # And it must not look like some other kind of failure.
    assert "Traceback" not in message and "AttributeError" not in message, (
        f"{name} leaked an internal error instead of a plain explanation: {message!r}"
    )


def test_the_demo_eval_audit_works_because_it_needs_no_browser(browser):
    """The audit is readable even with no browser, which is exactly when an
    operator most wants to know what a session tried to do."""
    call_tool(browser, "browse_eval", {"expression": "1 + 1", "reason": "a check"})
    result = call_tool(browser, "browse_eval_audit", {})
    assert result["ok"] is True
    assert result["count"] >= 1
    entry = result["entries"][-1]
    assert entry["reason"] == "a check", "the stated reason was not recorded"
    assert entry["expression"] == "1 + 1"


def test_demo_eval_admits_it_cannot_measure_mutation(browser):
    """None, not False.

    The real controller reports ``mutating`` from a before/after DOM signature.
    The demo browser has no DOM, so it has no measurement - and reporting False
    would be fabricating evidence that reads exactly like "this was safe". An
    unknown value must look unknown.
    """
    result = call_tool(browser, "browse_eval", {"expression": "1 + 1"})
    assert result["ok"] is True
    assert "mutating" in result, "the field should be present even when unknown"
    assert result["mutating"] is None, (
        f"demo mode reported mutating={result['mutating']!r}, but it cannot "
        "measure this - only None is honest"
    )
    entry = call_tool(browser, "browse_eval_audit", {})["entries"][-1]
    assert entry["mutating"] is None, "the audit fabricated a mutation measurement"


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
        has_core = {"browse_navigate", "browse_click", "browse_list_tabs"} <= set(tools)
        has_open = "browse_open_tab" in tools
        assert has_core or has_open
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
            return {"tool": "browse_snapshot", "args": {}}

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
    assert LLMPlanner._parse('```json\n{"tool": "browse_click", "args": {"selector": "#x"}}\n```') == {
        "tool": "browse_click",
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
            return {"choices": [{"message": {"content": '{"tool": "browse_snapshot", "args": {}}'}}]}

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["auth"] = kwargs["headers"]["Authorization"]
        captured["model"] = kwargs["json"]["model"]
        return FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    planner = LLMPlanner(base="http://local.test/v1", key="k", model="m")
    decision = planner.decide("look around", [{"kind": "tool", "tool": "browse_navigate", "result": {"ok": True}}])
    assert decision == {"tool": "browse_snapshot", "args": {}}
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
    # `wait=true` is the original one-call contract: dispatch, then return the
    # outcome. Without it the endpoint returns as soon as the run starts, because
    # a Sentinel-gated run can block indefinitely waiting for a human and the
    # API has to stay reachable to receive the answer.
    ran = client.post(
        f"/api/sessions/{sid}/goal",
        json={"goal": "list products"},
        params={"wait": True, "timeout": 30},
    ).json()
    assert ran["ok"] is True and ran["summary"]
    # cleanup handled per-process; no real browser is ever launched here
