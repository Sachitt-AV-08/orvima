"""FastAPI app: sessions, live frames via SSE, human controls, the /browse tools."""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Response
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


class CreateSession(BaseModel):
    mode: str = Field(default="demo", pattern="^(demo|real)$")
    start_url: str = "https://acme.dev"
    goal: str = ""


class RunGoal(BaseModel):
    goal: str


class ToolCall(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)


class Control(BaseModel):
    action: str = Field(pattern="^(pause|resume)$")


def create_app() -> FastAPI:
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
    def run_goal(session_id: str, body: RunGoal) -> dict:
        sess = store.get(session_id)
        if not body.goal:
            raise HTTPException(status_code=422, detail="goal is required")
        loop = AgentLoop(sess)
        sess._loop = loop
        result = loop.run(body.goal)
        if not result.get("ok"):
            raise HTTPException(status_code=502, detail=result)
        return result

    @app.post("/api/sessions/{session_id}/control")
    def control(session_id: str, body: Control) -> dict:
        sess = store.get(session_id)
        if body.action == "pause":
            sess.pause()
        else:
            sess.resume()
        return {"ok": True, "status": sess.status}

    # -------------------------------------------------------- direct tools ----
    @app.post("/api/sessions/{session_id}/tools")
    def run_tool(session_id: str, body: ToolCall) -> dict:
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
