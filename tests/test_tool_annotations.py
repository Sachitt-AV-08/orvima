"""Every tool must declare all four MCP hints, and declare them truthfully.

m8ven's review of `orvima` found one tool exposed with no annotations, and
OpenAI's MCP directory rejects tools where any of the four hints are missing or
non-boolean. Those are the mechanical rules, and `test_every_tool_has_all_four`
covers them.

The rule that actually matters is the second half of this file: a hint that is
present but wrong is worse than a missing one, because a host will trust it. A
tool marked `read_only_hint=True` that can spend money is a safety defect that
reads as a safety feature. So each annotation is cross-checked against the
handler's real behaviour rather than against the table beside it.
"""

from __future__ import annotations

import inspect
import re

import pytest

from orvima import tool_annotations, tools

mcp_types = pytest.importorskip("mcp.types", reason="mcp SDK not installed")

NAMES = [fn.__name__[5:] for fn in tools.TOOLS]


# ------------------------------------------------- the mechanical contract ----


def test_every_tool_has_all_four_hints() -> None:
    missing = []
    for name in NAMES:
        try:
            b = tool_annotations.for_tool(name)
        except KeyError as exc:
            missing.append(str(exc))
            continue
        for field in ("read_only", "destructive", "idempotent", "open_world"):
            value = getattr(b, field)
            if not isinstance(value, bool):
                missing.append(f"{name}.{field} is {value!r}, not a bool")
    assert not missing, "\n".join(missing)


def test_no_annotation_table_entry_goes_unused() -> None:
    """An entry for a renamed tool is a stale promise, so it must fail here."""
    extra = set(tool_annotations.all_names()) - set(NAMES)
    assert not extra, f"annotated but no such tool: {sorted(extra)}"


def test_annotations_build_a_valid_types_object() -> None:
    for name in NAMES:
        ann = mcp_types.ToolAnnotations(
            title=name.replace("_", " "),
            read_only_hint=tool_annotations.for_tool(name).read_only,
            destructive_hint=tool_annotations.for_tool(name).destructive,
            idempotent_hint=tool_annotations.for_tool(name).idempotent,
            open_world_hint=tool_annotations.for_tool(name).open_world,
        )
        assert isinstance(ann.read_only_hint, bool)
        assert isinstance(ann.destructive_hint, bool)


def test_an_unannotated_tool_raises_instead_of_defaulting() -> None:
    with pytest.raises(KeyError, match="no annotation"):
        tool_annotations.for_tool("browse_not_a_real_tool")


def test_the_server_actually_passes_annotations_to_the_sdk() -> None:
    """The table is only useful if it reaches the wire.

    A test that only checks `tool_annotations` would pass even if the
    registration loop stopped passing them, which is the defect m8ven actually
    reported.
    """
    from orvima import mcp_server

    server = mcp_server._server_class()("probe")
    assert "annotations" in inspect.signature(server.tool).parameters, (
        "installed mcp SDK has no annotations parameter; the hints would be "
        "dropped silently and the listing would stay unannotated"
    )

    ann = mcp_server._annotations_for("browse_click")
    assert ann is not None, "_annotations_for returned None on an SDK that supports them"
    assert ann.destructive_hint is True
    assert ann.read_only_hint is False

    assert mcp_server._annotations_for("browse_snapshot").read_only_hint is True


def _advertised(server) -> dict:
    """What the server would actually send a host: name -> wire annotations."""
    import asyncio

    listed = asyncio.run(server.list_tools())
    return {
        t.name: (t.annotations.model_dump(by_alias=True) if t.annotations else None)
        for t in listed
    }


def test_every_advertised_tool_carries_all_four_hints_on_the_wire() -> None:
    """The guarantee that actually matters, checked where a host reads it.

    Everything else in this file inspects `tool_annotations` or the SDK
    signature. That is one layer above where a host sees the value, and it is
    exactly the gap this test was written to close: during development every
    check here passed while a separate probe reported all four hints missing,
    because `ToolAnnotations` stores snake_case fields (`read_only_hint`) and
    serialises to camelCase aliases (`readOnlyHint`). A test that reads the
    field names it guessed would have repeated the mistake instead of catching
    it.

    So this registers through the production path - `register_tools`, the same
    function `run()` calls - and inspects the advertised payload with the
    aliases the MCP spec defines.
    """
    from orvima import mcp_server
    from orvima.agent import SessionStore

    WIRE = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

    sess = SessionStore().create(mode="demo")
    server = mcp_server._server_class()("probe")
    assert mcp_server.register_tools(server, sess), (
        "the installed mcp SDK has no annotations parameter, so every hint is "
        "dropped and the listing stays unannotated"
    )

    advertised = _advertised(server)

    assert set(advertised) == set(NAMES), (
        f"the server advertises a different tool set than tools.TOOLS: "
        f"advertised={sorted(advertised)} expected={sorted(NAMES)}"
    )

    problems = []
    for name, wire in advertised.items():
        if wire is None:
            problems.append(f"{name}: advertised with no annotations at all")
            continue
        for hint in WIRE:
            if hint not in wire:
                problems.append(f"{name}: {hint} absent from the advertised payload")
            elif not isinstance(wire[hint], bool):
                problems.append(f"{name}: {hint}={wire[hint]!r} is not a boolean")

    assert not problems, (
        "tools advertised without all four explicit boolean hints:\n  "
        + "\n  ".join(problems)
    )


# ------------------------------------------------------ truthfulness checks ----

# Tools that only observe. If one of these is ever marked as able to act, a
# host will skip a confirmation prompt it should have shown.
MUST_BE_READ_ONLY = {
    "browse_snapshot", "browse_extract", "browse_screenshot",
    "browse_list_tabs", "browse_wait", "browse_wait_for", "browse_eval_audit",
}

# Tools that can submit, send, spend, or delete. Marking any of these read-only
# is the dangerous direction, so each is pinned.
MUST_BE_DESTRUCTIVE = {
    "browse_click", "browse_type", "browse_fill", "browse_press",
    "browse_select", "browse_set_files", "browse_download", "browse_eval",
}


@pytest.mark.parametrize("name", sorted(MUST_BE_READ_ONLY))
def test_observing_tools_are_marked_read_only(name: str) -> None:
    b = tool_annotations.for_tool(name)
    assert b.read_only is True, (
        f"{name} only reads, so read_only_hint must be True; "
        f"got {b.read_only}. Reason on record: {b.why}"
    )
    assert b.destructive is False, f"{name} is read-only, so destructive must be False"


@pytest.mark.parametrize("name", sorted(MUST_BE_DESTRUCTIVE))
def test_action_tools_are_marked_destructive(name: str) -> None:
    b = tool_annotations.for_tool(name)
    assert b.destructive is True, (
        f"{name} can change remote state, so destructive_hint must be True; "
        f"got {b.destructive}. Reason on record: {b.why}"
    )


def test_eval_is_not_marked_read_only() -> None:
    """The single most misleading annotation available.

    `browse_eval` runs arbitrary JavaScript on a logged-in page. Its own
    docstring says "an escape hatch, not a sandbox". Marking it read-only would
    let a host skip a prompt on the one tool that can do anything.
    """
    b = tool_annotations.for_tool("browse_eval")
    assert b.read_only is False
    assert b.destructive is True


def test_every_tool_that_reaches_a_url_is_open_world() -> None:
    """A site the caller did not name is an untrusted input source."""
    for name in NAMES:
        fn = next(f for f in tools.TOOLS if f.__name__[5:] == name)
        src = inspect.getsource(fn)
        touches_web = bool(re.search(r"\.(navigate|extract|snapshot|click|fill)\(", src))
        if touches_web:
            b = tool_annotations.for_tool(name)
            assert b.open_world is True, (
                f"{name} touches the live page, so open_world_hint must be True; "
                f"got {b.open_world}"
            )


def test_compounding_actions_are_not_marked_idempotent() -> None:
    """Repeating a click twice is two clicks, not one.

    Idempotent is the hint most likely to be waved through, so the tools that
    accumulate are pinned: a second click can confirm a dialog the first opened.
    """
    for name in ("browse_click", "browse_type", "browse_fill", "browse_press"):
        b = tool_annotations.for_tool(name)
        assert b.idempotent is False, (
            f"{name} compounds when repeated, so idempotent_hint must be False; "
            f"got {b.idempotent}"
        )


def test_every_annotation_carries_a_reason() -> None:
    """A hint with no recorded reasoning cannot be re-checked after an edit."""
    for name in NAMES:
        b = tool_annotations.for_tool(name)
        assert b.why and len(b.why) > 20, f"{name} has no usable reason recorded"
