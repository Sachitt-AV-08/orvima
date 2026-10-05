"""FastAPI app: sessions, live frames via SSE, human controls, the /browse tools."""

from __future__ import annotations

import hmac
import json
import os
import threading
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import __version__
from .agent import AgentLoop, SessionStore
from .errors import OrvimaError
from .tools import TOOL_NAMES, call_tool

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8301

store = SessionStore()

#: Sentinel gate, shared by every session. A module-level singleton because the
#: policy and its caches are expensive to build and hold no per-session state
#: worth duplicating; only the pending-approval queue is per run.
#:
#: Built lazily. Constructing it at import time froze in whatever was importable
#: *at that moment*, which produced a gate that silently reported itself
#: unavailable and then refused every single action - a server that looked
#: healthy and prompted for everything. `:func:`get_gate` rebuilds on first use
#: and can be re-invoked after installing Sentinel without a restart.
_gate: Any | None = None
_gate_lock = threading.Lock()
#: One of "on", "degraded", "off". Kept distinct from `_gate is None` because
#: "a human switched this off" and "the gate failed to load" demand different
#: responses, and reporting a malfunction as a policy is how one becomes the
#: other. Surfaced by `gate_status` and the health endpoint.
_gate_status: str = "unknown"


class _RefusingResult:
    """A verdict from the stub below. Duck-types what the agent loop reads."""

    allowed = False
    pending = False
    risk = "unknown"
    reason = "the approval gate could not be loaded; refusing to auto-approve"
    confidence = 0.0
    degraded = True
    classifier_said = None

    def as_log(self) -> dict:
        return {
            "allowed": self.allowed,
            "pending": self.pending,
            "risk": self.risk,
            "reason": self.reason,
            "confidence": self.confidence,
            "degraded": self.degraded,
            "classifier_said": self.classifier_said,
        }


class _RefusingGate:
    """Stands in when the real gate cannot be imported, and refuses everything.

    Deliberately self-contained: it must work in exactly the case where
    `orvima.sentinel_gate` is the thing that is broken, so it cannot import from
    it. This is the last line of the fail-closed chain - the gate itself refuses
    when its policy is missing, and this refuses when the gate is missing.

    The alternative, which is what this replaced, was to return `None`. `None`
    means "no gate", and `_authorise` treats that as *allow everything*, so a
    syntax error in the gate module silently converted a gated agent into a fully
    autonomous one. That is the precise outcome `sentinel_gate.py` exists to
    prevent, reached by disabling the module that implements it.
    """

    def __init__(self, why: str) -> None:
        self._why = why
        self._result = _RefusingResult()
        self._result.reason = f"{self._why}; refusing to auto-approve"

    @property
    def available(self) -> bool:
        """False: this stands in for a gate that could not be built.

        `/api/gate/stats` reads it, so its absence crashed that endpoint with an
        `AttributeError` - the health check meant to explain a safe-but-degraded
        install was itself the thing that broke.
        """
        return False

    def check(self, tool, args=None, **_kw):
        return self._result

    def revalidate(self, session_id, tool, args=None, **_kw):
        """Called again after a human approves, to check the page has not moved on.

        Same verdict. There is nothing here that can be trusted to have changed
        its mind, so a human's approval cannot be laundered into permission by a
        re-check that has no policy behind it.
        """
        return self._result

    def request_approval(self, session_id, tool, args, result, snapshot=None):
        return f"unavailable-{abs(hash((session_id, tool, str(args)))):08x}"

    def pending(self, session_id=None):
        return []

    def lapsed(self, request_id) -> bool:
        """Always True: a request this gate issued can never be answered.

        `Agent._await_approval` calls `lapsed()` before it inspects `pending()`,
        because leaving the queue is ambiguous - `resolve()` pops a request too,
        so an answered one looks like a dropped one. This gate has no queue and
        no way to record an answer, so every request it hands out is dropped by
        definition.

        Without this method the waiting loop raised `AttributeError` on the
        first gated action and the whole run died with a 502 - so the default
        install, the one with no sentinel, could not fail closed at all. It
        crashed instead. Returning True makes the loop refuse immediately, which
        is the entire point of this class.
        """
        return True

    def resolve(self, request_id, approved):
        return None

    def forget_refs(self) -> None:
        return None

    def snapshot_stats(self) -> dict:
        return {"degraded": 1, "pending": 0, "reason": self._why}


def gate_status() -> str:
    """Whether gating is on, degraded, or deliberately off.

    Reported so that a session running with no gate in force is visible rather
    than indistinguishable from one that is being judged.
    """
    return _gate_status


def get_gate(rebuild: bool = False):
    """The shared gate, built on first use.

    `ORVIMA_SENTINEL=off` disables gating entirely, which makes the agent
    **fully unattended** - every action runs without being judged. That is a
    legitimate operator choice and it is honoured, but it is not the same thing
    as pausing, and it is reported through :func:`gate_status` rather than
    happening silently.

    Any *failure* to build the gate is a different matter. It yields a gate that
    refuses every action, never `None`. A malfunction must not have the same
    effect as a decision to turn safety off.
    """
    global _gate, _gate_status
    if os.environ.get("ORVIMA_SENTINEL", "on").lower() in ("off", "0", "false", "no"):
        _gate_status = "off"
        return None
    with _gate_lock:
        if _gate is None or rebuild:
            try:
                from .sentinel_gate import make_gate

                _gate = make_gate(
                    classifier_mode=os.environ.get("ORVIMA_SENTINEL_MODE", "off")
                )
                _gate_status = "degraded" if not getattr(_gate, "available", True) else "on"
            except Exception as exc:
                _gate = _RefusingGate(f"gate unavailable ({type(exc).__name__}: {exc})")
                _gate_status = "degraded"
        return _gate


class CreateSession(BaseModel):
    # real, not demo. A client that posts nothing must get a real browser, not a
    # scripted acme.dev that answers ok:true about sites it never opened.
    mode: str = Field(default="real", pattern="^(demo|real)$")
    # Empty by default, so a session with no URL is not silently parked on a
    # fictional storefront. Set it, or let ORVIMA_START_URL decide.
    start_url: str = ""
    goal: str = ""


class RunGoal(BaseModel):
    goal: str


class ToolCall(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)


class Control(BaseModel):
    action: str = Field(pattern="^(pause|resume|cancel)$")


class Approval(BaseModel):
    approved: bool
    #: optional human note, surfaced in the transcript
    note: str = ""


#: Header a remote caller may present the token in. A custom header rather than
#: only `Authorization` so a phone page can read the token from a form field and
#: a CLI can use either.
TOKEN_HEADER = "X-Orvima-Token"


def configured_token() -> str | None:
    """The API token, or None when none is set.

    A blank or whitespace-only value counts as unset. A shell variable that
    expanded to nothing is the common way to end up with a token that is present
    in the environment but carries no secret, and treating that as configured
    would hand out an endpoint anyone could open.
    """
    raw = os.environ.get("ORVIMA_API_TOKEN", "")
    return raw.strip() or None


def token_ok(offered: str | None) -> bool:
    """Whether `offered` is the configured token.

    With no token configured this is True for anything, because the loopback
    default has to work with zero setup - and because `create_app` refuses to
    build an app bound anywhere but loopback in that state. The safety lives in
    that refusal, not here: an open endpoint on a machine's own loopback
    interface has no trust boundary to cross, while an open one on a network
    does, and the network case is prevented from existing.

    The moment a token *is* configured it is required, and compared with
    `compare_digest` rather than `==`. A short-circuiting compare returns as soon
    as it finds a difference, which leaks the secret one character at a time to
    anyone able to time the response.
    """
    expected = configured_token()
    if not expected:
        return True
    if not offered:
        return False
    return hmac.compare_digest(offered, expected)


def _positive_ttl(active) -> float | None:
    """The gate's approval TTL, or None when it has no expiry.

    0 and negative values are orvima's "no expiry" sentinel rather than a real
    deadline, so they become None instead of travelling to the client as a
    number that reads as "the deadline has already passed".
    """
    ttl = getattr(active, "approval_ttl", None)
    return ttl if isinstance(ttl, (int, float)) and ttl > 0 else None


def _gate_health(active: Any | None) -> dict:
    """Gate health, in the shape both the UI and the phone page read.

    Split out of the endpoint so `gate=1` and `/api/gate/stats` cannot drift
    into reporting different states for the same gate.
    """
    if active is None:
        return {"gate": gate_status(), "available": False}
    return {
        "gate": gate_status(),
        "available": active.available,
        "mode": os.environ.get("ORVIMA_SENTINEL_MODE", "off"),
        # The phone page needs the deadline to say how long a queued decision is
        # still answerable. Age alone does not say whether it is still live.
        #
        # A TTL of 0 is orvima's own sentinel for "no expiry" (`_expired`
        # returns False when it is <= 0), so it is normalised to None here.
        # Reporting 0 would read as a deadline that has already passed: a client
        # subtracting a now-moment from zero concludes everything is expired, and
        # would hide the controls on every live decision.
        "approval_ttl": _positive_ttl(active),
    }


def _require_token(request: Request) -> None:
    """FastAPI dependency guarding the endpoints that act.

    Applied to the endpoints that approve an irreversible action or drive the
    browser directly - not to the read-only ones, because a phone on the other
    side of a VPN still needs to see whether the server is up and what it is
    waiting on.
    """
    offered = request.headers.get(TOKEN_HEADER)
    if not offered:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            offered = authorization[7:].strip()
    if not token_ok(offered):
        raise HTTPException(
            status_code=401,
            detail=(
                "this endpoint acts on a real browser; present the API token in "
                f"the {TOKEN_HEADER} header or as a bearer token"
            ),
        )


def create_app(host: str = DEFAULT_HOST) -> FastAPI:
    """Build the app, refusing a configuration that would expose it.

    `host` is the interface the server will be reachable on. With no API token
    configured the acting endpoints are open, which is right for loopback and
    wrong for anything else - so building an app that will listen on a network
    interface without a token is refused here rather than served.

    The check is in `create_app` and not only in the CLI, because `create_app`
    is what any other caller - a test, an embedder, a future entry point - gets.
    A guard that lives in one launcher is a guard the next launcher forgets.
    """
    from .cli import is_loopback  # noqa: PLC0415 - cli imports api; avoid a cycle at module load

    if not configured_token() and not is_loopback(host):
        raise OrvimaError(
            f"refusing to serve on {host or '(every interface)'} with no API "
            "token: the approval endpoint would let anything on that network "
            "approve actions in a real logged-in browser.\n"
            "  set ORVIMA_API_TOKEN to a secret, or bind loopback "
            "(host='127.0.0.1')."
        )

    app = FastAPI(title="Orvima", version=__version__, docs_url="/docs")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = store

    # ----------------------------------------------------------- meta ----
    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__, "sessions": len(store.list())}

    @app.get("/api/tools")
    def tools_list() -> dict:
        return {"tools": sorted(TOOL_NAMES), "ok": True}

    # -------------------------------------------------------- sessions ----
    @app.post("/api/sessions", status_code=201)
    def create_session(body: CreateSession) -> dict:
        try:
            sess = store.create(mode=body.mode, start_url=body.start_url, goal=body.goal)
        except OrvimaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "session": _public(sess)}

    @app.get("/api/sessions")
    def list_sessions() -> dict:
        return {"ok": True, "sessions": [_public(s) for s in store.list()]}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return {"ok": True, "session": _public(store.get(session_id))}

    @app.get("/api/sessions/{session_id}/frame")
    def get_frame(session_id: str) -> dict:
        sess = store.get(session_id)
        try:
            shot = sess.browser.screenshot()
        except OrvimaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **shot}

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str) -> dict:
        store.delete(session_id)
        return {"ok": True}

    # ------------------------------------------------------------ stream ----
    @app.get("/api/sessions/{session_id}/events")
    async def events(session_id: str):
        sess = store.get(session_id)
        q = sess.bus.subscribe()

        async def gen():
            try:
                sess.maybe_frame(force=True)
                for row in sess.transcript:
                    yield _sse({"type": "log", "row": row})
                yield _sse({"type": "status", "status": sess.status})
                while True:
                    while q:
                        yield _sse(q.pop(0))
                    await _yield_()
            finally:
                sess.bus.unsubscribe(q)

        return EventSourceResponse(gen())

    # ------------------------------------------------------------- agent ----
    @app.post("/api/sessions/{session_id}/goal")
    def run_goal(
        session_id: str,
        body: RunGoal,
        wait: bool = Query(default=False, description="Block until the run finishes."),
        timeout: float = Query(default=120.0, gt=0, le=3600),
    ) -> dict:
        sess = store.get(session_id)
        if not body.goal:
            raise HTTPException(status_code=422, detail="goal is required")

        loop = AgentLoop(sess, gate=get_gate())
        sess._loop = loop
        result: dict = {}
        done = threading.Event()

        def _work() -> None:
            try:
                result.update(loop.run(body.goal))
            finally:
                done.set()

        thread = threading.Thread(target=_work, daemon=True, name=f"loop-{sess.id}")
        thread.start()

        if not wait:
            # Default: return as soon as the run is under way. A gated run blocks
            # waiting for a human, so the request must not hold the connection -
            # watch the event stream for `approval_required`, or poll `/result`.
            return {"ok": True, "dispatched": True, "session": sess.id}

        # Opt-in synchronous mode, for callers that want the outcome in one call
        # (the original behaviour). Bounded, because a run waiting on a human
        # would otherwise hold the request open indefinitely.
        if not done.wait(timeout):
            return {"ok": True, "dispatched": True, "timed_out": True, "session": sess.id}
        if not result.get("ok"):
            raise HTTPException(status_code=502, detail=result)
        return result

    @app.get("/api/sessions/{session_id}/result")
    def run_result(session_id: str) -> dict:
        """Outcome of the last run, once it has finished."""
        sess = store.get(session_id)
        if sess.status in ("running", "awaiting_approval", "idle"):
            return {"ok": True, "status": sess.status, "done": False}
        rows = [t for t in sess.transcript if t["kind"] in ("summary", "error", "denied")]
        return {"ok": True, "status": sess.status, "done": True, "outcome": rows[-1] if rows else None}

    # ------------------------------------------------------------ phone ----
    @app.get("/phone", include_in_schema=False)
    def phone():
        """The approval queue, for a phone.

        Read-only in the sense that it grants nothing: every button it shows
        calls an endpoint that was already token-guarded. Serving it from orvima
        keeps a purchase decision from depending on a third-party script.
        """
        from .phone import phone_page  # noqa: PLC0415 - keeps the page optional to import

        return phone_page()

    # ------------------------------------------------------- approvals ----
    @app.get("/api/approvals")
    def list_approvals(
        session_id: str | None = None,
        gate: bool = Query(default=False),
    ) -> dict:
        """The pending approval queue.

        `gate=1` includes gate health. Optional because the existing UI polls
        this without it, and a parameter that changes the response shape should
        be asked for rather than imposed.

        Expiry is applied here, at the boundary that hands the queue to a human.
        A request past its TTL can no longer be answered - `resolve()` drops it
        and returns None - so listing one would put a live-looking decision in
        front of a human whose tap silently does nothing. Sweeping here keeps
        `pending()` a pure read, so the agent's own wait loop and this endpoint
        cannot race each other over who removes the request.
        """
        active = get_gate()
        if active is None:
            return {"ok": True, "approvals": [], "gate": "disabled"}
        active.expire_stale()
        body = {"ok": True, "approvals": [r.public() for r in active.pending(session_id)]}
        if gate:
            body.update(_gate_health(active))
        return body
        if active is None:
            return {"ok": True, "approvals": [], "gate": "disabled"}
        return {"ok": True, "approvals": [r.public() for r in active.pending(session_id)]}

    @app.post("/api/approvals/{request_id}", dependencies=[Depends(_require_token)])
    def answer_approval(request_id: str, body: Approval) -> dict:
        """Resolve a pending approval.

        Token-guarded because this is the endpoint that spends money. On
        loopback with no token configured it stays open, which is the point of
        the loopback default; `cli.check_bind` refuses to be reachable from
        anywhere else unless a token is set.
        """
        active = get_gate()
        if active is None:
            raise HTTPException(status_code=503, detail="sentinel gate disabled")
        request = active.resolve(request_id, body.approved)
        if request is None:
            raise HTTPException(status_code=404, detail=f"unknown request {request_id!r}")
        sess = store.get(request.session_id)
        if sess._loop is not None:
            sess._loop.resolve_approval(request_id, body.approved)
        if body.note:
            sess.log("approval_note", request_id=request_id, note=body.note)
        return {"ok": True, "approved": body.approved, "tool": request.tool}

    @app.get("/api/gate/stats")
    def gate_stats(rebuild: bool = Query(default=False)) -> dict:
        """Gate health. `available: false` means Sentinel is not importable.

        That state is safe but not useful - every action will be gated - so it is
        reported plainly here rather than showing up as unexplained prompts.
        """
        active = get_gate(rebuild=rebuild)
        if active is None:
            return {"ok": True, "gate": gate_status(), "available": False}
        # Spread from the shared builder so this endpoint cannot report a
        # different state for the same gate than /api/approvals?gate=1 does.
        return {
            "ok": True,
            **_gate_health(active),
            "stats": active.snapshot_stats(),
        }

    @app.post("/api/sessions/{session_id}/control", dependencies=[Depends(_require_token)])
    def control(session_id: str, body: Control) -> dict:
        # Guarded because `cancel` unblocks a run that is waiting on an approval,
        # so an unguarded caller could drive the run's control flow remotely.
        sess = store.get(session_id)
        if body.action == "pause":
            sess.pause()
        elif body.action == "cancel":
            # Unblocks a run that is waiting on an approval, so "cancel" is not
            # a polite request the agent loop can ignore forever.
            sess.status = "cancelled"
            sess.bus.emit({"type": "status", "status": sess.status})
        else:
            sess.resume()
        return {"ok": True, "status": sess.status}

    # -------------------------------------------------------- direct tools ----
    @app.post("/api/sessions/{session_id}/tools", dependencies=[Depends(_require_token)])
    def run_tool(session_id: str, body: ToolCall) -> dict:
        """Run one browse tool directly.

        Guarded for the same reason as the approval endpoint: this drives a real
        logged-in browser, so an open version of it is an open version of the
        account.
        """
        sess = store.get(session_id)
        try:
            result = call_tool(sess.browser, body.tool, body.args)
        except OrvimaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sess.log("manual_tool", tool=body.tool, args=body.args, result=result)
        sess.maybe_frame(force=True)
        return result

    @app.exception_handler(OrvimaError)
    async def orvima_error_handler(_req, exc: OrvimaError):
        return Response(json.dumps({"ok": False, "error": str(exc)}), status_code=400)

    return app


def _public(sess) -> dict:
    return {
        "id": sess.id,
        "mode": sess.mode,
        "status": sess.status,
        "goal": sess.goal,
        "start_url": sess.start_url,
        "created": sess.created,
        "steps": len([t for t in sess.transcript if t["kind"] == "tool_result"]),
    }


def _sse(data: dict) -> dict:
    return {"data": json.dumps(data)}


async def _yield_() -> None:  # pragma: no cover - union of await points
    import asyncio

    await asyncio.sleep(0.1)


app = create_app()
