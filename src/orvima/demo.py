"""DemoBrowser: a scripted, in-memory page so orvima runs offline and in CI.

It implements the same operation surface as BrowserController with a tiny
fictional site ("acme.dev") so every tool, the agent loop and the UI can be
written and tested without Chromium or internet access. A keystroke log
records what the agent did, which doubles as the demo transcript.
"""

from __future__ import annotations

from .errors import BrowserError

_PAGES = {
    "https://acme.dev": {
        "title": "Acme Hardware",
        "items": ["button | Products", "a | Contact", "h1 | Acme Hardware",
                  "label | Search our store", "input | search-box"],
        "body": ("Acme Hardware sells bolts, anchors and brick-and-mortar wisdom. "
                 "Known for same-day shipping and a courteous support team."),
    },
    "https://acme.dev/products": {
        "title": "Products — Acme Hardware",
        "items": ["a | Bolt M8 x 40mm", "a | Anchor HD 200", "a | Braid Cutter 3000",
                  "button | Add to cart", "button | Sort by price"],
        "body": ("Products: Bolt M8 x 40mm, Anchor HD 200, Braid Cutter 3000. "
                 "All in stock. Free shipping over $50."),
    },
    "https://acme.dev/contact": {
        "title": "Contact — Acme Hardware",
        "items": ["input | name", "input | email", "textarea | message",
                  "button | Send message", "a | Back to home"],
        "body": ("Write to Acme support. Typical response time under two hours."),
    },
}

_LINKS = [
    ("Products", "https://acme.dev/products"),
    ("Contact", "https://acme.dev/contact"),
    ("product", "https://acme.dev/products"),
]


class DemoBrowser:
    """Deterministic stand-in for BrowserController (same method names)."""

    def __init__(self, base_url: str = "https://acme.dev"):
        self._url = base_url
        self._history: list[str] = []
        self._tabs: list[str] = []
        self._active = 0
        self.log: list[str] = []
        self.sent: list[dict] = []
        self._form: dict = {}

    @property
    def page(self) -> None:
        return None  # kept so callers that reach for `.page` don't crash

    def _state(self) -> dict:
        return {"url": self._url, "title": _PAGES.get(self._url, _PAGES["https://acme.dev"])["title"]}

    def navigate(self, url: str) -> dict:
        if url not in _PAGES and "acme.dev" not in url:
            url = "https://acme.dev"  # unknown page folds back to home
        self._history.append(self._url)
        self._url = url
        self.log.append(f"navigate {url}")
        return self._state()

    def click(self, selector: str) -> dict:
        for label, target in _LINKS:
            if label.lower() in selector.lower() and target != self._url:
                self._url = target
                break
        self.log.append(f"click {selector}")
        if selector.lower().find("add to cart") >= 0:
            self.sent.append({"action": "cart", "url": self._url})
        return self._state()

    def hover(self, selector: str) -> dict:
        self.log.append(f"hover {selector}")
        return self._state()

    def type(self, selector: str, text: str) -> dict:
        self.log.append(f"type {selector} = {text!r}")
        return {"typed": text, **self._state()}

    def fill(self, selector: str, text: str) -> dict:
        self._form[selector] = text
        self.log.append(f"fill {selector} = {text!r}")
        return {"value": text, **self._state()}

    def select(self, selector: str, value: str) -> dict:
        self._form[selector] = value
        self.log.append(f"select {selector} = {value!r}")
        return {"selected": [value], "value": value, **self._state()}

    def wait_for(self, selector: str, timeout_ms: int = 10000) -> dict:
        self.log.append(f"wait_for {selector}")
        return self._state()

    def open_tab(self, url: str) -> dict:
        if url not in _PAGES:
            url = "https://acme.dev"
        self._tabs.append(self._url)
        self._url = url
        self._active = len(self._tabs) - 1
        self.log.append(f"open_tab {url}")
        return {"tabs": len(self._tabs) + 1, **self._state()}

    def list_tabs(self) -> dict:
        urls = self._tabs + [self._url]
        return {
            "tabs": [
                {"index": i, "url": u, "title": _PAGES[u]["title"], "active": i == len(urls) - 1}
                for i, u in enumerate(urls)
            ]
        }

    def switch_tab(self, index: int) -> dict:
        idx = int(index)
        if idx < 0 or idx > len(self._tabs):
            raise BrowserError(f"no tab at index {index!r}")
        urls = self._tabs + [self._url]
        self._url = urls[idx]
        self._active = idx
        self.log.append(f"switch_tab {idx}")
        return {"index": idx, **self._state()}

    def close_tab(self, index: int) -> dict:
        idx = int(index)
        if len(self._tabs) + 1 <= 1 or idx < 0 or idx >= len(self._tabs) + 1:
            raise BrowserError("refusing to close the last tab")
        self._tabs.pop(idx)
        self._active = min(self._active, len(self._tabs) - 1)
        self._url = self._tabs[self._active] if self._tabs else "https://acme.dev"
        self.log.append(f"close_tab {idx}")
        return {"closed": idx, "tabs": len(self._tabs) + 1, **self._state()}

    def press(self, key: str) -> dict:
        if key.lower() == "enter":
            self._submit()
        self.log.append(f"press {key}")
        return self._state()

    def _submit(self) -> None:
        if self._url == "https://acme.dev/contact" and self._form:
            self.sent.append({"action": "message", "form": dict(self._form)})
            self._form = {}
            self.log.append("submit message form")

    def go_back(self) -> dict:
        if self._history:
            self._url = self._history.pop()
        self.log.append("go_back")
        return self._state()

    def wait(self, ms: int = 500) -> dict:
        self.log.append(f"wait {ms}ms")
        return self._state()

    def scroll(self, direction: str = "down") -> dict:
        self.log.append(f"scroll {direction}")
        return self._state()

    def eval(self, expression: str) -> dict:
        self.log.append(f"eval {expression!r}")
        return {"result": "ok", **self._state()}

    def snapshot(self) -> dict:
        page = _PAGES.get(self._url, _PAGES["https://acme.dev"])
        return {"url": self._url, "title": page["title"], "items": list(page["items"]), "body": page["body"]}

    def screenshot(self) -> dict:
        # A tiny colored PNG so the UI always has a real frame (demo mode).
        import struct
        import zlib

        w = h = 8
        px = b"\x0f\x22\x3a" * (w * h)
        raw = b"".join(b"\x00" + px[y * w * 3 : (y + 1) * w * 3] for y in range(h))
        png = (
            b"\x89PNG\r\n\x1a\n"
            + self._chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + self._chunk(b"IDAT", zlib.compress(raw))
            + self._chunk(b"IEND", b"")
        )
        import base64

        return {"png_b64": base64.b64encode(png).decode("ascii")}

    @staticmethod
    def _chunk(kind: bytes, data: bytes) -> bytes:
        import struct
        import zlib

        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    def extract(self, selector: str) -> dict:
        page = _PAGES.get(self._url, _PAGES["https://acme.dev"])
        text = page["body"] if "body" in selector.lower() else page["title"]
        return {"text": text, "selector": selector, **self._state()}

    def close(self) -> None:  # pragma: no cover - nothing to free
        pass
