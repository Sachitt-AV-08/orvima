"""browse_* tools: the whole automation surface, as plain dict-in/dict-out
functions over any object that acts like BrowserController/DemoBrowser.

Writing them this way keeps the MCP server, the HTTP API and the agent loop
on one tested contract, and lets docs/agent-visible docstrings be exact.
"""

from __future__ import annotations

import re

from .errors import BrowserError
from .expectations import DEFAULT_EXPECT_TIMEOUT_MS

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


#: The keys an action accepts as an expectation, in the order they are passed.
_EXPECT_KEYS = ("expect_url", "expect_text", "expect_count", "expect_timeout_ms")


def _expect_kwargs(**given) -> dict:
    """Only the expectations the caller actually stated.

    Passing the rest as None would change the call for every caller that uses no
    expectations, and would break any browser implementation that has not adopted
    them - including DemoBrowser, which is a shipped class rather than a test
    double. "No expectation given" must mean "behave exactly as before", so an
    absent expectation is not forwarded at all.
    """
    out = {k: v for k, v in given.items() if v is not None}
    # A timeout or a count target on their own is meaningless, and forwarding
    # either alone would make an implementation that does not know the option
    # fail for no stated reason.
    if not any(k in out for k in ("expect_url", "expect_text", "expect_count")):
        return {}
    return out


def _error(exc, candidates=None):
    """Build a structured error dict with optional recovery candidates."""
    msg = str(exc)
    err = {"ok": False, "error": msg}
    if candidates:
        err["candidates"] = candidates
        err["error_type"] = "not_found"
    return err


def tool_browse_navigate(
    browser,
    url: str,
    expect_url: str | None = None,
    expect_text: str | None = None,
    expect_timeout_ms: int = DEFAULT_EXPECT_TIMEOUT_MS,
) -> dict:
    """Open a URL. Waits for the page to be interactive and returns URL + title.

    Optional ``expect_url`` / ``expect_text`` state what the page should look like
    once it has loaded. If one is given and does not come true within
    ``expect_timeout_ms``, the call fails with the mismatch rather than reporting
    a successful navigation - which is how a redirect to a login page or the
    wrong account goes unnoticed. Omit them for today's behaviour.

    The check is the same on every backend, real browser or offline. A backend
    that cannot read the page it claims to have reached reports ``verified:
    false`` rather than ``verified: true``.
    """
    try:
        return {
            "ok": True,
            **browser.navigate(
                url,
                **_expect_kwargs(
                    expect_url=expect_url,
                    expect_text=expect_text,
                    expect_timeout_ms=expect_timeout_ms,
                )
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_click(
    browser,
    selector: str | None = None,
    ref: str | None = None,
    expect_url: str | None = None,
    expect_text: str | None = None,
    expect_count: int | None = None,
    expect_for: str | None = None,
    expect_timeout_ms: int = DEFAULT_EXPECT_TIMEOUT_MS,
) -> dict:
    """Click an element by CSS selector OR stable ref (e.g. 'e12' from snapshot).

    Prefer refs — they survive DOM churn. Returns ``verified: true`` if the
    click caused a navigation or DOM mutation; otherwise ``verified: false``.

    That check only asks whether *something* changed, which a click on the wrong
    element can pass. To judge the click against intent instead, state what you
    expected:

    - ``expect_url`` - a substring the resulting url must contain
    - ``expect_text`` - a substring the resulting page must show
    - ``expect_count`` - the exact number of matching elements afterwards, and
      ``expect_for`` a selector to count (default: the element you clicked)

    All optional and all polled for up to ``expect_timeout_ms``, since the
    result of a click is often asynchronous. If any expectation is unmet the
    call fails and names every mismatch, rather than reporting success.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {
            "ok": True,
            **browser.click(
                sel,
                **_expect_kwargs(
                    expect_url=expect_url,
                    expect_text=expect_text,
                    expect_count=expect_count,
                    expect_for=expect_for,
                    expect_timeout_ms=expect_timeout_ms,
                )
            ),
        }
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


def tool_browse_eval(browser, expression: str, reason: str | None = None) -> dict:
    """Run a JS expression in the page. An escape hatch, not a sandbox.

    Use this only when no purpose-built tool fits - the tools cover clicks,
    typing, frames and shadow DOM, and reaching for this first hides bugs that a
    normal action would have surfaced.

    State ``reason``: it is recorded in an audit trail alongside the expression,
    because an agent that can run arbitrary JS on a logged-in page needs a record
    of what it ran and why.

    Two things are enforced rather than promised:

    - An expression that looks irreversible (a delete, a payment, a form submit)
      is refused **before it runs**, using the same classifier that protects a
      click. The previous version of this docstring claimed "read-only where
      possible" and nothing enforced it.
    - ``mutating`` reports whether the expression actually changed the page, from
      a before/after DOM signature - so "read-only" is measured, not assumed.
    """
    try:
        return {"ok": True, **browser.eval(expression, reason=reason)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_eval_audit(browser, *_args, **_kw) -> dict:
    """Everything browse_eval has run this session: expression, reason, effect.

    Newest last. Read this after any eval to see exactly what ran.
    """
    try:
        return {"ok": True, **browser.eval_audit_trail()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def tool_browse_download(browser, selector: str | None = None, ref: str | None = None,
                         timeout_ms: int = 15000) -> dict:
    """Click something that downloads a file, and save it locally.

    Returns ``savedTo``, ``filename`` and ``bytes``. Files go to
    ``~/.orvima/downloads`` unless ``ORVIMA_DOWNLOAD_DIR`` says otherwise.

    Fails explicitly when no download starts. That is not a rare edge case - an
    expired link, a permission prompt or a session timeout all look exactly like
    a working click - so this never reports success on a click alone.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.download(sel, timeout_ms=timeout_ms)}
    except Exception as exc:
        return _error(exc, _candidates(browser))


def tool_browse_set_files(browser, paths: list[str], selector: str | None = None,
                          ref: str | None = None) -> dict:
    """Attach files to an ``<input type=file>``.

    ``paths`` are local file paths. Returns ``pageSaw`` - what the page's own
    FileList ended up holding - because attaching the wrong file silently is how
    a resume goes out with someone else's CV.

    Fails if a path does not exist or the target is not a file input. It will not
    guess, and it will not attach an empty selection.
    """
    try:
        sel = _resolve(browser, ref, selector)
        return {"ok": True, **browser.set_files(sel, list(paths or []))}
    except Exception as exc:
        return _error(exc, _candidates(browser))


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
    tool_browse_eval_audit,
    tool_browse_download,
    tool_browse_set_files,
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
