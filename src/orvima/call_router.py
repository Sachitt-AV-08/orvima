"""call_router: route incoming calls to errands recipes based on speech.

Wraps errands' recipe matching into a call-aware routing layer.
"""

from __future__ import annotations

import os
from pathlib import Path

from .errands.recipes import load_dir


def _load_call_recipes(recipe_dir: str = "") -> list:
    d = recipe_dir or os.environ.get("ORVIMA_CALL_RECIPES", "")
    if not d:
        for candidate in [
            Path(__file__).resolve().parents[2] / "call_recipes",
            Path.home() / ".orvima" / "call_recipes",
        ]:
            if candidate.is_dir():
                d = str(candidate)
                break
    if not d:
        return []
    try:
        return load_dir(d)
    except Exception:
        return []


def route_call_intent(text: str, recipe_dir: str = "") -> dict:
    """Match caller speech to a call recipe.

    Returns the matched recipe name, steps, and confidence if found.
    Returns refused dict if no recipe matches.
    """
    recipes = _load_call_recipes(recipe_dir)
    if not recipes:
        return {"ok": False, "refused": True, "reason": "no call recipes loaded", "text": text}

    text_lower = text.lower()
    best_match = None
    best_score = 0.0

    for recipe in recipes:
        for trigger in recipe.triggers:
            if trigger.lower() in text_lower:
                score = len(trigger) / max(len(text_lower), 1)
                if score > best_score:
                    best_score = score
                    best_match = recipe

    if best_match is None or best_score < (best_match.match_threshold * 0.3):
        return {
            "ok": False,
            "refused": True,
            "reason": f"no call recipe matches: {text!r}",
            "text": text,
            "available": [r.name for r in recipes],
        }

    steps = []
    for s in best_match.steps:
        steps.append({
            "id": s.id,
            "tool": s.tool,
            "args": s.args,
            "intent": s.intent,
            "gated": s.gated,
        })

    return {
        "ok": True,
        "text": text,
        "recipe": best_match.name,
        "description": best_match.description,
        "confidence": round(best_score, 3),
        "steps": steps,
        "step_count": len(steps),
    }


def list_call_recipes(recipe_dir: str = "") -> dict:
    """List available call recipes."""
    recipes = _load_call_recipes(recipe_dir)
    out = []
    for r in recipes:
        out.append({
            "name": r.name,
            "triggers": list(r.triggers),
            "description": r.description,
            "tags": list(r.tags),
            "step_count": len(r.steps),
        })
    return {"ok": True, "count": len(out), "recipes": out}


CALL_ROUTER_TOOLS = (
    route_call_intent,
    list_call_recipes,
)
