"""orvima — an agent-operated browser with a human-grade UI.

Give any AI tool (Claude, Cursor, Copilot, any MCP client) eyes and hands on
the web. Everything runs on your machine: a real Chromium the agent drives,
a live view you can watch, and RN clear verify-before-report discipline —
every action is confirmed in the DOM before it is called done.

    pip install 'orvima[mcp]'
    orvima demo            # offline tour: no Chrome, no internet
    orvima serve           # local UI + API at http://127.0.0.1:8301
    orvima mcp             # stdio MCP server for any AI tool
    orvima run "summarize the top 3 HN stories"   # headless agent
"""

__version__ = "0.1.3"

from .errors import BrowserError, OrvimaError, SessionNotFoundError  # noqa: F401

__all__ = [
    "BrowserError",
    "OrvimaError",
    "SessionNotFoundError",
    "__version__",
]
