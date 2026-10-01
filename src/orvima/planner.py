"""Step planners: decide *the next single action* from goal + what happened.

The loop in :mod:`orvima.agent` calls ``decide`` after every step with a
history of tool calls/results plus the last page snapshot, until the planner
says ``{"done": true, "summary": "..."}`` (or max_steps is hit). This makes
the agent genuinely adaptive: it re-plans from what the page actually shows,
so it can do *anything on the web*, not just pre-scripted flows.
"""

from __future__ import annotations

import json
import os
import re

from . import tools
from .agent import _redact_sensitive
from .context import render_transcript

MAX_SNAPSHOT_ITEMS = 40
MAX_SNAPSHOT_BODY = 1200


class Planner:
    """Interface: return one action or a done-summary per call."""

    def decide(self, goal: str, history: list[dict]) -> dict:
        raise NotImplementedError

    @staticmethod
    def toolset() -> str:
        return ", ".join(sorted(tools.TOOL_NAMES))


class DemoPlanner(Planner):
    """Deterministic offline planner over the acme.dev simulator."""

    def decide(self, goal: str, history: list[dict]) -> dict:
        g = goal.lower()
        if any(k in g for k in ("contact", "message", "support", "email")):
            plan = [
                {"tool": "browse_navigate", "args": {"url": "https://acme.dev/contact"}},
                {"tool": "browse_fill", "args": {"selector": "input[name=name]", "text": "Orvima"}},
                {"tool": "browse_fill", "args": {"selector": "input[name=email]", "text": "hello@orvima.dev"}},
                {"tool": "browse_fill", "args": {"selector": "textarea[name=message]", "text": goal}},
                {"tool": "browse_click", "args": {"selector": "button:has-text('Send')"}},
                {"tool": "browse_wait", "args": {"ms": 400}},
                {"tool": "browse_snapshot", "args": {}},
                {"tool": "browse_list_tabs", "args": {}},
            ]
        elif any(k in g for k in ("product", "bolt", "anchor", "shop", "cutter", "price")):
            plan = [
                {"tool": "browse_navigate", "args": {"url": "https://acme.dev/products"}},
                {"tool": "browse_snapshot", "args": {}},
                {"tool": "browse_extract", "args": {"selector": "body"}},
                {"tool": "browse_open_tab", "args": {"url": "https://acme.dev"}},
                {"tool": "browse_list_tabs", "args": {}},
                {"tool": "browse_switch_tab", "args": {"index": 0}},
            ]
        else:
            plan = [
                {"tool": "browse_navigate", "args": {"url": "https://acme.dev"}},
                {"tool": "browse_snapshot", "args": {}},
            ]
        idx = len([h for h in history if h.get("kind") == "tool"])
        if idx >= len(plan):
            return {"done": True, "summary": "Finished the offline demo run."}
        return {"tool": plan[idx]["tool"], "args": plan[idx]["args"]}


def planner_for(mode: str) -> Planner:
    if mode == "demo":
        return DemoPlanner()
    base = os.environ.get("ORVIMA_LLM_BASE")
    key = os.environ.get("ORVIMA_LLM_KEY")
    model = os.environ.get("ORVIMA_LLM_MODEL", "gpt-4o-mini")
    if not (base and key):
        raise RuntimeError(
            "real-mode planning needs an LLM: set ORVIMA_LLM_BASE, ORVIMA_LLM_KEY "
            "(any OpenAI-compatible endpoint — OpenAI, OpenRouter, Groq, or local "
            "Ollama at http://localhost:11434/v1), or drive Orvima via MCP instead."
        )
    return LLMPlanner(base=base, key=key, model=model)


class LLMPlanner(Planner):
    """What actually makes Orvima 'do anything': an LLM reads the latest snapshot
    and history and names the next single tool call or says it is done."""

    def __init__(self, *, base: str, key: str, model: str):
        self._url = base.rstrip("/") + "/chat/completions"
        self._key = key
        self._model = model

    _SYSTEM = (
        "You are the step-planner for Orvima, a self-hosted browser agent. "
        "Given the goal, the running history, and a snapshot of the current page, "
        "return ONLY one JSON object with either "
        '{"tool": "<name>", "args": {...}} (one action to execute now) or '
        '{"done": true, "summary": "short result"} once the goal is met or safely '
        "impossible. Rules: prefer snapshot over dump_html; after mutating a page "
        "(click/submit) wait before verifying; one action per step; never invent "
        "selectors that are not in the snapshot or history — snapshot first if "
        "unsure; keep working until done."
    )

    def decide(self, goal: str, history: list[dict]) -> dict:
        import httpx

        messages = [
            {"role": "system", "content": self._SYSTEM + "\nTools: " + self.toolset()},
            {"role": "user", "content": f"Goal: {goal}"},
        ]
        transcript, last_snapshot = self._render(history)
        if transcript:
            messages.append({"role": "user", "content": "History:\n" + transcript})
        if last_snapshot:
            messages.append({"role": "user", "content": "Current page snapshot:\n" + last_snapshot})

        resp = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._key}"},
            json={"model": self._model, "temperature": 0, "messages": messages},
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return self._parse(content)

    @classmethod
    def _parse(cls, content: str) -> dict:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.S)
            if not match:
                raise RuntimeError(f"planner returned no JSON: {content[:200]!r}") from None
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise RuntimeError("planner did not return a JSON object")
        if parsed.get("done"):
            return {"done": True, "summary": str(parsed.get("summary", "done"))}
        tool = parsed.get("tool")
        if not tool or tool not in tools.TOOL_NAMES:
            raise RuntimeError(f"planner named unknown tool {tool!r}")
        return {"tool": tool, "args": parsed.get("args") or {}}

    @staticmethod
    def _render(history: list[dict]) -> tuple[str, str]:
        """Render history into a bounded transcript, plus the current page.

        The transcript goes through :mod:`orvima.context` so a long run has a
        bounded prompt instead of one that grows until something upstream
        truncates it silently. Redaction is applied there.

        The snapshot lookup used to test ``row["tool"] == "snapshot"``. No such
        tool exists - it is ``browse_snapshot`` - so ``last_snapshot`` was always
        empty and the ``if last_snapshot:`` guard below meant the planner was
        **never sent the current page at all**. It re-planned from the goal and
        its own history, blind. Nothing caught it: the only test touching this
        module called ``_parse``, and every end-to-end test uses a scripted
        planner that does not render anything.

        Matched on the result's shape as well as its name, so a renamed tool
        cannot silently disable this again.
        """
        last_snapshot = ""
        for row in reversed(history or []):
            if row.get("kind") != "tool":
                continue
            result = row.get("result") or {}
            if (
                result.get("ok")
                and row.get("tool") in {"snapshot", "browse_snapshot"}
                and result.get("items") is not None
            ):
                # Redacted before rendering, like every other page content that
                # leaves the process.
                last_snapshot = LLMPlanner._snapshot_text(_redact_sensitive(result))
                break
        return render_transcript(history, redact=_redact_sensitive), last_snapshot

    @staticmethod
    def _snapshot_text(result: dict) -> str:
        """The current page, in the shape a planner can act on.

        Bounded on purpose: items are capped at MAX_SNAPSHOT_ITEMS and body text
        at MAX_SNAPSHOT_BODY. A long page must not be able to crowd out the
        goal and the recent history.
        """
        items = result.get("items") or []
        body = result.get("body") or ""
        parts = [f"  URL: {result.get('url', '')}", f"  Title: {result.get('title', '')}"]
        if items:
            parts.append("  Elements: " + " | ".join(str(i) for i in items[:MAX_SNAPSHOT_ITEMS]))
        if body:
            parts.append("  Text: " + body[:MAX_SNAPSHOT_BODY])
        return "\n".join(parts)


def response_ok(data: dict) -> bool:
    """Convenience guard used by tests (kept importable without cycling)."""
    return data.get("ok") is True
