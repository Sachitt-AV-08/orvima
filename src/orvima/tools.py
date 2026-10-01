"""browse_* tools: the whole automation surface, as plain dict-in/dict-out
functions over any object that acts like BrowserController/DemoBrowser.

Writing them this way keeps the MCP server, the HTTP API and the agent loop
on one tested contract, and lets docs/agent-visible docstrings be exact.
"""

from __future__ import annotations

import re

from .errors import BrowserError

REF_RE = re.compile(r"^(?:f\d+:)?e\d+$")


def _resolve(browser, ref: str | None, selector: str | None) -> str:
    """Resolve a ref or selector to a CSS selector the browser understands.

    - If ``ref`` is given, it must match ``e<number>`` on the main document, or
      ``f<frame>:e<number>`` inside a frame, and is converted to
      ``[data-orvima-ref="eN"]`` which works on the real browser and is
      intercepted by DemoBrowser for scripted navigation.
    - If only ``selector`` is given, it is passed through unchanged.
    - Exactly one of ``ref`` or ``selector`` must be provided.
    """
    if ref is not None and selector is not None:
        raise BrowserError("provide either 'ref' or 'selector', not both")
    if ref is not None:
        if not REF_RE.match(ref):
            raise BrowserError(f"invalid ref {ref!r} — expected e.g. e12")
        return f'[data-orvima-ref="{ref}"]'
    if selector is None:
        raise BrowserError("provide 'ref' or 'selector'")
    return selector


def _candidates(browser):
    """Return a list of candidate elements from a fresh snapshot for error recovery."""
    try:
        snap = browser.snapshot()
        return snap.get("items", [])[:10]
    except Exception:
        return []


def _error(exc, candidates=None):
    """Build a structured error dict with optional recovery candidates."""
    msg = str(exc)
    err = {"ok": False, "error": msg}
    if candidates:
        err["candidates"] = candidates
        err["error_type"] = "not_found"
    return err


def tool_browse_navigate(browser, url: str) -> dict:
    """Open a URL. Waits for the page to be interactive and returns URL + title."""
    try:
        return {"ok": True, **browser.navigate(url)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_click(browser, selector: str | None = None, ref: str | None = None) -> dict:
    """Click an element by CSS selector OR stable ref (e.g. 'e12' from snapshot).

    Prefer refs — they survive DOM churn. Returns ``verified: true`` if the
    click caused a navigation or DOM mutation; otherwise ``verified: false``.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.click(sel)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_hover(browser, selector: str | None = None, ref: str | None = None) -> dict:
    """Hover an element by selector or ref."""
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.hover(sel)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_select(browser, value: str, selector: str | None = None, ref: str | None = None) -> dict:
    """Pick an option in a <select> by value or label, using selector or ref."""
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.select(sel, value)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_wait_for(browser, selector: str | None = None, ref: str | None = None, timeout_ms: int = 10000) -> dict:
    """Wait until an element matching selector or ref exists."""
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.wait_for(sel, timeout_ms)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_type(browser, text: str, selector: str | None = None, ref: str | None = None) -> dict:
    """Type text into a field at a human-ish pace, by selector or ref.

    Returns the field's actual value after typing and ``verified``.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.type(sel, text)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_fill(browser, text: str, selector: str | None = None, ref: str | None = None) -> dict:
    """Replace the value of a field wholesale, by selector or ref.

    Returns the field's actual value and ``verified``.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.fill(sel, text)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_press(browser, key: str) -> dict:
    """Press a keyboard key, e.g. Enter, Escape, Tab, ArrowDown."""
    try:
        return {"ok": True, **browser.press(key)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_go_back(browser, *_args, **_kw) -> dict:
    """Go back one page in history."""
    try:
        return {"ok": True, **browser.go_back()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_wait(browser, ms: int = 400) -> dict:
    """Pause briefly (e.g. after a submit or before a snapshot)."""
    try:
        return {"ok": True, **browser.wait(int(ms))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_scroll(browser, direction: str = "down") -> dict:
    """Scroll the viewport: 'down' or 'up'."""
    try:
        return {"ok": True, **browser.scroll(direction)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_snapshot(browser, *_args, **_kw) -> dict:
    """Describe the current page: URL, title, interactive elements and visible text.

    Compact and LLM-friendly — prefer this over dump_html. Use it after every
    action to confirm the result before reporting success.
    """
    try:
        data = browser.snapshot()
        return {"ok": True, **data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_screenshot(browser, *_args, **_kw) -> dict:
    """Return the current page screenshot as base64 PNG (for the UI and humans)."""
    try:
        return {"ok": True, **browser.screenshot()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_extract(browser, selector: str | None = None, ref: str | None = None) -> dict:
    """Extract text from the first element matching a selector or ref."""
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.extract(sel)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_eval(browser, expression: str) -> dict:
    """Run a small JS expression in the page (read-only where possible)."""
    try:
        return {"ok": True, **browser.eval(expression)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------- tabs ----
def tool_browse_open_tab(browser, url: str) -> dict:
    """Open a URL in a new tab and switch to it."""
    try:
        return {"ok": True, **browser.open_tab(url)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_list_tabs(browser, *_args, **_kw) -> dict:
    """List open tabs with index, url and which one is active."""
    try:
        return {"ok": True, **browser.list_tabs()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_switch_tab(browser, index: int) -> dict:
    """Switch to another open tab by its list index."""
    try:
        return {"ok": True, **browser.switch_tab(index)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_close_tab(browser, index: int) -> dict:
    """Close a tab by index (never the last remaining one)."""
    try:
        return {"ok": True, **browser.close_tab(index)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


TOOLS = (
    tool_browse_navigate,
    tool_browse_click,
    tool_browse_hover,
    tool_browse_select,
    tool_browse_wait_for,
    tool_browse_type,
    tool_browse_fill,
    tool_browse_press,
    tool_browse_go_back,
    tool_browse_wait,
    tool_browse_scroll,
    tool_browse_snapshot,
    tool_browse_screenshot,
    tool_browse_extract,
    tool_browse_eval,
    tool_browse_open_tab,
    tool_browse_list_tabs,
    tool_browse_switch_tab,
    tool_browse_close_tab,
)

TOOL_NAMES = {fn.__name__[5:] for fn in TOOLS}


def call_tool(browser, name: str, args: dict) -> dict:
    """Dispatch ``name`` to the right browse_* function (unknown -> ok: False)."""
    fn = next((f for f in TOOLS if f.__name__ == f"tool_{name}"), None)
    if fn is None:
        from .errors import ToolNotFoundError

        raise ToolNotFoundError(f"unknown tool {name!r}; have {sorted(TOOL_NAMES)}")
    return fn(browser, **args)
