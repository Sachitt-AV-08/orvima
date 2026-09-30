"""Optional LLM planner: turns a goal into a list of browse_* steps.

Only used when ORVIMA_LLM_BASE + ORVIMA_LLM_KEY are set. Anything that speaks
an OpenAI-compatible /chat/completions API works (OpenAI, OpenRouter, local
Ollama, LM Studio, Groq, ...). falls back to the scripted demo planner
otherwise.
"""

from __future__ import annotations

import json

import httpx

from . import tools

_SYSTEM = (
    "You are the planner inside Orvima, a self-hosted browser agent. "
    f"Return ONLY JSON: a list of steps to reach the goal. Each step is "
    f'{{"tool": "<name>", "args": {{...}}}}. Available tools: {sorted(tools.TOOL_NAMES)}. '
    "Do one action per step, keep steps small, and always end with a "
    '"snapshot" step to verify. After mutating a page (submit/click), add a '
    '"wait" step before verifying. Never invent selectors seen in the last '
    "snapshot of available elements; if unsure, snapshot first."
)


def llm_plan(goal: str, *, base: str, key: str, model: str) -> list[dict]:
    url = base.rstrip("/") + "/chat/completions"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": goal},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    try:
        steps = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("["), content.rfind("]")
        steps = json.loads(content[start : end + 1])
    if not isinstance(steps, list):
        raise RuntimeError("planner did not return a list of steps")
    return steps
