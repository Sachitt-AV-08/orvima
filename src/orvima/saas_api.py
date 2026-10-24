"""orvima SaaS — Deploy browser sessions, get CDP URLs.

Day 2: Minimal viable deploy endpoint.
Launches a Chromium instance with a remote debugging port and returns
the CDP WebSocket URL that any Playwright/Puppeteer client can connect to.

Usage:
    python -m orvima.saas_api
    # or: uvicorn orvima.saas_api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_PORT = int(os.environ.get("ORVIMA_SAAS_BASE_PORT", "9222"))
MAX_SESSIONS = int(os.environ.get("ORVIMA_SAAS_MAX_SESSIONS", "10"))
SESSION_TTL_MINUTES = int(os.environ.get("ORVIMA_SAAS_TTL_MINUTES", "60"))

# ---------------------------------------------------------------------------
# Session registry
# ---------------------------------------------------------------------------
@dataclass
class DeployedSession:
    id: str
    port: int
    pid: int | None
    cdp_url: str
    ws_url: str
    created: float
    expires: float
    status: str = "running"


_sessions: dict[str, DeployedSession] = {}
_lock = threading.Lock()
_port_counter = BASE_PORT


def _next_port() -> int:
    global _port_counter
    with _lock:
        port = _port_counter
        _port_counter += 1
        if _port_counter > BASE_PORT + 999:
            _port_counter = BASE_PORT
    return port


def _launch_chromium(port: int, headless: bool = True) -> tuple[int, str]:
    """Launch Chromium with remote debugging and return (pid, ws_url)."""
    import shutil

    # Find chromium binary — prefer Playwright's bundled one
    chrome_paths = []
    try:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        chrome_paths.append(_pw.chromium.executable_path)
        _pw.stop()
    except Exception:
        pass
    chrome_paths.extend([
        os.environ.get("CHROME_BIN", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ])
    chrome_bin = None
    for p in chrome_paths:
        if p and os.path.exists(p):
            chrome_bin = p
            break
    if not chrome_bin:
        chrome_bin = shutil.which("chrome") or shutil.which("chromium") or shutil.which("google-chrome")
    if not chrome_bin:
        raise RuntimeError("No Chromium/Chrome binary found. Install Chrome or set CHROME_BIN env var.")

    user_data_dir = os.path.join(os.environ.get("TEMP", "/tmp"), f"orvima-session-{port}")
    os.makedirs(user_data_dir, exist_ok=True)

    args = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--headless=new" if headless else "",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    args = [a for a in args if a]

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for CDP endpoint to be ready
    for _ in range(30):
        try:
            resp = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
            data = json.loads(resp.read())
            ws_url = data.get("webSocketDebuggerUrl", "")
            if ws_url:
                return proc.pid, ws_url
        except Exception:
            time.sleep(0.5)

    proc.kill()
    raise RuntimeError(f"Chromium did not start on port {port}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Orvima SaaS",
    description="Deploy browser sessions, get CDP URLs",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DeployRequest(BaseModel):
    headless: bool = True
    start_url: str = ""
    ttl_minutes: int = Field(default=SESSION_TTL_MINUTES, ge=1, le=1440)


class DeployResponse(BaseModel):
    ok: bool
    session_id: str
    cdp_url: str
    ws_url: str
    port: int
    expires_in_minutes: int
    connect_example: str


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "version": "0.1.0",
        "active_sessions": len(_sessions),
        "max_sessions": MAX_SESSIONS,
    }


@app.post("/api/deploy", response_model=DeployResponse)
def deploy(body: DeployRequest, x_api_key: str = Header(default="demo")) -> DeployResponse:
    """Deploy a new browser session and return its CDP URL."""
    if len(_sessions) >= MAX_SESSIONS:
        raise HTTPException(status_code=429, detail="Max sessions reached. Try again later.")

    session_id = uuid.uuid4().hex[:12]
    port = _next_port()

    try:
        pid, ws_url = _launch_chromium(port, headless=body.headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    cdp_url = f"http://localhost:{port}"
    expires = time.time() + body.ttl_minutes * 60

    session = DeployedSession(
        id=session_id,
        port=port,
        pid=pid,
        cdp_url=cdp_url,
        ws_url=ws_url,
        created=time.time(),
        expires=expires,
    )

    with _lock:
        _sessions[session_id] = session

    # Schedule cleanup
    def _cleanup():
        time.sleep(body.ttl_minutes * 60)
        destroy_session(session_id)

    threading.Thread(target=_cleanup, daemon=True).start()

    connect_example = (
        f"from playwright.sync_api import sync_playwright\n"
        f"pw = sync_playwright().start()\n"
        f"browser = pw.chromium.connect_over_cdp('{cdp_url}')\n"
        f"page = browser.contexts[0].pages[0]\n"
        f"page.goto('{body.start_url or 'https://example.com'}')"
    )

    return DeployResponse(
        ok=True,
        session_id=session_id,
        cdp_url=cdp_url,
        ws_url=ws_url,
        port=port,
        expires_in_minutes=body.ttl_minutes,
        connect_example=connect_example,
    )


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    with _lock:
        session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    remaining = max(0, int(session.expires - time.time()))
    return {
        "ok": True,
        "session_id": session.id,
        "cdp_url": session.cdp_url,
        "ws_url": session.ws_url,
        "status": session.status,
        "remaining_seconds": remaining,
    }


@app.delete("/api/sessions/{session_id}")
def destroy_session(session_id: str) -> dict:
    with _lock:
        session = _sessions.pop(session_id, None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Kill the process
    if session.pid:
        try:
            import psutil
            proc = psutil.Process(session.pid)
            proc.kill()
        except Exception:
            try:
                os.kill(session.pid, 9)
            except Exception:
                pass

    # Clean up user data dir
    import shutil
    user_data_dir = os.path.join(os.environ.get("TEMP", "/tmp"), f"orvima-session-{session.port}")
    try:
        shutil.rmtree(user_data_dir, ignore_errors=True)
    except Exception:
        pass

    return {"ok": True, "session_id": session_id, "destroyed": True}


@app.get("/api/sessions")
def list_sessions() -> dict:
    with _lock:
        sessions = list(_sessions.values())
    return {
        "ok": True,
        "sessions": [
            {
                "id": s.id,
                "cdp_url": s.cdp_url,
                "status": s.status,
                "remaining_seconds": max(0, int(s.expires - time.time())),
            }
            for s in sessions
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
