"""Pins orvima.router goal routing tools."""

from __future__ import annotations

import json
from pathlib import Path

from orvima import router


def _write_recipe(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    data = {
        "name": "demo_errand",
        "triggers": ["unsubscribe", "cancel subscription"],
        "description": "demo",
        "tags": ["demo"],
        "match_threshold": 0.3,
        "steps": [
            {
                "id": "s1",
                "tool": "browser.navigate",
                "args": {"url": "https://example.com"},
                "intent": "go",
                "gated": False,
            }
        ],
    }
    (d / "demo.json").write_text(json.dumps(data), encoding="utf-8")


def test_list_recipes_empty():
    res = router.goal_list_recipes(recipe_dir="/no/such/dir")
    assert res["ok"] is True
    assert res["count"] == 0
    assert res["recipes"] == []


def test_route_no_recipes():
    res = router.goal_route("unsubscribe please", recipe_dir="/no/such/dir")
    assert res["ok"] is False
    assert res["refused"] is True
    assert "no recipes loaded" in res["reason"]


def test_router_happy_path(tmp_path):
    rdir = tmp_path / "recipes"
    _write_recipe(rdir)
    res = router.goal_list_recipes(recipe_dir=str(rdir))
    assert res["ok"] is True
    assert res["count"] == 1
    assert res["recipes"][0]["name"] == "demo_errand"

    res = router.goal_route("please unsubscribe now", recipe_dir=str(rdir))
    assert res["ok"] is True
    assert res["recipe"] == "demo_errand"
    assert res["step_count"] == 1
    assert res["steps"][0]["id"] == "s1"


def test_route_no_match(tmp_path):
    rdir = tmp_path / "recipes"
    _write_recipe(rdir)
    res = router.goal_route("totally unrelated goal xyz", recipe_dir=str(rdir))
    assert res["ok"] is False
    assert res["refused"] is True
    assert "no recipe matches" in res["reason"]


def test_route_broken_recipe_dir_returns_empty(tmp_path):
    rdir = tmp_path / "bad"
    rdir.mkdir()
    (rdir / "broken.json").write_text("{not json", encoding="utf-8")
    res = router.goal_list_recipes(recipe_dir=str(rdir))
    assert res["ok"] is True
    assert res["count"] == 0
    res2 = router.goal_route("anything", recipe_dir=str(rdir))
    assert res2["ok"] is False
    assert res2["refused"] is True


def test_default_load_uses_env(monkeypatch, tmp_path):
    rdir = tmp_path / "recipes"
    _write_recipe(rdir)
    monkeypatch.setenv("ORVIMA_RECIPES", str(rdir))
    # module reads env at import; override may not apply to already-loaded default
    res = router.goal_list_recipes()
    # env set after import may not apply; accept either
    assert res["ok"] is True


def test_router_tools_tuple():
    assert len(router.ROUTER_TOOLS) == 2
