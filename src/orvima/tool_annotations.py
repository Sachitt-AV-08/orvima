"""Per-tool MCP annotations, derived from what each handler actually does.

m8ven's review flagged `orvima` as exposing one tool with no annotations, and
OpenAI's directory rejects tools where any of the four hints are missing or
non-boolean. The values here are not inferred from names: each was read off the
handler in `tools.py`, and the reasoning is recorded per tool so a later edit can
tell whether the hint still matches the code.

The four hints mean:

- `read_only_hint`    the call cannot change remote or local state
- `destructive_hint`  the call can delete, spend, send, or submit
- `idempotent_hint`   repeating it is safe and has no additional effect
- `open_world_hint`   the call reaches systems the user did not name up front
  (the open web, or any site whose content is attacker-influenced)

`browse_eval` is the interesting one and is deliberately not read-only: it runs
arbitrary JavaScript on a logged-in page, so it can do anything a script can do,
and its own docstring calls it "an escape hatch, not a sandbox". Marking it
read-only would be the single most misleading annotation in the set.
"""

from __future__ import annotations

from typing import NamedTuple


class ToolBehaviour(NamedTuple):
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool
    why: str


# Read-only: nothing is sent and nothing is stored.
# Destructive: can submit, spend, send, or delete.
# Idempotent: repeating reaches the same state, rather than compounding.
# Open world: the response is a live third-party page.
_BEHAVIOUR: dict[str, ToolBehaviour] = {
    "browse_snapshot": ToolBehaviour(
        True, False, True, True,
        "reads the accessibility tree and text; writes nothing to the page",
    ),
    "browse_extract": ToolBehaviour(
        True, False, True, True,
        "reads text from the page; writes nothing to the page",
    ),
    "browse_screenshot": ToolBehaviour(
        True, False, True, True,
        "renders the viewport to an image; writes nothing to the page",
    ),
    "browse_list_tabs": ToolBehaviour(
        True, False, True, False,
        "reads orvima's own tab list; touches no remote system",
    ),
    "browse_hover": ToolBehaviour(
        True, False, True, True,
        "moves the pointer, which can fire hover handlers but submits nothing",
    ),
    "browse_wait": ToolBehaviour(
        True, False, True, False,
        "sleeps; cannot affect any system",
    ),
    "browse_wait_for": ToolBehaviour(
        True, False, True, True,
        "polls for a selector until it appears; writes nothing",
    ),
    # Navigation changes browser state and reaches an untrusted site, but a
    # GET does not submit a purchase. Idempotent in effect, not in request:
    # repeating it re-fetches, which servers may treat as a new request.
    "browse_navigate": ToolBehaviour(
        False, False, False, True,
        "changes the current page and loads a URL the caller did not verify",
    ),
    "browse_go_back": ToolBehaviour(
        False, False, False, True,
        "changes history and re-requests a page; not safely repeatable",
    ),
    "browse_open_tab": ToolBehaviour(
        False, False, False, True,
        "creates a tab and loads a URL; changes browser state",
    ),
    "browse_close_tab": ToolBehaviour(
        False, False, True, False,
        "closes a tab, discarding its state; not repeatable once gone",
    ),
    "browse_switch_tab": ToolBehaviour(
        False, False, True, False,
        "changes which tab is active; a repeat is a no-op",
    ),
    "browse_scroll": ToolBehaviour(
        False, False, True, True,
        "changes scroll position only; repeating just moves further",
    ),
    "browse_press": ToolBehaviour(
        False, True, False, True,
        "sends a key; Enter on a focused control can submit a form or a purchase",
    ),
    "browse_click": ToolBehaviour(
        False, True, False, True,
        "a click can submit, pay, or delete; the most destructive common action",
    ),
    "browse_type": ToolBehaviour(
        False, True, False, True,
        "enters text into a live page; on a checkout field this writes a credential",
    ),
    "browse_fill": ToolBehaviour(
        False, True, False, True,
        "sets a field value; same credential exposure as typing",
    ),
    "browse_select": ToolBehaviour(
        False, True, False, True,
        "changes a select's value, which can fire change handlers that submit",
    ),
    "browse_set_files": ToolBehaviour(
        False, True, False, True,
        "hands files to an upload control, sending them off the machine",
    ),
    "browse_download": ToolBehaviour(
        False, True, False, True,
        "writes a file to disk and fetches it from a remote host",
    ),
    # Arbitrary JS on a logged-in page: can delete, spend, or exfiltrate.
    "browse_eval": ToolBehaviour(
        False, True, False, True,
        "runs arbitrary JS on the page; its own docstring says escape hatch, not sandbox",
    ),
    # The one genuinely read-only member of the eval family.
    "browse_eval_audit": ToolBehaviour(
        True, False, True, True,
        "reads orvima's own audit log; sentinel tests assert it cannot perform an action",
    ),
}


def for_tool(name: str) -> ToolBehaviour:
    """Behaviour for a bare tool name such as ``browse_click``.

    Raises rather than defaulting, so a new tool cannot ship unannotated by
    omission: adding a handler without adding it here fails loudly.
    """
    try:
        return _BEHAVIOUR[name]
    except KeyError:
        raise KeyError(
            f"{name} has no annotation. Add it to _BEHAVIOUR with a reason - "
            "OpenAI's directory rejects tools missing any of the four hints, and "
            "a default would be a guess about whether an action can spend money."
        ) from None


def all_names() -> tuple[str, ...]:
    return tuple(sorted(_BEHAVIOUR))
