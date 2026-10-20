"""router_* tools: errands recipe matching for goal routing.

Wraps errands' recipe loader and matcher into Orvima's dict-in/dict-out contract.
Goals that match a reviewed recipe are routed; unknown goals are refused.
"""

from __future__ import annotations

import os
from pathlib import Path

from .errands.recipes import load_dir

# Default recipe directory: bundled recipes or ORVIMA_RECIPES env var
_DEFAULT_RECIPE_DIR = os.environ.get("ORVIMA_RECIPES", "")


def _load_recipes(recipe_dir: str = "") -> list:
    d = recipe_dir or _DEFAULT_RECIPE_DIR
    if not d:
        # Try default locations
        for candidate in [
            Path(__file__).resolve().parents[2] / "recipes",
            Path.home() / ".orvima" / "recipes",
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


def goal_list_recipes(recipe_dir: str = "") -> dict:
    """List all available errand recipes (name, triggers, description, tags)."""
    recipes = _load_recipes(recipe_dir)
    out = []
    for r in recipes:
        out.append({
            "name": r.name,
            "triggers": list(r.triggers),
            "description": r.description,
            "tags": list(r.tags),
            "match_threshold": r.match_threshold,
            "step_count": len(r.steps),
        })
    return {"ok": True, "count": len(out), "recipes": out}


def goal_route(goal: str, recipe_dir: str = "") -> dict:
    """Match a goal to a reviewed recipe or refuse.

    Returns the matched recipe name, steps, and confidence if a match is found.
    Returns {"ok": False, "refused": True, "reason": ...} if no recipe matches.
    """
    recipes = _load_recipes(recipe_dir)
    if not recipes:
        return {"ok": False, "refused": True, "reason": "no recipes loaded", "goal": goal}

    # Simple keyword matching against triggers
    goal_lower = goal.lower()
    best_match = None
    best_score = 0.0

    for recipe in recipes:
        triggers = [t.lower() for t in recipe.triggers]
        # Check if any trigger is a substring of the goal
        for trigger in triggers:
            if trigger in goal_lower:
                score = len(trigger) / max(len(goal_lower), 1)
                if score > best_score:
                    best_score = score
                    best_match = recipe

    if best_match is None or best_score < best_match.match_threshold * 0.3:
        return {
            "ok": False,
            "refused": True,
            "reason": f"no recipe matches goal {goal!r}; refusing to plan",
            "goal": goal,
            "available_recipes": [r.name for r in recipes],
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
        "goal": goal,
        "recipe": best_match.name,
        "description": best_match.description,
        "confidence": round(best_score, 3),
        "steps": steps,
        "step_count": len(steps),
    }


ROUTER_TOOLS = (
    goal_list_recipes,
    goal_route,
)
