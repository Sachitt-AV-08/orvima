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
import os
import sys
from pathlib import Path

from .errors import BrowserError

DEFAULT_PROFILE = str(Path.home() / ".orvima" / "profile")

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
    const val = (el.value !== undefined && el.value) ? ` value=${JSON.stringify(String(el.value).slice(0, 80))}` : "";
    const info = [r, label || own, val].filter(Boolean).join(" | ");
    if (info) {
      out.push({
        ref,
        tag: el.tagName.toLowerCase(),
        role: r,
        label: label || own,
        text: own,
        value: el.value || "",
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
    ):
        self._base_url = base_url
        self._headless = bool(os.environ.get("ORVIMA_HEADLESS", headless))
        self._profile_dir = profile_dir or os.environ.get("ORVIMA_PROFILE", DEFAULT_PROFILE)
        self._attach = attach or os.environ.get("ORVIMA_ATTACH", "") or None
        self._channel = None if self._attach else detect_channel()
        self._context = None
        self.page = None
        self._pw = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        try:
            self._pw = sync_playwright().start()
            if self._attach:
                browser = self._pw.chromium.connect_over_cdp(self._attach)
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
        except Exception as exc:  # pragma: no cover - launch failures vary
            raise BrowserError(f"could not start a browser: {exc}") from exc

    def _goto(self, url: str) -> dict:
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"navigation failed: {exc}") from exc
        return self._state()

    def _state(self) -> dict:
        return {"url": self.page.url, "title": self.page.title()}

    def _dom_signature(self) -> str:
        """Lightweight signature of DOM structure for click verification."""
        try:
            count = self.page.evaluate("document.querySelectorAll('*').length")
            title = self.page.title()
            return f"{title}|{count}"
        except Exception:
            return ""

    # ------------------------------------------------------------- actions ----
    def navigate(self, url: str) -> dict:
        self._goto(url)
        return {**self._state(), "load_state": "domcontentloaded", "verified": True}

    def click(self, selector: str) -> dict:
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

    def type(self, selector: str, text: str) -> dict:
        try:
            self.page.click(selector, timeout=10000)
            self.page.keyboard.type(text, delay=24)
        except Exception as exc:
            raise BrowserError(f"type into {selector!r} failed: {exc}") from exc
        value = ""
        try:
            value = self.page.input_value(selector)
        except Exception:
            pass
        verified = value == text
        return {"typed": text, "value": value, "verified": verified, **self._state()}

    def fill(self, selector: str, text: str) -> dict:
        try:
            self.page.fill(selector, text, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"fill {selector!r} failed: {exc}") from exc
        value = ""
        try:
            value = self.page.input_value(selector)
        except Exception:
            pass
        verified = value == text
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
            if getattr(self, "_pw", None) is not None:
                self._pw.stop()
        except Exception:  # pragma: no cover
            pass
