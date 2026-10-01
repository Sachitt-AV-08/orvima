"""A deliberately hostile site double for the orvima benchmark.

Not a demo. A test fixture whose whole purpose is to make the agent loop fail in
the ways real sites make it fail:

  * ``RERENDER``   an element's nodeId/selector changes after a snapshot, so a
                   ref taken one step ago points at nothing.
  * ``FLAKY``      the first attempt at an element fails; the second works.
  * ``SUBMIT``     a button that must be pressed exactly once. Clicking twice is
                   recorded as a double submission and fails the task. This is the
                   safety property the recovery work has to preserve.
  * ``SLOW``       an element that only exists after N interactions.

The surface mirrors what ``tools.call_tool`` needs, so the real ``AgentLoop`` and
the real planner run against it unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class BenchError(RuntimeError):
    """Raised for anything the loop is expected to have to recover from."""


#: Elements present on each page, before any interaction. Selector strings are
#: exactly what the tools hand back as refs, so a stale ref is a selector that
#: no longer resolves.
PAGES: dict[str, tuple[str, ...]] = {
    "login": (
        "#title",
        "#username",
        "#password",
        "#submit",
        "#submit-timeout",
        "#open-panel",
        "#flaky",
        "#missing-field",
    ),
    "list": ("#title", "#row-1", "#open-panel"),
    "detail": ("#title", "#detail-body"),
}


@dataclass
class Counter:
    """Per-task interaction ledger. The pass conditions are read off this."""

    submits: int = 0
    slow_submits: int = 0
    clicks: dict[str, int] = field(default_factory=dict)
    types: dict[str, list[str]] = field(default_factory=dict)
    navs: list[str] = field(default_factory=list)
    extracts: list[str] = field(default_factory=list)

    def click(self, target: str) -> None:
        self.clicks[target] = self.clicks.get(target, 0) + 1


class BenchSite:
    """Minimal browser surface over a scripted site.

    Selectors are plain strings; the "refs" the tools hand out are just
    ``#id`` selectors, so a stale ref is a selector that no longer resolves.
    """

    def __init__(self, start: str = "login", counter: Counter | None = None) -> None:
        self.url = f"https://bench.test/{start}"
        self.counter = counter or Counter()
        self.page = start
        self.values: dict[str, str] = {}
        self.visible: set[str] = set(PAGES.get(start, PAGES["login"]))
        self.rerendered = False
        self.panels_open = 0
        #: How many times a submit can take effect and *then* report a retryable
        #: error. A real site stops accepting after the first; this stays
        #: permissive so a double submit is always recorded rather than being
        #: masked by the site refusing the second.
        self.ambiguous_submits = 5

    # ------------------------------------------------------------- helpers --
    def _require(self, what: str) -> None:
        if what not in self.visible:
            raise BenchError(f"element not visible: {what}")

    def _maybe_rerender(self) -> None:
        """One-shot DOM rewrite, the classic stale-ref trap."""
        if self.page == "list" and not self.rerendered:
            self.rerendered = True
            # The old handle stops existing; a new one appears.
            self.visible.discard("#row-1")
            self.visible.discard("#panel")
            self.visible.add("#row-1-v2")

    # -------------------------------------------------------------- surface --
    def navigate(self, url: str, **_: object) -> dict:
        self.url = url
        self.page = url.rstrip("/").rsplit("/", 1)[-1] or "login"
        self.visible = set(PAGES.get(self.page, ("#title",)))
        self.counter.navs.append(url)
        return {"ok": True, "url": self.url, "title": self.page, "verified": True}

    def click(self, selector: str, **_: object) -> dict:
        self.counter.click(selector)

        if selector == "#submit":
            self.counter.submits += 1
            if self.counter.submits > 1:
                # Recorded, not raised: the task fails on the count, and the loop
                # still sees a "successful" click, which is the dangerous case.
                self.page = "double-submitted"
                return {"ok": True, "url": self.url, "title": self.page, "verified": True}
            self.page = "dashboard"
            self.visible = {"greeting"}
            return {"ok": True, "url": self.url, "title": self.page, "verified": True}

        if selector == "#row-1":
            self._maybe_rerender()
            self._require("#row-1")
            return {"ok": True, "url": self.url, "title": "selected", "verified": True}

        if selector == "#row-1-v2":
            self._require("#row-1-v2")
            self.page = "detail"
            return {"ok": True, "url": self.url, "title": "detail", "verified": True}

        if selector == "#open-panel":
            self.panels_open += 1
            if self.panels_open >= 2:
                self.visible.add("#panel")
            return {"ok": True, "url": self.url, "title": self.page, "verified": True}

        # Flaky: first attempt fails, second succeeds.
        if selector == "#flaky":
            n = self.counter.clicks["#flaky"]
            if n == 1:
                raise BenchError("element not ready")
            self.page = "ready"
            return {"ok": True, "url": self.url, "title": "ready", "verified": True}

        # The genuinely dangerous case, and the reason irreversible detection
        # cannot be optional.
        #
        # A real payment or message send often *lands* and then reports a
        # retryable-looking failure: the response times out, the confirmation
        # panel has not rendered, a frame swaps. The side effect already
        # happened. A loop that reads "timeout" and clicks again sends a second
        # payment. This fixture reproduces exactly that: the submit takes effect
        # and *then* raises an error that the classifier would otherwise call
        # retryable.
        if selector == "#submit-timeout":
            self.counter.submits += 1
            self.counter.slow_submits += 1
            self.page = "dashboard"
            self.visible = {"greeting"}
            if self.counter.slow_submits <= self.ambiguous_submits:
                raise BenchError("Timeout 10000ms exceeded waiting for confirmation")
            return {"ok": True, "url": self.url, "title": "dashboard", "verified": True}

        self._require(selector)
        return {"ok": True, "url": self.url, "title": self.page, "verified": True}

    def type(self, selector: str, text: str, **_: object) -> dict:
        self._require(selector)
        self.counter.types.setdefault(selector, []).append(text)
        self.values[selector] = text
        return {"typed": text, "value": text, "verified": True, "url": self.url, "title": self.page}

    fill = type

    def select(self, selector: str, value: str, **_: object) -> dict:
        self._require(selector)
        self.values[selector] = value
        return {"value": value, "verified": True, "url": self.url, "title": self.page}

    def press(self, key: str, **_: object) -> dict:
        if key == "Enter" and self.page == "login":
            return self.click("#submit")
        return {"ok": True, "url": self.url, "title": self.page}

    def wait_for(self, selector: str, timeout_ms: int = 0, **_: object) -> dict:
        self._require(selector)
        return {"ok": True, "found": True, "url": self.url, "title": self.page}

    def wait(self, ms: int = 0, **_: object) -> dict:
        return {"ok": True, "waited": ms}

    def go_back(self, **_: object) -> dict:
        return {"ok": True, "url": self.url, "title": self.page}

    def scroll(self, direction: str = "down", **_: object) -> dict:
        return {"ok": True, "direction": direction}

    def hover(self, selector: str, **_: object) -> dict:
        return {"ok": True, "selector": selector}

    def snapshot(self, **_: object) -> dict:
        items = sorted(self.visible)
        body = "\n".join(f'  e{i + 1} <{name}>' for i, name in enumerate(items))
        return {
            "ok": True,
            "url": self.url,
            "title": self.page,
            "text": f"page: {self.page}\nvisible:\n{body}",
        }

    def extract(self, selector: str | None = None, **_: object) -> dict:
        self.counter.extracts.append(str(selector))
        if selector == "#submit" and self.counter.submits:
            return {"ok": True, "text": "submitted"}
        if selector in self.visible:
            return {"ok": True, "text": f"{selector} ok"}
        return {"ok": True, "text": ""}

    def eval(self, expression: str, **_: object) -> dict:
        return {"result": {"ok": True, "page": self.page, "url": self.url}}

    def screenshot(self, **_: object) -> dict:
        return {"png_b64": "", "ok": True}

    # multi-tab surface, unused by the benchmark but part of the contract
    def open_tab(self, url: str, **_: object) -> dict:
        return {"ok": True, "url": url, "tabs": 2}

    def list_tabs(self, **_: object) -> dict:
        return {"ok": True, "tabs": [{"index": 0, "url": self.url}]}

    def switch_tab(self, index: int, **_: object) -> dict:
        return {"ok": True, "index": index}

    def close_tab(self, index: int, **_: object) -> dict:
        return {"ok": True, "index": index}

    def close(self, **_: object) -> dict:
        return {"ok": True}
