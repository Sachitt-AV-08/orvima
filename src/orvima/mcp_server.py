"""MCP server: let any MCP client drive Orvima's browser.

    orvima mcp                 # stdio

Client config (Claude Code / Claude Desktop / Cursor ...):
    { "mcpServers": { "orvima": { "command": "orvima", "args": ["mcp"], "type": "stdio" } } }

Every browse_* tool runs against the session's browser (a demo browser by
default; ``--mode real`` drives a live Chromium you control).
"""

from __future__ import annotations

import inspect

from . import tools
from .agent import SessionStore

HIDDEN = ("session", "browser", "_args", "_kw")


def run(demo: bool = True, name: str = "orvima") -> int:
    """Build a session + MCP server and serve on stdio. Blocks until stdin closes."""
    sess = SessionStore().create(mode="demo" if demo else "real")
    server = _server_class()(name)
    for fn in tools.TOOLS:
        bound = _bind(sess, fn)
        server.tool(name=fn.__name__[5:], description=_doc(fn))(bound)

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
