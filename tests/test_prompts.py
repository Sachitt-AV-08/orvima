"""Tests for orvima.prompts module."""

from orvima.prompts import get_prompt, list_prompts


def test_list_prompts():
    result = list_prompts()
    assert isinstance(result, (list, dict))


def test_get_prompt_valid():
    prompts = list_prompts()
    if isinstance(prompts, list) and prompts:
        name = prompts[0] if isinstance(prompts[0], str) else prompts[0].get("name", "")
        if name:
            result = get_prompt(name)
            assert result is not None


def test_get_prompt_invalid():
    result = get_prompt("nonexistent_prompt_xyz")
    assert result is None or isinstance(result, (str, dict))