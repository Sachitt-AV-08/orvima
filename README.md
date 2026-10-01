# Orvima

**Your browser, driven by any AI — with a live viewport you control.**

Orvima is a self-hosted, local-first browser agent. Any MCP-capable AI tool (Claude, Cursor, Copilot, your own agent) gets a full set of `browse_*` hands on **your own Chrome or Edge** — navigate, click, type, extract, verify, multi-tab — powered by your logins, running on your machine, while you watch every step in a live viewport and stop it whenever you like.

```
  any AI tool            MCP / stdio            +--------------------+
  (Claude, Copilot,         │                   |  Orvima (localhost) |
   Cursor, your agent)      └────browse_*──────▶|   YOUR browser with |
                                                 |   your logins       |
                                                 |   live viewport     |
                                                 |   pause / approve   |
                                                 +--------------------+
```

No cloud, no API key to try it, no account. Install it, point your AI at it, done.

---

## Why Orvima — the three things that actually matter

| | |
|---|---|
| **Live viewport** | See exactly what the agent sees — frames stream in real time via SSE. |
| **Human-in-the-loop** | Pause, resume, or approve any action before it commits. |
| **Verified steps** | Every action confirms the DOM result (`snapshot`) before the agent proceeds — no silent failures, no guessed success. |

Local-first. Everything runs at `127.0.0.1`. Your cookies, sessions and scrapes never leave your computer. Bring your own brain: plug in any OpenAI-compatible model (OpenAI, OpenRouter, Groq, local Ollama), or use your MCP client (Claude, Cursor, Copilot) as the brain.

---

## Quick start (30 seconds)

```bash
# Windows (PowerShell)
irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex

# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh

orvima demo                        # offline tour — try everything, zero setup
```

**Try it headlessly first — no browser, no internet, no keys:**

```bash
orvima run "send a message to Acme support"
```

That goal gets planned, executed step by step against Orvima's built-in simulator, and every step is confirmed before the next one starts.

**Plug your AI into it (MCP):**

Copy the exact config for your client:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "orvima": {
      "command": "orvima",
      "args": ["mcp", "--mode", "demo"],
      "type": "stdio"
    }
  }
}
```

**Claude Code** (add to your project or global config):

```bash
claude mcp add orvima orvima mcp --mode demo
```

**Cursor** (`.cursor/mcp.json` in your project root):

```json
{
  "mcpServers": {
    "orvima": {
      "command": "orvima",
      "args": ["mcp", "--mode", "demo"],
      "type": "stdio"
    }
  }
}
```

**Copilot / VS Code** (`settings.json`):

```json
{
  "mcp": {
    "servers": {
      "orvima": {
        "command": "orvima",
        "args": ["mcp", "--mode", "demo"],
        "type": "stdio"
      }
    }
  }
}
```

Use `--mode real` instead of `--mode demo` to drive your real browser (requires `ORVIMA_LLM_BASE` and `ORVIMA_LLM_KEY` for autonomous runs).

Then just tell your assistant things like
*"open the top hacker news story and summarize the comments"*.
It will `browse_navigate`, `browse_snapshot`, and report back — verified, not guessed.

**Use your real browser (real mode):**

Orvima launches **your installed Chrome or MS Edge** — visible, with a persistent profile at `~/.orvima/profile`, so your logins survive restarts. Your everyday profile is never touched. Want it to drive the browser you already have open?

```bash
orvima serve --mode real                                 # watch it work at :8301
orvima run --mode real "compare prices on two flights"   # autonomous, needs a brain
```

For autonomous `orvima run`, give it a brain — any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, or **local Ollama**):

```bash
export ORVIMA_LLM_BASE=http://localhost:11434/v1   # or https://api.openai.com/v1
export ORVIMA_LLM_KEY=sk-…                          # ORVIMA_LLM_MODEL=llama3.1 (default gpt-4o-mini)
```

Attach to a browser you already have running (parley-style, over CDP):

```bash
orvima --attach http://127.0.0.1:9222 mcp --mode real
```

`--browser {chrome,msedge,chromium}`, `--attach <cdp-url>`, `--headless`, `--max-steps` are global flags — they work with any subcommand.

> `--mode demo` = offline simulator (works everywhere, perfect for CI and tours)
> `--mode real` = your own installed browser, streaming frames to the UI
> flags: `--browser {chrome,msedge,chromium}`, `--attach <cdp-url>`, `--headless`, `--max-steps`

---

## Orvima vs. the alternatives

| | Orvima | Playwright MCP | Chrome DevTools MCP | browser-use |
|---|---|---|---|---|
| **Live viewport** | ✅ SSE stream | ❌ | ❌ | ❌ |
| **Human approval** | ✅ pause/resume/approve | ❌ | ❌ | ❌ |
| **Verified steps** | ✅ DOM-confirmed | ❌ | ❌ | ❌ |
| **Your logins / your profile** | ✅ persistent | ❌ fresh | ✅ your profile | ❌ fresh |
| **Local-first / loopback only** | ✅ | ✅ | ✅ | ✅ |
| **MCP stdio** | ✅ | ✅ | ✅ | ❌ |
| **Any OpenAI-compatible brain** | ✅ | ❌ | ❌ | ✅ |
| **Offline demo / CI** | ✅ | ❌ | ❌ | ❌ |
| **Self-hosted, MIT** | ✅ | ✅ | ✅ | ✅ |

*Comparison based on verifiable features: live viewport, human-in-the-loop controls, DOM-verified actions, and profile persistence. "brain" flexibility refers to supporting any OpenAI-compatible endpoint vs. vendor-locked models.*

---

## The tools

| tool | does |
| --- | --- |
| `browse_navigate(url)` | open a URL and wait for it to be interactive |
| `browse_click(selector)` | click the first element matching a selector |
| `browse_hover(selector)` | hover (reveals menus, tooltips) |
| `browse_type(selector, text)` | type into a field, human-ish pace |
| `browse_fill(selector, text)` | replace a field's value wholesale |
| `browse_select(selector, value)` | pick an option in a dropdown |
| `browse_press(key)` | press Enter / Escape / Tab / … |
| `browse_go_back()` | one page back |
| `browse_wait(ms)` | breathe (after submits, before verifying) |
| `browse_wait_for(selector)` | wait until an element exists |
| `browse_scroll(direction)` | down / up |
| `browse_snapshot()` | the compact DOM outline agents plan from |
| `browse_extract(selector)` | pull text out of one element |
| `browse_screenshot()` | base64 PNG of the live viewport |
| `browse_eval(expression)` | run a small JS expression (read-only where possible) |
| `browse_open_tab(url)` / `browse_list_tabs()` | multi-tab research |
| `browse_switch_tab(index)` / `browse_close_tab(index)` | move between / close tabs |

Every mutating tool (`browse_click`, `browse_type`, `browse_fill`, `browse_select`, `browse_press`, `browse_navigate`, `browse_go_back`, `browse_wait_for`, `browse_open_tab`, `browse_switch_tab`, `browse_close_tab`) returns `{"ok": true, ...}` with a `verified` flag after the page has confirmed the result. Read tools (`browse_snapshot`, `browse_screenshot`, `browse_extract`, `browse_eval`, `browse_hover`, `browse_wait`, `browse_scroll`, `browse_go_back`, `browse_list_tabs`) return `ok: true` without a `verified` field.

---

## How it's built

| piece | what |
| --- | --- |
| `src/orvima/browser.py` | `BrowserController` — your Chrome/Edge (persistent profile or CDP attach) with verify-first ops |
| `src/orvima/demo.py` | `DemoBrowser` — the same surface, scripted, offline, CI-friendly |
| `src/orvima/tools.py` | the `browse_*` tools as plain dict-in/dict-out functions |
| `src/orvima/planner.py` | adaptive step-planner: `LLMPlanner` (any OpenAI-compatible endpoint) + `DemoPlanner` |
| `src/orvima/agent.py` | sessions, the event bus, and the agent loop (snapshot → decide → act → verify) |
| `src/orvima/api.py` | FastAPI app + SSE events (live frames, transcript, controls) |
| `src/orvima/mcp_server.py` | MCP (stdio) binding so any AI tool can drive it |
| `src/orvima/cli.py` | argparse CLI with demo/serve/mcp/run/doctor |

## Roadmap

- [x] Core agent: 19 `browse_*` tools, verify-after-every-step loop
- [x] Drives **your** installed Chrome/Edge (persistent profile) or attaches to a running browser over CDP
- [x] Adaptive step-planner (snapshot → decide → act) with LLM / local-Ollama / MCP brains
- [x] Offline demo mode (runs anywhere, powers CI)
- [x] MCP server (works with mcp SDK v1 *and* v2)
- [x] HTTP API + live SSE stream (frames + transcript, pause/resume)
- [x] CI + test suite (demo-mode tests, no browser needed)
- [x] One-line installers (`irm … | iex` / `curl … | sh`)
- [ ] Dashboard UI (watch the agent live, approve actions)
- [ ] Media + downloads
- [ ] Cross-platform browser detection (macOS/Linux Chrome/Edge paths)

## Security

Orvima is **loopback-only by default** and stores nothing of yours remotely. It is a tool for *your* browser and *your* accounts: only run it on machines you trust, and never expose the API port publicly. Real-mode sessions use your real browser profile — an agent can act as you on the websites *you* are already logged into, in a browser **you can physically watch**. Pause it (`browse_control` / the UI), read the transcript, and let it do one thing at a time.

## Known limits

| Area | Status | Notes |
|------|--------|-------|
| CAPTCHAs / 2FA | ❌ Not supported | Human takeover (pause/resume) is the intended workflow |
| File dialogs | ❌ Not supported | Human takeover required |
| Iframes | ⚠️ Partial | Detected and noted in snapshot; not traversed |
| Shadow DOM | ⚠️ Partial | Not traversed (host detection not yet implemented) |
| Browser updates | ⚠️ May break selectors | Fixture tests catch regressions; update fixtures when needed |
| CAPTCHAs on login | ❌ Not solvable | Pause, solve manually, resume |
| Media / downloads | ❌ Not supported | On roadmap |

These are honest constraints — not bugs. Orvima is designed for human-in-the-loop automation where the human handles the hard edge cases.

## License

MIT. Free forever. Self-host it, fork it, run it on your own boxes.

---

Made with care — and a browser that keeps its eyes on the page.