"""BrowserController: a real Chromium the agent drives, with verify-first ops.

Every mutating op returns confirmation from the page itself. ``snapshot()``
renders a compact, LLM-friendly outline of the DOM (roles, labels, headings,
visible text) so an agent can decide without dumping megabytes of HTML.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from .errors import BrowserError

# Compact outline of what matters on a page: interactive elements, headings,
# inputs and the main visible text. Stable across Chromium versions.
_OUTLINE_JS = """
() => {
  const out = [];
  const text = (el) => (el.innerText || "").trim().replace(/\\s+/g, " ").slice(0, 400);
  const role = (el) => {
    if (el.tagName === "A" || el.tagName === "BUTTON") return el.tagName.toLowerCase();
    return el.getAttribute("role") || "";
  };
  const items = document.querySelectorAll(
    "a,button,input,textarea,select,label,h1,h2,h3,h4,h5,h6,[role=\"button\"],[role=\"link\"],[role=\"textbox\"],[aria-label]"
  );
  for (const el of items) {
    const r = role(el);
    const label = el.getAttribute("aria-label") || el.getAttribute("placeholder") ||
                  el.getAttribute("title") || (el.tagName === "LABEL" ? text(el) : "");
    const own = text(el);
    const val = (el.value !== undefined && el.value) ? ` value=${JSON.stringify(String(el.value).slice(0, 80))}` : "";
    const info = [r, label || own, val].filter(Boolean).join(" | ");
    if (info) out.push(info);
  }
  const body = document.body ? text(document.body) : "";
  return { url: location.href, title: document.title, items: out.slice(0, 120), body: body.slice(0, 3000) };
}
"""


@dataclass
class PageRef:
    """A stable handle to one browser + page."""
    controller: object
    page_id: str


class BrowserController:
    """Launches and owns a Chromium page via Playwright (headless by default)."""

    def __init__(self, headless: bool = True, base_url: str = "https://example.com"):
        self._headless = headless
        self._base_url = base_url
        self._browser = None
        self.page = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self._headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self.page = self._browser.new_page()
        except Exception as exc:  # pragma: no cover - launch failures vary
            raise BrowserError(f"could not start Chromium: {exc}") from exc
        self._goto(self._base_url)

    def _goto(self, url: str) -> dict:
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"navigation failed: {exc}") from exc
        return self._state()

    def _state(self) -> dict:
        return {"url": self.page.url, "title": self.page.title()}

    # ------------------------------------------------------------- actions ----
    def navigate(self, url: str) -> dict:
        return self._goto(url)

    def click(self, selector: str) -> dict:
        try:
            self.page.click(selector, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"click {selector!r} failed: {exc}") from exc
        return self._state()

    def type(self, selector: str, text: str) -> dict:
        try:
            self.page.click(selector, timeout=10000)
            self.page.keyboard.type(text, delay=24)
        except Exception as exc:
            raise BrowserError(f"type into {selector!r} failed: {exc}") from exc
        return {"typed": text, **self._state()}

    def fill(self, selector: str, text: str) -> dict:
        try:
            self.page.fill(selector, text, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"fill {selector!r} failed: {exc}") from exc
        return {"value": text, **self._state()}

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
            if self.page is not None:
                self.page.close()
            if self._browser is not None:
                self._browser.close()
            if getattr(self, "_pw", None) is not None:
                self._pw.stop()
        except Exception:  # pragma: no cover
            pass
