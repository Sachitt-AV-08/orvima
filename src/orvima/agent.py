"""Sessions + AgentLoop: the "watch your agent work" layer.

A Session owns one browser, a transcript, and an EventBus that streams what
the agent is doing to the UI (tool calls, results, live frames). The AgentLoop
executes one goal as a sequence of browse_* tool calls. Without an LLM key it
falls back to a deterministic scripted planner (demo site), so the whole thing
is runnable offline and in CI.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import tools


class EventBus:
    """Minimal fan-out: emit() puts a message on every subscriber's queue."""

    def __init__(self) -> None:
        self._queues: list[list[dict]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> list[dict]:
        with self._lock:
            q: list[dict] = []
            self._queues.append(q)
            return q

    def unsubscribe(self, q: list[dict]) -> None:
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def emit(self, event: dict) -> None:
        event = {**event, "ts": time.time()}
        with self._lock:
            for q in self._queues:
                q.append(event)


@dataclass
class Session:
    id: str
    mode: str
    browser: Any
    bus: EventBus = field(default_factory=EventBus)
    status: str = "idle"
    goal: str = ""
    start_url: str = "https://acme.dev"
    transcript: list[dict] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    _loop: AgentLoop | None = None
    _paused: threading.Event = field(default_factory=threading.Event)
    _last_frame: float = 0.0

    def __post_init__(self) -> None:
        self._paused.set()

    def pause(self) -> None:
        self._paused.clear()
        self.status = "paused"
        self.bus.emit({"type": "status", "status": self.status})

    def resume(self) -> None:
        self._paused.set()
        self.status = "running"
        self.bus.emit({"type": "status", "status": self.status})

    def log(self, kind: str, **data: Any) -> None:
        row = {"kind": kind, **data}
        self.transcript.append(row)
        self.bus.emit({"type": "log", "row": row})

    def maybe_frame(self, force: bool = False) -> None:
        """Stream a screenshot event, throttled to ~1 fps, so the UI stays light."""
        now = time.time()
        if not force and now - self._last_frame < 1.0:
            return
        try:
            shot = self.browser.screenshot()
            self._last_frame = now
            self.bus.emit({"type": "frame", "png_b64": shot["png_b64"]})
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.browser.close()
        except Exception:
            pass


class AgentLoop:
    """Runs a goal: plan steps -> execute browse_* tools -> verify each step."""

    def __init__(self, session: Session, planner: Callable[[str], list[dict]] | None = None):
        self.session = session
        self.planner = planner or planner_for(session.mode)

    def run(self, goal: str) -> dict:
        sess = self.session
        sess.goal = goal
        sess.status = "running"
        sess.bus.emit({"type": "status", "status": "running"})
        sess.log("goal", goal=goal)
        try:
            steps = self.planner(goal)
            if not steps:
                raise RuntimeError("planner produced no steps")
            sess.log("plan", steps=steps)
            for i, step in enumerate(steps, start=1):
                sess._paused.wait()  # human pause/approve gate
                name = step.get("tool", "")
                args = step.get("args", {})
                sess.log("tool_call", step=i, tool=name, args=args)
                try:
                    result = self._run_tool(name, args)
                except Exception as exc:  # make sure UI always gets an answer
                    result = {"ok": False, "error": str(exc)}
                sess.log("tool_result", step=i, result=result)
                sess.maybe_frame()
                if result.get("ok") is not True:
                    raise RuntimeError(
                        f"step {i} ({name}) failed: {result.get('error', 'unknown')}"
                    )
            sess.status = "done"
            sess.bus.emit({"type": "status", "status": "done"})
            sess.maybe_frame(force=True)
            return {"ok": True, "steps": len(steps), "goal": goal}
        except Exception as exc:
            sess.status = "error"
            sess.bus.emit({"type": "status", "status": "error"})
            sess.log("error", error=str(exc))
            return {"ok": False, "error": str(exc)}

    def _run_tool(self, name: str, args: dict) -> dict:
        return tools.call_tool(self.session.browser, name, args)


# ------------------------------------------------------------ planners -------

def _demo_planner(goal: str) -> list[dict]:
    """Deterministic scripted plan for the acme.dev demo site."""
    g = goal.lower()
    if any(k in g for k in ("contact", "message", "support", "email")):
        return [
            {"tool": "navigate", "args": {"url": "https://acme.dev/contact"}},
            {"tool": "fill", "args": {"selector": "input[name=name]", "text": "Orvima"}},
            {"tool": "fill", "args": {"selector": "input[name=email]", "text": "hello@orvima.dev"}},
            {"tool": "fill", "args": {"selector": "textarea[name=message]", "text": goal}},
            {"tool": "click", "args": {"selector": "button:has-text('Send')"}},
            {"tool": "snapshot", "args": {}},
        ]
    if any(k in g for k in ("product", "bolt", "anchor", "shop", "cutter")):
        return [
            {"tool": "navigate", "args": {"url": "https://acme.dev/products"}},
            {"tool": "snapshot", "args": {}},
        ]
    return [
        {"tool": "navigate", "args": {"url": "https://acme.dev"}},
        {"tool": "snapshot", "args": {}},
    ]


def planner_for(mode: str) -> Callable[[str], list[dict]]:
    base = os.environ.get("ORVIMA_LLM_BASE")
    key = os.environ.get("ORVIMA_LLM_KEY")
    model = os.environ.get("ORVIMA_LLM_MODEL", "gpt-4o-mini")
    if mode == "demo" or not (base and key):
        return _demo_planner
    return _llm_planner(base, key, model)


def _llm_planner(base: str, key: str, model: str) -> Callable[[str], list[dict]]:
    def planner(goal: str) -> list[dict]:
        from .planner_llm import llm_plan

        return llm_plan(goal, base=base, key=key, model=model)

    return planner


# -------------------------------------------------------------- store -------

class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, mode: str, start_url: str = "https://acme.dev", goal: str = "") -> Session:
        sess = Session(
            id=uuid.uuid4().hex[:12],
            mode=mode,
            browser=_make_browser(mode),
            start_url=start_url,
        )
        with self._lock:
            self._sessions[sess.id] = sess
        return sess

    def get(self, session_id: str) -> Session:
        from .errors import SessionNotFoundError

        with self._lock:
            sess = self._sessions.get(session_id)
        if sess is None:
            raise SessionNotFoundError(f"unknown session {session_id!r}")
        return sess

    def list(self) -> list[Session]:
        with self._lock:
            return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess is not None:
            sess.close()

    def close_all(self) -> None:
        for sess in list(self._sessions.values()):
            sess.close()


def _make_browser(mode: str) -> Any:
    if mode == "demo":
        from .demo import DemoBrowser

        return DemoBrowser()
    from .browser import BrowserController

    browser = BrowserController(base_url=os.environ.get("ORVIMA_START_URL", "https://example.com"))
    browser.start()
    return browser
