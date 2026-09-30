"""browse_* tools: the whole automation surface, as plain dict-in/dict-out
functions over any object that acts like BrowserController/DemoBrowser.

Writing them this way keeps the MCP server, the HTTP API and the agent loop
on one tested contract, and lets docs/agent-visible docstrings be exact.
"""

from __future__ import annotations


def tool_navigate(browser, url: str) -> dict:
    """Open a URL. Waits for the page to be interactive and returns URL + title."""
    try:
        return {"ok": True, **browser.navigate(url)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_click(browser, selector: str) -> dict:
    """Click the first element matching a CSS selector or Playwright locator."""
    try:
        return {"ok": True, **browser.click(selector)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_hover(browser, selector: str) -> dict:
    """Hover the first element matching a selector (reveals menus/tooltips)."""
    try:
        return {"ok": True, **browser.hover(selector)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_select(browser, selector: str, value: str) -> dict:
    """Pick an option in a <select> dropdown by value or label."""
    try:
        return {"ok": True, **browser.select(selector, value)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_wait_for(browser, selector: str, timeout_ms: int = 10000) -> dict:
    """Wait until an element matching a selector exists (e.g. after a submit)."""
    try:
        return {"ok": True, **browser.wait_for(selector, timeout_ms)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_type(browser, selector: str, text: str) -> dict:
    """Type text into a field at a human-ish pace (after focusing it)."""
    try:
        return {"ok": True, **browser.type(selector, text)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_fill(browser, selector: str, text: str) -> dict:
    """Replace the value of a field wholesale."""
    try:
        return {"ok": True, **browser.fill(selector, text)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_press(browser, key: str) -> dict:
    """Press a keyboard key, e.g. Enter, Escape, Tab, ArrowDown."""
    try:
        return {"ok": True, **browser.press(key)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_go_back(browser, *_args, **_kw) -> dict:
    """Go back one page in history."""
    try:
        return {"ok": True, **browser.go_back()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_wait(browser, ms: int = 400) -> dict:
    """Pause briefly (e.g. after a submit or before a snapshot)."""
    try:
        return {"ok": True, **browser.wait(int(ms))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_scroll(browser, direction: str = "down") -> dict:
    """Scroll the viewport: 'down' or 'up'."""
    try:
        return {"ok": True, **browser.scroll(direction)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_snapshot(browser, *_args, **_kw) -> dict:
    """Describe the current page: URL, title, interactive elements and visible text.

    Compact and LLM-friendly — prefer this over dump_html. Use it after every
    action to confirm the result before reporting success.
    """
    try:
        data = browser.snapshot()
        return {"ok": True, **data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_screenshot(browser, *_args, **_kw) -> dict:
    """Return the current page screenshot as base64 PNG (for the UI and humans)."""
    try:
        return {"ok": True, **browser.screenshot()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_extract(browser, selector: str) -> dict:
    """Extract text from the first element matching a selector."""
    try:
        return {"ok": True, **browser.extract(selector)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_eval(browser, expression: str) -> dict:
    """Run a small JS expression in the page (read-only where possible)."""
    try:
        return {"ok": True, **browser.eval(expression)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------- tabs ----
def tool_open_tab(browser, url: str) -> dict:
    """Open a URL in a new tab and switch to it."""
    try:
        return {"ok": True, **browser.open_tab(url)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_list_tabs(browser, *_args, **_kw) -> dict:
    """List open tabs with index, url and which one is active."""
    try:
        return {"ok": True, **browser.list_tabs()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_switch_tab(browser, index: int) -> dict:
    """Switch to another open tab by its list index."""
    try:
        return {"ok": True, **browser.switch_tab(index)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_close_tab(browser, index: int) -> dict:
    """Close a tab by index (never the last remaining one)."""
    try:
        return {"ok": True, **browser.close_tab(index)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


TOOLS = (
    tool_navigate,
    tool_click,
    tool_hover,
    tool_select,
    tool_wait_for,
    tool_type,
    tool_fill,
    tool_press,
    tool_go_back,
    tool_wait,
    tool_scroll,
    tool_snapshot,
    tool_screenshot,
    tool_extract,
    tool_eval,
    tool_open_tab,
    tool_list_tabs,
    tool_switch_tab,
    tool_close_tab,
)

TOOL_NAMES = {fn.__name__[5:] for fn in TOOLS}


def call_tool(browser, name: str, args: dict) -> dict:
    """Dispatch ``name`` to the right browse_* function (unknown -> ok: False)."""
    fn = next((f for f in TOOLS if f.__name__ == f"tool_{name}"), None)
    if fn is None:
        from .errors import ToolNotFoundError

        raise ToolNotFoundError(f"unknown tool {name!r}; have {sorted(TOOL_NAMES)}")
    return fn(browser, **args)
