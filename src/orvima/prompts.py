"""MCP prompts: prepared workflows the client can invoke by name.

Each prompt is a function returning a prompt template. The template may include
placeholders like {goal}, {url}, {selector} that the client fills in before
sending it to the model. This keeps the agent's reasoning structured while
still letting it adapt to the live page.
"""

from __future__ import annotations

from typing import Any

PROMPTS: dict[str, dict[str, Any]] = {
    "orvima/verify-action": {
        "name": "orvima/verify-action",
        "title": "Verify an action actually did what you expected",
        "description": (
            "Run a tool, then snapshot and extract the specific thing you expected "
            "to change. Returns a compact verdict. Use this instead of trusting "
            "ok: true — the whole point of Orvima is that it re-reads the DOM."
        ),
        "arguments": [
            {
                "name": "action_tool",
                "description": "The browse_* tool to run (e.g. browse_click, browse_fill)",
                "required": True,
            },
            {
                "name": "action_args",
                "description": "Arguments for that tool (selector/ref/text etc)",
                "required": True,
            },
            {
                "name": "expectation",
                "description": "What you expect to see change (e.g. 'cart count becomes 1', 'modal closes')",
                "required": True,
            },
            {
                "name": "selector_or_ref",
                "description": "Selector or ref of the element to read after the action",
                "required": True,
            },
        ],
    },
    "orvima/extract-table": {
        "name": "orvima/extract-table",
        "title": "Extract a table from the current page as structured data",
        "description": (
            "Snapshot the page, find the table by selector, then extract rows and "
            "cells into a JSON array. Handles pagination by defaulting to the first "
            "page — pass continue=true to fetch more."
        ),
        "arguments": [
            {
                "name": "selector",
                "description": "CSS selector for the <table> element (or its container)",
                "required": True,
            },
            {
                "name": "continue",
                "description": "Whether to paginate (not implemented yet — reserved)",
                "required": False,
            },
        ],
    },
    "orvima/read-article": {
        "name": "orvima/read-article",
        "title": "Read the main article content from a news/blog page",
        "description": (
            "Navigate to a URL, strip boilerplate (nav, ads, sidebars), and return "
            "the article text. Uses browse_extract on common article selectors with "
            "a fallback to the full body text."
        ),
        "arguments": [
            {
                "name": "url",
                "description": "The article URL to read",
                "required": True,
            },
        ],
    },
    "orvima/compare-prices": {
        "name": "orvima/compare-prices",
        "title": "Compare prices on two product pages",
        "description": (
            "Open two URLs, extract the price from each using a selector, and return "
            "a simple comparison. Useful for flight/hotel/shopping checks."
        ),
        "arguments": [
            {
                "name": "url_a",
                "description": "First product URL",
                "required": True,
            },
            {
                "name": "url_b",
                "description": "Second product URL",
                "required": True,
            },
            {
                "name": "selector",
                "description": "CSS selector for the price element on both pages",
                "required": True,
            },
        ],
    },
    "orvima/submit-form": {
        "name": "orvima/submit-form",
        "title": "Fill and submit a form with verification",
        "description": (
            "Navigate to a page, fill fields by selector/ref, submit, then verify "
            "the result (success message, redirect, confirmation number). The gate "
            "will hold the submit if it looks destructive."
        ),
        "arguments": [
            {
                "name": "url",
                "description": "Page containing the form",
                "required": True,
            },
            {
                "name": "fields",
                "description": "Array of {selector, value} pairs to fill",
                "required": True,
            },
            {
                "name": "submit_selector",
                "description": "Selector for the submit button",
                "required": True,
            },
            {
                "name": "expectation",
                "description": "What success looks like (e.g. 'order number appears')",
                "required": True,
            },
        ],
    },
    "orvima/wait-and-extract": {
        "name": "orvima/wait-and-extract",
        "title": "Wait for an element to appear, then extract its text",
        "description": (
            "Polls for a selector (with browse_wait_for), then extracts text. Useful "
            "for dynamic content that loads after a click or navigation."
        ),
        "arguments": [
            {
                "name": "selector",
                "description": "Selector to wait for and then extract",
                "required": True,
            },
            {
                "name": "timeout_ms",
                "description": "Maximum time to wait (default 10000)",
                "required": False,
            },
        ],
    },
}


def get_prompt(name: str) -> dict[str, Any] | None:
    """Return the prompt definition, or None if not found."""
    return PROMPTS.get(name)


def list_prompts() -> list[dict[str, Any]]:
    """Return all prompt definitions for the MCP list_prompts handler."""
    return list(PROMPTS.values())
