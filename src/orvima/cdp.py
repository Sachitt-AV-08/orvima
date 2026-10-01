"""Drive a tab that is already open, over raw CDP.

Why this exists
---------------
Playwright can only attach to a browser as a whole: ``connect_over_cdp`` against
the browser endpoint enumerates and auto-attaches to *every* target before its
handshake finishes. On a real daily-driver profile - extension service workers,
reCAPTCHA iframes, a dozen tabs - that never completes. Measured on Brave with
18 targets: still hanging at 90s with no other client attached.

Connecting to a single page's own debugger socket skips the enumeration and
returns in milliseconds, but Playwright then hands back a context with no pages
and refuses to create one (``Target.createBrowserContext: Not allowed``), so its
high-level API is unusable there.

So this module speaks CDP to one page socket directly. It is deliberately small:
the operations an agent actually needs, with real waits, and nothing that fakes
success. Only ``127.0.0.1`` is accepted.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time
import urllib.request

MAX_FRAME = 100 * 1024 * 1024


class CDPError(RuntimeError):
    """A CDP command failed, or the page socket is unusable."""


def list_page_targets(endpoint: str) -> list[dict]:
    """Open page targets on a CDP HTTP endpoint, newest-listed first."""
    base = endpoint.rstrip("/")
    if not base.startswith("http"):
        return []
    try:
        with urllib.request.urlopen(f"{base}/json/list", timeout=3) as resp:  # noqa: S310
            targets = json.loads(resp.read().decode())
    except Exception as exc:
        raise CDPError(f"could not list targets on {base}: {exc}") from exc
    return [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def find_page_socket(endpoint: str, hint: str = "") -> str:
    """Return the debugger socket of an open page.

    ``hint`` matches against the tab's url first, then its title. An empty hint
    takes the first page.
    """
    pages = list_page_targets(endpoint)
    if not pages:
        raise CDPError(f"no open page targets on {endpoint} - is a browser running with that port?")
    if not hint:
        return pages[0]["webSocketDebuggerUrl"]
    low = hint.lower()
    for t in pages:
        if low in (t.get("url") or "").lower():
            return t["webSocketDebuggerUrl"]
    for t in pages:
        if low in (t.get("title") or "").lower():
            return t["webSocketDebuggerUrl"]
    listing = ", ".join((t.get("title") or t.get("url") or "?")[:40] for t in pages)
    raise CDPError(f"no open tab matches {hint!r}. Open tabs: {listing}")


class PageSocket:
    """A minimal RFC 6455 client for one page's CDP socket."""

    def __init__(self, ws_url: str, timeout: float = 30.0) -> None:
        if not ws_url.startswith(("ws://127.0.0.1", "ws://localhost")):
            raise CDPError(f"refusing non-loopback CDP socket: {ws_url}")
        self.ws_url = ws_url
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 0

    # ------------------------------------------------------------- plumbing --
    def connect(self) -> PageSocket:
        _, rest = self.ws_url.split("://", 1)
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        sock = socket.create_connection((host, int(port)), timeout=self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall(
            (
                f"GET /{path} HTTP/1.1\r\n"
                f"Host: {hostport}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk:
                raise CDPError("socket closed during websocket handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise CDPError(f"websocket handshake refused: {head.split(chr(13).encode())[0]!r}")
        self._sock = sock
        return self

    def _send_frame(self, payload: str) -> None:
        data = payload.encode()
        if len(data) > MAX_FRAME:
            raise CDPError(f"payload too large: {len(data)} bytes")
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            header = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 65536:
            header = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self._sock.sendall(header + mask + masked)

    def _read_exact(self, n: int) -> bytes:
        out = bytearray()
        while len(out) < n:
            chunk = self._sock.recv(min(65536, n - len(out)))
            if not chunk:
                raise CDPError("page closed the CDP connection")
            out.extend(chunk)
        return bytes(out)

    def _read_frame(self) -> tuple[int, bytes]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if length > MAX_FRAME:
            raise CDPError(f"frame too large: {length}")
        return opcode, self._read_exact(length)

    # ---------------------------------------------------------------- calls --
    def call(self, method: str, params: dict | None = None, timeout: float | None = None):
        """Send one CDP command and return its result, matching on id.

        Frames that arrive while waiting are events, not replies; they are
        dropped. If the page navigates mid-call the socket dies, and that surfaces
        as a CDPError rather than a silent wrong answer.
        """
        if self._sock is None:
            raise CDPError("socket is not connected")
        self._next_id += 1
        msg_id = self._next_id
        self._send_frame(json.dumps({"id": msg_id, "method": method, "params": params or {}}))

        previous = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(timeout)
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        try:
            while time.monotonic() < deadline:
                opcode, data = self._read_frame()
                if opcode == 0x8:
                    raise CDPError(f"page closed the connection while waiting for {method}")
                if opcode not in (0x1, 0x2):
                    continue  # ping/pong/continuation we do not use
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") != msg_id:
                    continue  # an event, or a stale reply
                if "error" in msg:
                    err = msg["error"]
                    raise CDPError(f"{method} failed: {err.get('message', err)}")
                return msg.get("result", {})
        except TimeoutError as exc:
            raise CDPError(f"timed out waiting for {method} ({timeout or self.timeout:.0f}s)") from exc
        finally:
            self._sock.settimeout(previous)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self) -> PageSocket:
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()


class CDPPage:
    """Page-level operations over a :class:`PageSocket`.

    Everything here reports what it actually observed. ``eval`` returns the real
    JS result, ``wait_for`` polls until the element exists or the deadline
    passes, and nothing returns a success value for work it did not confirm.
    """

    def __init__(self, endpoint: str, tab_hint: str = "", timeout: float = 30.0) -> None:
        self.endpoint = endpoint
        self.tab_hint = tab_hint
        self._timeout = timeout
        self._sock: PageSocket | None = None

    def open(self) -> CDPPage:
        ws = find_page_socket(self.endpoint, self.tab_hint)
        self._sock = PageSocket(ws, timeout=self._timeout).connect()
        for domain in ("Page", "Runtime", "DOM"):
            self._sock.call(f"{domain}.enable")
        return self

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> CDPPage:
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def socket(self) -> PageSocket:
        if self._sock is None:
            raise CDPError("page is not open - use it as a context manager or call open()")
        return self._sock

    # ---------------------------------------------------------------- basics --
    def goto(self, url: str, timeout: float | None = None) -> str:
        self.socket.call("Page.navigate", {"url": url}, timeout=timeout or self._timeout)
        self.wait_ready(timeout=timeout or self._timeout)
        return self.url()

    def eval(self, expression: str, await_promise: bool = False):
        """Evaluate a JS expression and return its value."""
        res = self.socket.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "userGesture": True,
            },
        )
        if res.get("exceptionDetails"):
            detail = res["exceptionDetails"]
            text = (detail.get("exception") or {}).get("description") or detail.get("text", "")
            raise CDPError(f"JS threw: {text}")
        return res.get("result", {}).get("value")

    def url(self) -> str:
        return self.eval("location.href") or ""

    def title(self) -> str:
        return self.eval("document.title") or ""

    # ----------------------------------------------------------------- waits --
    def wait_ready(self, timeout: float = 30.0, settle_s: float = 0.5) -> None:
        """Wait for document.readyState to settle, then a short breather for SPAs."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.eval("document.readyState") in ("interactive", "complete"):
                break
            time.sleep(0.2)
        time.sleep(settle_s)

    def wait_for(self, selector: str, timeout_s: float = 10.0, visible: bool = True) -> bool:
        """True if the selector appears (and is visible) before the deadline."""
        import json as _json

        deadline = time.monotonic() + timeout_s
        expr = (
            f"(() => {{ const el = document.querySelector({_json.dumps(selector)});"
            f" if (!el) return false;"
            f" const r = el.getBoundingClientRect();"
            f" return {'r.width > 0 && r.height > 0' if visible else 'true'}; }})()"
        )
        while time.monotonic() < deadline:
            try:
                if self.eval(expr):
                    return True
            except CDPError:
                pass  # mid-navigation; keep polling until the deadline
            time.sleep(0.25)
        return False

    # -------------------------------------------------------------- actions --
    def click(self, selector: str) -> bool:
        """Click via JS. Reports whether the element was there to click."""
        import json as _json

        return bool(
            self.eval(
                f"(() => {{ const el = document.querySelector({_json.dumps(selector)});"
                " if (!el) return false; el.click(); return true; })()"
            )
        )

    def focus(self, selector: str) -> bool:
        import json as _json

        return bool(
            self.eval(
                f"(() => {{ const el = document.querySelector({_json.dumps(selector)});"
                " if (!el) return false; el.focus(); return true; })()"
            )
        )

    def insert_text(self, text: str) -> None:
        """Type text into whatever is focused.

        ``Input.insertText`` is one call for the whole string, so a long post
        costs the same as a short one. Some editors need real key events; fall
        back to those if nothing lands.
        """
        self.socket.call("Input.insertText", {"text": text})
        if self.eval("(() => { const a = document.activeElement;"
                     " return a ? (a.innerText || a.value || '') : ''; })()") in (None, ""):
            for ch in text:
                self.socket.call("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch})
                self.socket.call("Input.dispatchKeyEvent", {"type": "keyUp", "text": ch})

    def set_file_input(self, selector: str, files: list[str]) -> None:
        """Attach files to a file input without an OS file chooser."""

        doc = self.socket.call("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
        found = self.socket.call("DOM.querySelector", {"nodeId": doc, "selector": selector})
        node_id = found.get("nodeId")
        if not node_id:
            raise CDPError(f"no file input matched {selector!r}")
        self.socket.call("DOM.setFileInputFiles", {"files": files, "nodeId": node_id})

    def screenshot(self, fmt: str = "png", full_page: bool = False) -> bytes:
        params: dict = {"format": fmt}
        if full_page:
            params["captureBeyondViewport"] = True
        return base64.b64decode(self.socket.call("Page.captureScreenshot", params)["data"])

