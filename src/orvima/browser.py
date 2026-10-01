"""The browser the agent lives in.

Two ways to reach "your browser":

* default — launch **your installed Chrome or MS Edge** with a persistent
  Orvima profile (~/.orvima/profile). Visible, headful, and your logins
  survive restarts; your everyday profile is never touched.
* ``--attach`` — connect over CDP to a browser that is *already running*
  (``orvima setup`` can start one), driving its real tabs and logins as-is.

Every op returns confirmation from the page itself (verify-first). ``snapshot``
renders a compact, LLM-friendly outline of the DOM so an agent can decide
without megabytes of HTML.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .errors import BrowserError

DEFAULT_PROFILE = str(Path.home() / ".orvima" / "profile")

# Playwright's default connect_over_cdp timeout is 180s. When another CDP client
# already owns the browser the handshake never completes, so that default turns a
# clear mistake into a silent three-minute freeze. Fail fast and say why instead.
DEFAULT_ATTACH_TIMEOUT_S = 10.0


def _attach_timeout_ms() -> int:
    """Bounded CDP attach budget, overridable with ORVIMA_ATTACH_TIMEOUT (seconds)."""
    raw = os.environ.get("ORVIMA_ATTACH_TIMEOUT")
    try:
        seconds = float(raw) if raw else DEFAULT_ATTACH_TIMEOUT_S
    except ValueError:
        seconds = DEFAULT_ATTACH_TIMEOUT_S
    if seconds <= 0:
        seconds = DEFAULT_ATTACH_TIMEOUT_S
    return int(seconds * 1000)


def _type_delay_ms() -> int:
    """Per-character typing delay, overridable with ORVIMA_TYPE_DELAY_MS.

    Defaults to 0: an agent pays this cost on every character it sends, and
    human-style pacing is the product layer's job (see parley's HumanPacing),
    not the browser driver's.
    """
    raw = os.environ.get("ORVIMA_TYPE_DELAY_MS")
    try:
        ms = float(raw) if raw else 0.0
    except ValueError:
        ms = 0.0
    return max(0, int(ms))


def _cdp_endpoint_alive(attach: str) -> bool:
    """True when something answers on the CDP HTTP endpoint."""
    if attach.startswith(("ws://", "wss://")):
        return True  # can't cheaply probe a websocket URL; let connect try
    base = attach.rstrip("/")
    url = f"{base}/json/version" if base.startswith("http") else attach
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - fixed loopback endpoint
            return resp.status < 500
    except urllib.error.HTTPError:
        return True  # something is listening, just not on this path
    except Exception:
        return False


def _cdp_page_sockets(attach: str) -> list[dict]:
    """List the open page targets on a CDP endpoint."""
    base = attach.rstrip("/")
    if not base.startswith("http"):
        return []
    try:
        with urllib.request.urlopen(f"{base}/json/list", timeout=3) as resp:  # noqa: S310
            targets = json.loads(resp.read().decode())
    except Exception:
        return []
    return [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def _page_socket_for(attach: str, hint: str) -> str:
    """Find a page target's own debugger socket.

    Browser-level ``connect_over_cdp`` enumerates and auto-attaches to every
    target before finishing its handshake, so against a real daily-driver profile
    (extension service workers, reCAPTCHA iframes, a dozen tabs) it never
    completes - measured past 90s with no other client attached. Connecting to a
    single page's socket skips that entirely and returns in milliseconds.

    Returns "" when no target matches, so the caller can fall back.
    """
    pages = _cdp_page_sockets(attach)
    if not pages:
        return ""
    if hint:
        hint_l = hint.lower()
        for target in pages:
            if hint_l in (target.get("url") or "").lower():
                return target["webSocketDebuggerUrl"]
            if hint_l in (target.get("title") or "").lower():
                return target["webSocketDebuggerUrl"]
        return ""
    return pages[0]["webSocketDebuggerUrl"]

_BROWSER_PATHS = {
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
    "msedge": (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ),
}

_OUTLINE_JS = """(() => {
  const out = [];
  const text = (el) => (el.innerText || "").trim().replace(/\\s+/g, " ").slice(0, 400);
  const role = (el) => {
    if (el.tagName === "A" || el.tagName === "BUTTON") return el.tagName.toLowerCase();
    return el.getAttribute("role") || "";
  };
  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  const items = document.querySelectorAll(
    "a,button,input,textarea,select,label,h1,h2,h3,h4,h5,h6,[role='button'],[role='link'],[role='textbox'],[aria-label]"
  );
  let idx = 0;
  for (const el of items) {
    if (!isVisible(el)) continue;
    idx++;
    const ref = "e" + idx;
    try { el.setAttribute("data-orvima-ref", ref); } catch (_) {}
    const r = role(el);
    const label = el.getAttribute("aria-label") || el.getAttribute("placeholder") ||
                  el.getAttribute("title") || (el.tagName === "LABEL" ? text(el) : "");
    const own = text(el);
    // Redact password values in snapshots
    const isPassword = el.type === "password";
    const rawVal = el.value !== undefined && el.value ? String(el.value).slice(0, 80) : "";
    const val = (el.value !== undefined && el.value)
        ? ` value=${JSON.stringify(isPassword ? "***" : rawVal)}`
        : "";
    const info = [r, label || own, val].filter(Boolean).join(" | ");
    if (info) {
      out.push({
        ref,
        tag: el.tagName.toLowerCase(),
        role: r,
        label: label || own,
        text: own,
        value: isPassword ? "***" : (el.value || ""),
      });
    }
    if (idx >= 60) break;
  }
  const body = document.body ? text(document.body) : "";
  const iframeCount = document.querySelectorAll("iframe").length;
  const shadowHosts = document.querySelectorAll("*[shadow-root]").length;
  return {
    url: location.href,
    title: document.title,
    items: out,
    body: body.slice(0, 3000),
    truncated: out.length >= 60,
    iframes: iframeCount ? iframeCount + " iframe(s) — not supported yet" : "none",
    shadowDom: shadowHosts ? shadowHosts + " shadow host(s) — not supported yet" : "none"
  };
})()
"""


def detect_channel() -> str | None:
    """Return 'chrome', 'msedge', or None (use bundled chromium)."""
    env = (os.environ.get("ORVIMA_BROWSER") or "").strip().lower()
    if env in ("chrome", "msedge", "chromium"):
        return None if env == "chromium" else env
    for name, candidates in _BROWSER_PATHS.items():
        if sys.platform == "win32" and any(Path(p).exists() for p in candidates):
            return name
    return None


class BrowserController:
    """Owns a browser + one active page, over Playwright."""

    def __init__(
        self,
        *,
        base_url: str = "https://example.com",
        headless: bool | None = None,
        profile_dir: str | None = None,
        attach: str | None = None,
        attach_tab: str | None = None,
    ):
        self._base_url = base_url
        env_headless = os.environ.get("ORVIMA_HEADLESS")
        if env_headless:
            self._headless = env_headless.lower() in ("1", "true", "yes")
        else:
            self._headless = headless
        self._profile_dir = profile_dir or os.environ.get("ORVIMA_PROFILE", DEFAULT_PROFILE)
        self._attach = attach or os.environ.get("ORVIMA_ATTACH", "") or None
        self._attach_tab = attach_tab or os.environ.get("ORVIMA_ATTACH_TAB", "") or ""
        self._channel = None if self._attach else detect_channel()
        self._context = None
        self.page = None
        self._pw = None
        self._closed = False

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            if self._attach:
                if not _cdp_endpoint_alive(self._attach):
                    raise BrowserError(
                        f"no browser is listening at {self._attach}. Start the browser with a "
                        f"debugging port (for example --remote-debugging-port=9334), or drop "
                        f"--attach to let orvima launch its own browser."
                    )
                timeout_ms = _attach_timeout_ms()
                page_ws = _page_socket_for(self._attach, self._attach_tab)
                if self._attach_tab and not page_ws:
                    open_tabs = ", ".join(
                        f"{(t.get('title') or t.get('url') or '?')[:40]}" for t in _cdp_page_sockets(self._attach)
                    )
                    raise BrowserError(
                        f"no open tab matches {self._attach_tab!r} in {self._attach}. "
                        f"Open tabs: {open_tabs or 'none'}"
                    )
                try:
                    # A page target's own socket skips browser-level target
                    # enumeration, which is what stalls on a busy real profile.
                    endpoint = page_ws or self._attach
                    browser = self._pw.chromium.connect_over_cdp(endpoint, timeout=timeout_ms)
                except Exception as exc:
                    if page_ws:
                        raise BrowserError(
                            f"could not attach to the {self._attach_tab!r} tab in "
                            f"{self._attach} within {timeout_ms // 1000}s: {exc}"
                        ) from exc
                    raise BrowserError(
                        f"could not attach to {self._attach} within {timeout_ms // 1000}s. The "
                        f"endpoint answered but the CDP browser handshake never completed. "
                        f"Chromium's connect_over_cdp enumerates and auto-attaches to every "
                        f"target, so a busy profile - extension service workers, reCAPTCHA "
                        f"iframes, many open tabs - can stall it indefinitely. Pass "
                        f"ORVIMA_ATTACH_TAB=<substring of the tab url or title> to attach to a "
                        f"single page instead, or let orvima launch its own browser."
                    ) from exc
                self._context = browser.contexts[0] if browser.contexts else None
                if self._context is None:
                    self._context = browser.new_context()
            elif self._channel:
                self._context = self._pw.chromium.launch_persistent_context(
                    self._profile_dir,
                    channel=self._channel,
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            else:
                self._context = self._pw.chromium.launch_persistent_context(
                    self._profile_dir,
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            pages = self._context.pages
            self.page = pages[0] if pages else self._context.new_page()
            self._goto(self._base_url)
        except BrowserError:
            self._teardown_playwright()
            raise  # already actionable - don't bury the real cause
        except Exception as exc:  # pragma: no cover - launch failures vary
            self._teardown_playwright()
            raise BrowserError(f"could not start a browser: {exc}") from exc

    def _teardown_playwright(self) -> None:
        """Stop the Playwright driver after a failed start.

        Without this, a failed start leaks the driver process *and* its asyncio
        loop. The next sync_playwright() start in the same process then fails
        with the misleading "you are using Playwright Sync API inside the asyncio
        loop" - so one failure cascades into unrelated ones.
        """
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # pragma: no cover - best effort
                pass
            self._pw = None
        self._context = None
        self.page = None

    def _goto(self, url: str) -> dict:
        self._require_open()
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"navigation failed: {exc}") from exc
        return self._state()

    def _state(self) -> dict:
        return {"url": self.page.url, "title": self.page.title()}

    def _dom_signature(self) -> str:
        """Signature of DOM state for click verification.

        Node count alone is not evidence: it changes on any unrelated mutation
        (ads, timers) and stays identical when a click only mutates attributes
        or text. This includes a text digest, so clicking something that updates
        a counter or swaps content is detected, while clicking inert elements is
        not.
        """
        try:
            parts = self.page.evaluate(
                """() => {
                  const body = document.body;
                  const text = (body && body.innerText) ? body.innerText.slice(0, 20000) : "";
                  let h = 0;
                  for (let i = 0; i < text.length; i++) {
                    h = (Math.imul(31, h) + text.charCodeAt(i)) | 0;
                  }
                  return {
                    url: location.href,
                    title: document.title,
                    nodes: document.querySelectorAll('*').length,
                    hash: h,
                  };
                }"""
            )
            return f"{parts['url']}|{parts['title']}|{parts['nodes']}|{parts['hash']}"
        except Exception:
            return ""

    def _read_value(self, selector: str) -> str | None:
        """Read a field's current value, whichever kind of element it is.

        `input_value()` only works on input/textarea/select, so contenteditable
        targets (rich editors, tiptap/ProseMirror composers) used to read back
        as a hard failure. Returns None only if the element can't be found.
        """
        try:
            return self.page.input_value(selector)
        except Exception:
            pass
        try:
            return self.page.inner_text(selector)
        except Exception:
            return None

    # ------------------------------------------------------------- actions ----
    def navigate(self, url: str) -> dict:
        self._goto(url)
        return {**self._state(), "load_state": "domcontentloaded", "verified": True}

    def click(self, selector: str) -> dict:
        self._require_open()
        before_sig = self._dom_signature()
        try:
            self.page.click(selector, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"click {selector!r} failed: {exc}") from exc
        after_sig = self._dom_signature()
        verified = before_sig != after_sig
        return {**self._state(), "verified": verified}

    def hover(self, selector: str) -> dict:
        try:
            self.page.hover(selector, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"hover {selector!r} failed: {exc}") from exc
        return self._state()

    def type(self, selector: str, text: str, delay_ms: int | None = None) -> dict:
        self._require_open()
        delay = _type_delay_ms() if delay_ms is None else max(0, int(delay_ms))
        try:
            self.page.click(selector, timeout=10000)
            self.page.keyboard.type(text, delay=delay)
        except Exception as exc:
            raise BrowserError(f"type into {selector!r} failed: {exc}") from exc
        value = self._read_value(selector)
        if value is None:
            raise BrowserError(f"typed into {selector!r} but could not read it back to verify")
        verified = value.strip() == text.strip()
        return {"typed": text, "value": value, "verified": verified, **self._state()}

    def fill(self, selector: str, text: str) -> dict:
        self._require_open()
        try:
            self.page.fill(selector, text, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"fill {selector!r} failed: {exc}") from exc
        value = self._read_value(selector)
        if value is None:
            raise BrowserError(f"filled {selector!r} but could not read it back to verify")
        verified = value.strip() == text.strip()
        return {"value": value, "verified": verified, **self._state()}

    def select(self, selector: str, value: str) -> dict:
        try:
            values = self.page.select_option(selector, value, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"select {selector!r}={value!r} failed: {exc}") from exc
        verified = value in (values or [])
        return {"selected": values, "verified": verified, **self._state()}

    def press(self, key: str) -> dict:
        try:
            self.page.keyboard.press(key)
        except Exception as exc:
            raise BrowserError(f"press {key!r} failed: {exc}") from exc
        return self._state()

    def go_back(self) -> dict:
        try:
            self.page.go_back()
        except Exception as exc:
            raise BrowserError(f"go_back failed: {exc}") from exc
        return self._state()

    def wait(self, ms: int = 500) -> dict:
        self.page.wait_for_timeout(ms)
        return self._state()

    def wait_for(self, selector: str, timeout_ms: int = 10000) -> dict:
        try:
            self.page.wait_for_selector(selector, timeout=timeout_ms)
        except Exception as exc:
            raise BrowserError(f"wait_for {selector!r} failed: {exc}") from exc
        return self._state()

    def scroll(self, direction: str = "down") -> dict:
        amount = "window.scrollBy(0, 800)" if direction == "down" else "window.scrollBy(0, -800)"
        self.eval(amount)
        return self._state()

    def eval(self, expression: str) -> dict:
        try:
            result = self.page.evaluate(expression)
        except Exception as exc:
            raise BrowserError(f"eval failed: {exc}") from exc
        return {"result": result, **self._state()}

    # ----------------------------------------------------------------- tabs ----
    def open_tab(self, url: str) -> dict:
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"new tab to {url!r} failed: {exc}") from exc
        self.page = page
        return {"tabs": len(self._tabs()), **self._state()}

    def list_tabs(self) -> dict:
        tabs = self._tabs()
        return {
            "tabs": [
                {"index": i, "url": p.url, "title": p.title(), "active": p is self.page}
                for i, p in enumerate(tabs)
            ]
        }

    def switch_tab(self, index: int) -> dict:
        tabs = self._tabs()
        try:
            self.page = tabs[int(index)]
        except (IndexError, ValueError) as exc:
            raise BrowserError(f"no tab at index {index!r}") from exc
        return {"index": int(index), **self._state()}

    def close_tab(self, index: int) -> dict:
        tabs = self._tabs()
        try:
            page = tabs[int(index)]
        except (IndexError, ValueError) as exc:
            raise BrowserError(f"no tab at index {index!r}") from exc
        if len(tabs) == 1:
            raise BrowserError("refusing to close the last tab")
        page.close()
        self.page = self._tabs()[0]
        return {"closed": int(index), "tabs": len(self._tabs()), **self._state()}

    def _tabs(self) -> list:
        return self._context.pages if self._context else []

    # --------------------------------------------------------------- reads ----
    def snapshot(self) -> dict:
        try:
            data = self.page.evaluate(_OUTLINE_JS)
        except Exception as exc:
            raise BrowserError(f"snapshot failed: {exc}") from exc
        return data

    def screenshot(self) -> dict:
        try:
            png = self.page.screenshot(type="png", full_page=False)
        except Exception as exc:
            raise BrowserError(f"screenshot failed: {exc}") from exc
        return {"png_b64": base64.b64encode(png).decode("ascii")}

    def extract(self, selector: str) -> dict:
        try:
            el = self.page.locator(selector).first
            text = el.inner_text() if el.count() else ""
        except Exception as exc:
            raise BrowserError(f"extract {selector!r} failed: {exc}") from exc
        return {"text": text, "selector": selector, **self._state()}

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # pragma: no cover
            pass
        self._teardown_playwright()
        self._closed = True

    def _require_open(self) -> None:
        """Fail loudly and usefully if the controller was already closed.

        Without this, any action on a closed controller surfaces Playwright's
        cryptic "Event loop is closed! Is Playwright already stopped?", which
        reads like an internal bug rather than a lifecycle mistake.
        """
        if self._closed:
            raise BrowserError(
                "this browser controller is closed - construct a new one and call start() "
                "(restarting on a closed controller is not supported)"
            )
        if self.page is None:
            raise BrowserError("no active page - call start() first")

    # Context manager protocol for sync `with` statement
    def __enter__(self) -> BrowserController:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
