"""Sessions + AgentLoop: the "watch your agent work" layer.

A Session owns one browser, a transcript, and an EventBus that streams what
the agent is doing to the UI (tool calls, results, live frames). The AgentLoop
runs one goal as an adaptive loop: snapshot -> planner picks the next single
browse_* action -> execute -> verify -> repeat, until the planner reports done.
Without an LLM key, the demo planner drives the offline site; everything is
runnable in CI and demos.

Concurrency: each Session owns its own BrowserController instance, so multiple
sessions run independently. The SessionStore manages the session registry.
Human takeover: pause/resume + optional approve-before-action gate.
Redaction: password fields and obvious secrets masked in snapshots/transcripts.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from . import tools
from .recovery import classify


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


def _redact_sensitive(data: dict) -> dict:
    """Redact password fields, API keys, and other secrets from data structures.

    Applied to snapshots, screenshots metadata, and transcript logs before
    they leave the process (e.g., to the UI or an LLM).
    """
    if not isinstance(data, dict):
        return data
    redacted = {}
    sensitive_keys = {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "credit_card",
        "ssn",
        "cvv",
    }
    for k, v in data.items():
        kl = k.lower()
        if any(s in kl for s in sensitive_keys):
            redacted[k] = "***REDACTED***"
        elif isinstance(v, dict):
            redacted[k] = _redact_sensitive(v)
        elif isinstance(v, list):
            redacted[k] = [_redact_sensitive(item) if isinstance(item, dict) else item for item in v]
        else:
            redacted[k] = v
    return redacted


def _redact_html(html: str) -> str:
    """Redact sensitive content in HTML (password fields, etc.)."""
    # Mask password input values
    html = re.sub(
        r'(<input[^>]*type=["\']password["\'][^>]*value=["\'])([^"\']*)(["\'])',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )
    # Mask data-* attributes that look sensitive
    html = re.sub(
        r'(data-(?:password|secret|token|key|auth)=["\'])([^"\']*)(["\'])',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )
    return html


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
        row = _redact_sensitive({"kind": kind, **data})
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
    """Runs a goal: snapshot -> decide -> act -> verify, until done."""

    def __init__(
        self,
        session: Session,
        planner=None,
        max_steps: int = 20,
        max_attempts: int | None = None,
    ):
        """Run a goal under a step budget and a separate attempt budget.

        ``max_steps`` bounds *progress*: how many decisions the planner may make.
        ``max_attempts`` bounds *work*: how many tool calls may actually run,
        retries included. They are separate on purpose - without the split, a
        retry loop spends the step budget and the run ends looking like it made
        progress when it only re-tried the same thing.
        """
        from .planner import planner_for

        self.session = session
        self.max_steps = max_steps
        # Enough headroom to recover from a few failures without letting a stuck
        # loop run forever.
        self.max_attempts = max_attempts if max_attempts is not None else max_steps * 3
        self.attempts = 0
        self.history: list[dict] = []
        self.planner = planner or planner_for(session.mode)

    def run(self, goal: str) -> dict:
        sess = self.session
        sess.goal = goal
        sess.status = "running"
        sess.bus.emit({"type": "status", "status": "running"})
        sess.log("goal", goal=goal)
        try:
            for step in range(1, self.max_steps + 1):
                sess._paused.wait()  # human pause/approve gate
                decision = self.planner.decide(goal, self.history)
                if decision.get("done"):
                    summary = decision.get("summary", "done")
                    sess.log("summary", summary=summary)
                    sess.status = "done"
                    sess.bus.emit({"type": "status", "status": "done"})
                    sess.maybe_frame(force=True)
                    return {
                        "ok": True,
                        "steps": step,
                        "attempts": self.attempts,
                        "goal": goal,
                        "summary": summary,
                    }

                name = decision["tool"]
                args = decision.get("args", {})
                result = self._attempt(step, name, args)

                if result.get("ok") is not True:
                    verdict = classify(
                        result.get("error", "unknown"), tool=name, args=args
                    )
                    sess.log("recovery", step=step, tool=name, **asdict(verdict))

                    if not verdict.retryable:
                        # Irreversible, fatal, or simply not understood. Ending
                        # here is the safe choice: a duplicated action is worse
                        # than a failed run.
                        raise RuntimeError(
                            f"step {step} ({name}) failed and will not be retried "
                            f"[{verdict.cls.value}: {verdict.reason}]: "
                            f"{result.get('error', 'unknown')}"
                        )

                    # Transient. Hand the fresh page state back to the planner
                    # and let it choose again - re-snapshotting here is what
                    # turns a dead ref into a usable one.
                    self._refresh_after_failure(name, args)
                    continue

            raise RuntimeError(f"did not finish in {self.max_steps} steps")
        except Exception as exc:
            sess.status = "error"
            sess.bus.emit({"type": "status", "status": "error"})
            sess.log("error", error=str(exc))
            return {"ok": False, "error": str(exc)}

    def _attempt(self, step: int, name: str, args: dict) -> dict:
        """Run one tool once, honouring the attempt budget.

        The attempt budget is checked here rather than in ``run`` because a retry
        loop must not be able to spend the whole step budget re-trying.
        """
        sess = self.session
        if self.attempts >= self.max_attempts:
            raise RuntimeError(
                f"attempt budget exhausted ({self.max_attempts} tool calls) - "
                "the run is not making progress"
            )
        self.attempts += 1
        sess.log("tool_call", step=step, attempt=self.attempts, tool=name, args=args)
        try:
            result = self._run_tool(name, args)
        except Exception as exc:  # keep the UI informed on bad args
            result = {"ok": False, "error": str(exc)}
        sess.log("tool_result", step=step, result=result)
        self.history.append(
            {
                "kind": "tool",
                "step": step,
                "attempt": self.attempts,
                "tool": name,
                "args": args,
                "result": result,
            }
        )
        sess.maybe_frame()
        return result

    def _refresh_after_failure(self, name: str, args: dict) -> None:
        """Put current page state back in front of the planner after a failure.

        Skipped when the action that failed was itself a read, so a failed
        ``browse_snapshot`` does not trigger another one.
        """
        if name in ("browse_snapshot", "browse_list_tabs", "browse_extract"):
            return
        try:
            self._attempt(self.history[-1]["step"] if self.history else 0, "browse_snapshot", {})
        except RuntimeError:
            raise
        except Exception:
            # A snapshot that also fails is not itself a reason to give up; the
            # planner still gets the error from the action that did fail.
            pass

    def _run_tool(self, name: str, args: dict) -> dict:
        return tools.call_tool(self.session.browser, name, args)


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
