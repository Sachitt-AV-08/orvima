#!/usr/bin/env python3
"""Generate the full orvima.in documentation site from source.

This produces a single HTML file with:
- Full tool reference (all 22 browse_* tools, from docstrings)
- HTTP API reference
- MCP config per client
- Architecture + gate flow
- All numbers measured, not remembered
"""

from __future__ import annotations

import html
import inspect
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from orvima import tools
from orvima import tool_annotations
from orvima import prompts

REPO = pathlib.Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"


def _markup(text: str) -> str:
    """Escape a data field, then honour its inline code marks.

    Docstrings and prompt descriptions describe markup *as text* —
    `browse_select` says "Pick an option in a `<select>`", `browse_set_files`
    says ``` ``<input type=file>`` ```, a prompt argument mentions `<table>`.
    Injected raw, those became live widgets on the docs page: a file picker
    nobody opened, a dropdown eating its own sentence. And the backticks
    around every inline code span printed literally. Escape first — escaping
    leaves backticks alone — then turn the code marks into `<code>`.
    """
    text = html.escape(text or "")
    text = re.sub(r"``([^`]+)``", r"<code>\1</code>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def get_tool_docstrings() -> list[dict]:
    """Extract structured info from each tool's docstring."""
    results = []
    for fn in tools.TOOLS:
        name = fn.__name__[5:]  # strip "tool_"
        doc = inspect.getdoc(fn) or ""
        # Parse into sections
        sections = {}
        current = "summary"
        for line in doc.splitlines():
            if line.startswith("Returns ") or line.startswith("Raises ") or line.startswith("Use ") or line.startswith("Give "):
                current = line.split()[0].lower()
                sections[current] = line
            elif current in sections:
                sections[current] += " " + line.strip()
            else:
                sections.setdefault(current, line.strip())
        bh = tool_annotations.for_tool(name)
        results.append({
            "name": name,
            "summary": sections.get("summary", doc.split(".")[0] + "."),
            "docstring": doc,
            "read_only": bh.read_only,
            "destructive": bh.destructive,
            "idempotent": bh.idempotent,
            "open_world": bh.open_world,
            "why": bh.why,
        })
    return results


def get_api_reference() -> dict:
    """Build the HTTP API reference."""
    return {
        "base": "http://127.0.0.1:8301",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/health",
                "summary": "Health check",
                "response": '{"ok": true, "version": "0.1.x"}',
            },
            {
                "method": "GET",
                "path": "/api/tools",
                "summary": "List all browse_* tools with descriptions",
                "response": '{"tools": [{"name": "browse_navigate", "description": "..."}, ...]}',
            },
            {
                "method": "POST",
                "path": "/api/sessions",
                "summary": "Create a new session",
                "request": '{"mode": "real", "start_url": "", "goal": ""}',
                "response": '{"ok": true, "session": {"id": "...", "mode": "real", "status": "idle", ...}}',
            },
            {
                "method": "POST",
                "path": "/api/sessions/{id}/goal",
                "summary": "Run a goal in a session",
                "params": "wait=true|false, timeout=60",
                "request": '{"goal": "summarize the top HN story"}',
                "response": '{"ok": true, "summary": "...", "steps": 12}',
            },
            {
                "method": "GET",
                "path": "/api/sessions/{id}/events",
                "summary": "SSE stream of session events (snapshots, tool calls, approvals)",
                "response": "text/event-stream",
            },
            {
                "method": "GET",
                "path": "/api/approvals",
                "summary": "List pending approvals (for the phone page)",
                "response": '{"approvals": [...], "gate": "on", "available": true, ...}',
            },
            {
                "method": "POST",
                "path": "/api/approvals/{id}",
                "summary": "Approve or deny a pending action",
                "request": '{"approved": true}',
            },
            {
                "method": "GET",
                "path": "/api/gate/stats",
                "summary": "Gate health and statistics",
                "response": '{"evaluated": 12, "degraded": 0, "approval_ttl": 120}',
            },
        ],
    }


def get_mcp_configs() -> dict:
    """MCP configs for each client."""
    return {
        "Claude Desktop": {
            "file": "~/Library/Application Support/Claude/claude_desktop_config.json (macOS) or %APPDATA%\\Claude\\claude_desktop_config.json (Windows)",
            "config": {
                "mcpServers": {
                    "orvima": {"command": "orvima", "args": ["mcp"], "type": "stdio"}
                }
            },
        },
        "Claude Code": {
            "file": "project or global .mcp.json",
            "config": {
                "mcpServers": {
                    "orvima": {"command": "orvima", "args": ["mcp"], "type": "stdio"}
                }
            },
            "cli": "claude mcp add orvima orvima mcp",
        },
        "Cursor": {
            "file": ".cursor/mcp.json",
            "config": {
                "mcpServers": {
                    "orvima": {"command": "orvima", "args": ["mcp"], "type": "stdio"}
                }
            },
        },
        "Copilot / VS Code": {
            "file": "settings.json",
            "config": {
                "mcp": {
                    "servers": {
                        "orvima": {"command": "orvima", "args": ["mcp"], "type": "stdio"}
                    }
                }
            },
        },
    }


def render_tool_reference(tools_data: list[dict]) -> str:
    """Render the full tool reference section."""
    out = []
    out.append('<section id="tool-reference" class="docsec">')
    # Counted, not typed: the heading used to say 22 for ever.
    out.append(f'<h2>Tool Reference — all {len(tools_data)} <code>browse_*</code> tools</h2>')
    out.append('<p class="section-lede">Every tool is dict-in, dict-out with <code>verified</code> on every action.</p>')
    out.append('<div class="grid two">')

    for t in tools_data:
        badges = []
        if t["read_only"]:
            badges.append('<span class="badge read-only">read-only</span>')
        if t["destructive"]:
            badges.append('<span class="badge destructive">destructive</span>')
        if t["idempotent"]:
            badges.append('<span class="badge idempotent">idempotent</span>')
        if t["open_world"]:
            badges.append('<span class="badge open-world">open-world</span>')

        out.append(f'<article class="tool">')
        out.append(f'<h3><code>{t["name"]}</code> {" ".join(badges)}</h3>')
        out.append(f'<p>{_markup(t["summary"])}</p>')
        if t["why"]:
            out.append(f'<p class="why"><strong>Why these hints:</strong> {_markup(t["why"])}</p>')
        out.append(f'</article>')
    out.append('</div>')
    out.append('</section>')
    return "\n".join(out)


def render_api_reference(api: dict) -> str:
    """Render the HTTP API reference section."""
    out = []
    out.append(f'<section id="api-reference" class="docsec">')
    out.append(f'<h2>HTTP API — <code>{api["base"]}</code></h2>')
    out.append('<p class="section-lede">Local-first. Nothing leaves 127.0.0.1. Your browser, your logins, your machine.</p>')
    out.append('<div class="grid two">')

    for ep in api["endpoints"]:
        out.append('<article class="endpoint">')
        out.append(f'<div class="ep-head"><span class="method {ep["method"].lower()}">{ep["method"]}</span> <code>{ep["path"]}</code></div>')
        out.append(f'<p>{_markup(ep["summary"])}</p>')
        if "request" in ep:
            out.append(f'<pre><code>{_markup(ep["request"])}</code></pre>')
        if "params" in ep:
            out.append(f'<p class="params"><strong>Query params:</strong> {_markup(ep["params"])}</p>')
        if "response" in ep:
            out.append(f'<pre><code>{_markup(ep["response"])}</code></pre>')
        out.append('</article>')
    out.append('</div>')
    out.append('</section>')
    return "\n".join(out)


def render_mcp_configs(configs: dict) -> str:
    """Render MCP config examples per client."""
    out = []
    out.append('<section id="mcp-configs" class="docsec">')
    out.append('<h2>MCP Configs — paste into your client</h2>')
    out.append('<p class="section-lede">Real mode is the default. No <code>--mode</code> flag needed.</p>')
    out.append('<div class="grid two">')

    for client, data in configs.items():
        out.append(f'<article class="client-config">')
        out.append(f'<h3>{client}</h3>')
        out.append(f'<p><strong>File:</strong> <code>{_markup(data["file"])}</code></p>')
        if "cli" in data:
            out.append(f'<p><strong>CLI:</strong> <code>{_markup(data["cli"])}</code></p>')
        out.append(f'<pre><code>{_markup(json.dumps(data["config"], indent=2))}</code></pre>')
        out.append('</article>')
    out.append('</div>')
    out.append('</section>')
    return "\n".join(out)


def render_prompts() -> str:
    """Render the MCP prompts section."""
    out = []
    out.append('<section id="mcp-prompts" class="docsec">')
    out.append('<h2>MCP Prompts — prepared workflows</h2>')
    out.append('<p class="section-lede">Invoke by name from any MCP client. Each returns a structured prompt template with placeholders you fill in.</p>')
    out.append('<div class="grid two">')

    for p in prompts.list_prompts():
        out.append('<article class="prompt">')
        out.append(f'<h3><code>{p["name"]}</code></h3>')
        out.append(f'<p><strong>{_markup(p["title"])}</strong> — {_markup(p["description"])}</p>')
        if p["arguments"]:
            out.append('<p><strong>Arguments:</strong></p>')
            out.append('<ul>')
            for arg in p["arguments"]:
                req = " (required)" if arg["required"] else " (optional)"
                out.append(f'<li><code>{arg["name"]}</code>{req} — {_markup(arg["description"])}</li>')
            out.append('</ul>')
        out.append('</article>')
    out.append('</div>')
    out.append('</section>')
    return "\n".join(out)


def render_architecture() -> str:
    """Render the architecture section."""
    n_tools = len(tools.TOOLS)
    n_prompts = len(prompts.list_prompts())
    return f"""
<section id="architecture" class="docsec">
<h2>Architecture</h2>
<p class="section-lede">Three layers, one contract.</p>

<div class="grid two">
<article class="arch-layer">
  <h3>MCP Server (stdio)</h3>
  <p>Exposes {n_tools} <code>browse_*</code> tools + {n_prompts} prompts over stdio. Any MCP client (Claude, Cursor, Copilot, your agent) gets hands on your browser.</p>
</article>

<article class="arch-layer">
  <h3>HTTP API (127.0.0.1:8301)</h3>
  <p>REST + SSE for the local UI, programmatic control, and the phone approval page. Same contract as the MCP tools.</p>
</article>

<article class="arch-layer">
  <h3>Agent Loop</h3>
  <p>Plans → acts → verifies. <code>browse_snapshot</code> after every step. If <code>verified: false</code>, the loop retries or escalates to the gate.</p>
</article>

<article class="arch-layer">
  <h3>Approval Gate (Sentinel)</h3>
  <p>Classifies every tool call. Destructive actions wait for a human. The gate reads the page <em>now</em>, not when the approval was queued. Expired approvals disappear.</p>
</article>
</div>
</section>
"""


def render() -> str:
    """Build the full docs.html text.

    Split out from main() so the test suite can diff the shipped page
    against a fresh generation without writing anything to disk.
    """
    tools_data = get_tool_docstrings()
    api = get_api_reference()
    mcp_configs = get_mcp_configs()

    # Build the full HTML
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>orvima — Documentation</title>
<meta name="description" content="orvima: self-hosted browser agent. 22 browse_* tools, HTTP API, MCP prompts. Real browser, local-first, verified steps.">
<link rel="icon" href="mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="style.css">
</head>
<body>

<header class="site">
  <nav>
    <a class="brand" href="#top">
      <img src="mark.svg" alt="" width="22" height="21">
      <span>orvima</span>
    </a>
    <div class="navlinks">
      <a href="#tool-reference">Tools</a>
      <a href="#api-reference">API</a>
      <a href="#mcp-configs">MCP Configs</a>
      <a href="#mcp-prompts">Prompts</a>
      <a href="#architecture">Architecture</a>
      <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener">GitHub</a>
    </div>
  </nav>
</header>

<main id="top">
  <section class="hero">
    <p class="eyebrow">MIT · self-hosted · nothing leaves your machine</p>
    <h1>orvima — Documentation</h1>
    <p class="lede">Every tool, endpoint, and workflow. All numbers measured, not remembered.</p>
    <div class="cta">
      <a class="btn primary" href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener">GitHub</a>
      <a class="btn" href="#tool-reference">Start with the tools</a>
    </div>
  </section>

  {render_tool_reference(tools_data)}

  {render_api_reference(api)}

  {render_mcp_configs(mcp_configs)}

  {render_prompts()}

  {render_architecture()}

  <section id="proof" class="proof">
    <h2>Proof — real runs, not samples</h2>
    <p>The transcripts below were captured by running orvima, not written by hand.</p>
    <div class="runners">
      <div class="runner">
        <div class="runnerhead"><span class="goal">send a message to Acme support</span><span class="stepcount">9 steps</span></div>
        <div class="term" id="term-happy" role="region" aria-label="Successful run transcript"></div>
        <p class="runnerfoot">Every step returns <code>verified: true</code>.</p>
      </div>
      <div class="runner highlight">
        <div class="runnerhead"><span class="goal">delete everything in my account</span><span class="stepcount">held</span></div>
        <div class="term" id="term-gate" role="region" aria-label="Destructive action held by gate"></div>
        <p class="runnerfoot">The gate read the selector, judged it <code>outward</code>, and stopped.</p>
      </div>
    </div>
  </section>

</main>

<footer>
  <p>orvima is free and MIT licensed. Self-hosted, local-first, and yours.</p>
  <p class="small"><a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener">Source</a> · <a href="mailto:sachitt@orvima.in">sachitt@orvima.in</a> · A V Sachitt</p>
</footer>

<script src="main.js"></script>
</body>
</html>"""


def main() -> int:
    html = render()
    out_path = DOCS / "docs.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())