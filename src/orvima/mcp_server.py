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

from . import compute, gate, mail, media, prompts, router, tool_annotations, tools, vision, voice, whatsapp
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
        readOnlyHint=b.read_only,
        destructiveHint=b.destructive,
        idempotentHint=b.idempotent,
        openWorldHint=b.open_world,
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


def _bind_mail(fn):
    """Bind fn for MCP without injecting a browser. Mail tools speak
    SMTP/IMAP directly and take their own parameters; no session state needed.
    Produces a real named function the MCP runtime can introspect.
    """
    name = fn.__name__
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values()]

    callsig = ", ".join(
        p.name + ("=" + repr(p.default) if p.default is not inspect._empty else "")
        for p in params
    )
    arglist = ", ".join(p.name for p in params) if params else ""
    src = f"def the_tool({callsig}):\n    return __fn({arglist})\n"
    ns: dict = {"__fn": fn}
    exec(src, ns)  # trusted, static source from our own tool defs
    tool = ns["the_tool"]
    tool.__name__ = name
    tool.__doc__ = _doc(fn)
    return tool


def register_mail_tools(server: Any) -> bool:
    """Register every mail tool on `server`. Returns whether hints were attached.

    Mail tools do not need a session or a browser: they connect directly to an
    SMTP/IMAP server using credentials from call args or environment variables.
    """
    supports_annotations = "annotations" in inspect.signature(server.tool).parameters

    for fn in mail.MAIL_TOOLS:
        tool_name = fn.__name__  # mail_send / mail_read, domain-qualified like browse_*
        bound = _bind_mail(fn)
        kwargs: dict[str, Any] = {"name": tool_name, "description": _doc(fn)}
        if supports_annotations:
            annotations = _annotations_for(tool_name)
            if annotations is not None:
                kwargs["annotations"] = annotations
        server.tool(**kwargs)(bound)

    return supports_annotations


def _bind_simple(fn):
    """Bind fn for MCP with no injection. Used for tools that take all their
    parameters from call args (voice, media, compute, whatsapp)."""
    name = fn.__name__
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values()]

    callsig = ", ".join(
        p.name + ("=" + repr(p.default) if p.default is not inspect._empty else "")
        for p in params
    )
    arglist = ", ".join(p.name for p in params) if params else ""
    src = f"def the_tool({callsig}):\n    return __fn({arglist})\n"
    ns: dict = {"__fn": fn}
    exec(src, ns)
    tool = ns["the_tool"]
    tool.__name__ = name
    tool.__doc__ = _doc(fn)
    return tool


def register_module_tools(server: Any, tool_list: tuple, prefix: str = "") -> bool:
    """Register a module's tools on the server. Returns whether hints were attached."""
    supports_annotations = "annotations" in inspect.signature(server.tool).parameters

    for fn in tool_list:
        tool_name = fn.__name__
        bound = _bind_simple(fn)
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

    if not register_mail_tools(server):
        print(
            "orvima: this mcp SDK predates tool annotations for mail tools.",
            file=sys.stderr,
        )

    for mod_name, mod_tools in [
        ("whatsapp", whatsapp.WHATSAPP_TOOLS),
        ("voice", voice.VOICE_TOOLS),
        ("media", media.MEDIA_TOOLS),
        ("compute", compute.COMPUTE_TOOLS),
        ("gate", gate.GATE_TOOLS),
        ("router", router.ROUTER_TOOLS),
        ("vision", vision.VISION_TOOLS_SIMPLE),
    ]:
        if not register_module_tools(server, mod_tools):
            print(
                f"orvima: this mcp SDK predates tool annotations for {mod_name} tools.",
                file=sys.stderr,
            )

    # Browser-bound vision tools (use the user's real Chrome like browse_*)
    supports_annotations = "annotations" in inspect.signature(server.tool).parameters
    for fn in vision.VISION_TOOLS_BROWSER:
        tool_name = fn.__name__
        bound = _bind(sess, fn)
        kwargs = {"name": tool_name, "description": _doc(fn)}
        if supports_annotations:
            annotations = _annotations_for(tool_name)
            if annotations is not None:
                kwargs["annotations"] = annotations
        server.tool(**kwargs)(bound)

    if not register_prompts(server):
        print(
            "orvima: this mcp SDK predates prompt support. Install mcp>=2 to get prompts.",
            file=sys.stderr,
        )

    import asyncio  # noqa: PLC0415
    try:
        import nest_asyncio  # noqa: PLC0415
        nest_asyncio.apply()
    except ImportError:
        pass

    async def _serve() -> None:
        if hasattr(server, 'create_initialization_options'):
            # mcp < 2.0 (FastMCP)
            from mcp.server.stdio import stdio_server  # noqa: PLC0415
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())
        else:
            # mcp >= 2.0 (MCPServer) - run_stdio_async handles stdio internally
            await server.run_stdio_async()

    # Playwright's sync_playwright().start() leaves a (possibly running) event
    # loop. Reuse it instead of creating a new one, using the non-deprecated
    # policy accessor.
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_running():
        # Schedule on the running loop and wait
        future = asyncio.ensure_future(_serve(), loop=loop)
        try:
            loop.run_until_complete(future)
        except RuntimeError:
            import time
            while not future.done():
                time.sleep(0.1)
            if future.exception():
                raise future.exception() from None
    else:
        loop.run_until_complete(_serve())
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

    # Preserve original type annotations so fastmcp can introspect them
    # for its Pydantic arg model (untyped vars broke registration).
    try:
        from typing import get_type_hints as _get_hints
        _hints = _get_hints(fn)
    except Exception:
        _hints = {}
    _pieces = []
    for _p in params:
        _piece = _p.name
        _ann = _hints.get(_p.name)
        if _ann is not None and _ann is not inspect._empty:
            _name = getattr(_ann, "__name__", str(_ann))
            if "." in str(_name):
                _name = str(_name).rsplit(".", 1)[-1]
            _piece += ": " + str(_name)
        else:
            _piece += ": Any"
        if _p.default is not inspect._empty:
            _piece += " = " + repr(_p.default)
        _pieces.append(_piece)
    callsig = ", ".join(_pieces)
    arglist = ", ".join(p.name for p in params) if params else ""
    src = f"def the_tool({callsig}):\n    return __fn(__browser, {arglist})\n"
    if not params:
        src = "def the_tool():\n    return __fn(__browser)\n"
    ns: dict = {"__fn": fn, "__browser": sess.browser, "Any": Any}
    exec(src, ns)  # trusted, static source from our own tool defs
    tool = ns["the_tool"]
    tool.__name__ = name
    tool.__doc__ = _doc(fn)
    return tool
