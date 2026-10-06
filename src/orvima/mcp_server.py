"""MCP server: let any MCP client drive Orvima's browser.

    orvima mcp                 # stdio

Client config (Claude Code / Claude Desktop / Cursor ...):
    { "mcpServers": { "orvima": { "command": "orvima", "args": ["mcp"], "type": "stdio" } } }

Every browse_* tool runs against the session's browser (a demo browser by
default; ``--mode real`` drives a live Chromium you control).
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

from . import prompts, tool_annotations, tools
from .agent import SessionStore

HIDDEN = ("session", "browser", "_args", "_kw")


def _annotations_for(tool_name: str):
    """Build `ToolAnnotations` for a tool, or None if this SDK lacks them.

    The four hints are mandatory for OpenAI's MCP directory and are what let a
    host warn a user before an action spends money. mcp 1.x had no annotations
    parameter, so the registration below probes once and falls back rather than
    pinning the project to one SDK generation.
    """
    try:
        from mcp.types import ToolAnnotations  # noqa: PLC0415
    except ImportError:
        return None

    b = tool_annotations.for_tool(tool_name)
    return ToolAnnotations(
        title=tool_name.replace("_", " "),
        read_only_hint=b.read_only,
        destructive_hint=b.destructive,
        idempotent_hint=b.idempotent,
        open_world_hint=b.open_world,
    )


def register_tools(server: Any, sess: Any) -> bool:
    """Register every tool on `server`. Returns whether hints were attached.

    Split out of `run()` so a test can exercise the exact registration path
    instead of a copy of it. A test that rebuilds the loop itself proves only
    that the copy works: the original m8ven finding was that the table was
    correct and the registration silently dropped it.
    """
    # Probe whether this SDK generation accepts annotations at all.
    supports_annotations = "annotations" in inspect.signature(server.tool).parameters

    for fn in tools.TOOLS:
        tool_name = fn.__name__[5:]
        bound = _bind(sess, fn)
        kwargs: dict[str, Any] = {"name": tool_name, "description": _doc(fn)}
        if supports_annotations:
            annotations = _annotations_for(tool_name)
            if annotations is not None:
                kwargs["annotations"] = annotations
        server.tool(**kwargs)(bound)

    return supports_annotations


def register_prompts(server: Any) -> bool:
    """Register all prompts on `server`.

    Returns whether the server accepted prompt registrations (mcp >= 2.0).
    """
    has_prompt = hasattr(server, "prompt")
    if not has_prompt:
        return False

    for p in prompts.list_prompts():
        # The SDK expects a function that returns the prompt messages.
        # We pass the definition as metadata and return a simple template.
        def make_handler(prompt: dict[str, Any]):
            async def handler(arguments: dict[str, Any] | None = None) -> list[dict[str, str]]:
                return [
                    {
                        "role": "user",
                        "content": (
                            f"PROMPT: {prompt['name']}\n"
                            f"TITLE: {prompt['title']}\n"
                            f"DESCRIPTION: {prompt['description']}\n"
                            f"ARGUMENTS: {arguments or {}}"
                        ),
                    }
                ]

            return handler

        server.prompt(
            name=p["name"],
            title=p["title"],
            description=p["description"],
        )(make_handler(p))

    return True


def run(demo: bool = False, name: str = "orvima") -> int:
    """Build a session + MCP server and serve on stdio. Blocks until stdin closes."""
    sess = SessionStore().create(mode="demo" if demo else "real")
    server = _server_class()(name)

    if not register_tools(server, sess):
        print(
            "orvima: this mcp SDK predates tool annotations, so readOnlyHint "
            "and destructiveHint are absent. Install mcp>=2 to get them.",
            file=sys.stderr,
        )

    if not register_prompts(server):
        print(
            "orvima: this mcp SDK predates prompt support. Install mcp>=2 to get prompts.",
            file=sys.stderr,
        )

    import asyncio  # noqa: PLC0415

    async def _serve() -> None:
        if hasattr(server, 'create_initialization_options'):
            # mcp < 2.0 (FastMCP)
            from mcp.server.stdio import stdio_server  # noqa: PLC0415
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())
        else:
            # mcp >= 2.0 (MCPServer) - run_stdio_async handles stdio internally
            await server.run_stdio_async()

    asyncio.run(_serve())
    return 0


def _doc(fn) -> str:
    return inspect.getdoc(fn) or "Orvima browse tool."


def _server_class():
    try:
        from mcp.server.fastmcp import (  # mcp < 2.0 (FastMCP)
            FastMCP as ServerClass,
        )

        return ServerClass
    except ImportError:
        from mcp.server.mcpserver import MCPServer as ServerClass  # mcp >= 2.0

        return ServerClass


def _bind(sess, fn):
    """Bind fn to sess's browser, producing a real named function the MCP runtime
    can introspect (v2 rejects functools.partial: it needs __name__/signature).
    The `session`/`browser` params are hidden from the exposed signature.
    """
    name = fn.__name__
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values() if p.name not in HIDDEN]

    callsig = ", ".join(
        p.name + ("=" + repr(p.default) if p.default is not inspect._empty else "")
        for p in params
    )
    arglist = ", ".join(p.name for p in params) if params else ""
    src = f"def the_tool({callsig}):\n    return __fn(__browser, {arglist})\n"
    if not params:
        src = "def the_tool():\n    return __fn(__browser)\n"
    ns: dict = {"__fn": fn, "__browser": sess.browser}
    exec(src, ns)  # trusted, static source from our own tool defs
    tool = ns["the_tool"]
    tool.__name__ = name
    tool.__doc__ = _doc(fn)
    return tool
