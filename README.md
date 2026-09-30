# Orvima

**Why should Claude be the only one with a browser?**

Orvima is a self-hosted, local-first browser agent for **any** AI tool — Claude,
Cursor, Copilot, or your own Agent. Any MCP client gets a full set of `browse_*`
hands on **your own Chrome or Edge** — navigate, click, type, extract, verify,
multi-tab — powered by your logins, running on your machine, while you watch every
step in a live viewport and stop it whenever you like.

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

## Quick start (30 seconds)

```bash
pip install 'orvima[mcp]'          # or: uv tool install 'orvima[mcp]'
orvima demo                        # offline tour — try everything, zero setup
```

**Try it headlessly first — no browser, no internet, no keys:**

```bash
orvima run "send a message to Acme support"
```

That goal gets planned, executed step by step against Orvima's built-in
simulator, and every step is confirmed before the next one starts.

**Plug your AI into it (MCP):**

In Claude Code / Claude Desktop / Cursor / Copilot, add:

```json
{
  "mcpServers": {
    "orvima": { "command": "orvima", "args": ["mcp", "--mode", "demo"], "type": "stdio" }
  }
}
```

Then just tell your assistant things like
*“open the top hacker news story and summarize the comments”*.
It will `browse_navigate`, `browse_snapshot`, and report back — verified, not guessed.

**Use your real browser (real mode):**

Orvima launches **your installed Chrome or MS Edge** — visible, with a persistent
profile at `~/.orvima/profile`, so your logins survive restarts. Your everyday
profile is never touched. Want it to drive the browser you already have open?

```bash
orvima serve --mode real                                 # watch it work at :8301
orvima run --mode real "compare prices on two flights"   # autonomous, needs a brain
```

For autonomous `orvima run`, give it a brain — any OpenAI-compatible endpoint
(OpenAI, OpenRouter, Groq, or **local Ollama**):

```bash
export ORVIMA_LLM_BASE=http://localhost:11434/v1   # or https://api.openai.com/v1
export ORVIMA_LLM_KEY=sk-…                          # ORVIMA_LLM_MODEL=llama3.1 (default gpt-4o-mini)
```

Attach to a browser you already have running (parley-style, over CDP):

```bash
orvima --attach http://127.0.0.1:9222 mcp --mode real
```

> `--mode demo` = offline simulator (works everywhere, perfect for CI and tours)
> `--mode real` = your own installed browser, streaming frames to the UI
> flags: `--browser {chrome,msedge,chromium}`, `--attach <cdp-url>`,
> `--headless`, `--max-steps

---

## What makes Orvima different

- **A browser the agent *lives* in, not a scraper it pings.** The agent opens pages,
  clicks, types, waits, scrolls — like a careful human with WebDriver powers.
- **Verify before report.** After every action the agent confirms the result in the
  DOM (`snapshot`) before saying “done”. You see the same transcript the AI sees.
- **You are in the loop.** Live viewport, live tool-call log, pause/resume/approve
  controls. It’s your machine and your accounts.
- **Local-first.** Everything runs at `127.0.0.1`. Your cookies, sessions and scrapes
  never leave your computer.
- **Bring your own brain.** Orvima is tool surface + adaptive planner. The loop
  re-plans from what the page actually shows (`snapshot`), so it can do *anything
  on the web* — no pre-scripted flows. Plug in any OpenAI-compatible model
  (`ORVIMA_LLM_BASE/KEY/MODEL`, incl. local Ollama), or none at all: your MCP
  client (Claude, Cursor…) is the brain instead.
- **Boring primitives for smart agents.** `snapshot()` returns a compact,
  LLM-friendly outline of the page (roles, labels, headings, text) — not a wall of HTML.

## The tools

| tool | does |
| --- | --- |
| `browse_navigate(url)` | open a URL and wait for it to be interactive |
| `browse_click(selector)` | click the first element matching a selector |
| `browse_hover(selector)` | hover (reveals menus, tooltips) |
| `browse_type(selector, text)` | type into a field, human-ish pace |
| `browse_fill(selector, text)` | replace a field’s value wholesale |
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

Every tool returns `{"ok": true, ...}` only after the page has confirmed the result.

## How it’s built

| piece | what |
| --- | --- |
| `src/orvima/browser.py` | `BrowserController` — your Chrome/Edge (persistent profile or CDP attach) with verify-first ops |
| `src/orvima/demo.py` | `DemoBrowser` — the same surface, scripted, offline, CI-friendly |
| `src/orvima/tools.py` | the `browse_*` tools as plain dict-in/dict-out functions |
| `src/orvima/planner.py` | adaptive step-planner: `LLMPlanner` (any OpenAI-compatible endpoint) + `DemoPlanner` |
| `src/orvima/agent.py` | sessions, the event bus, and the agent loop (snapshot → decide → act → verify) |
| `src/orvima/api.py` | FastAPI app + SSE events (live frames, transcript, controls) |
| `src/orvima/mcp_server.py` | MCP (stdio) binding so any AI tool can drive it |
| `web/` | the dashboard UI (Next.js/React) — *on the way* |

## Roadmap

- [x] Core agent: 19 `browse_*` tools, verify-after-every-step loop
- [x] Drives **your** installed Chrome/Edge (persistent profile) or attaches to a running browser over CDP
- [x] Adaptive step-planner (snapshot → decide → act) with LLM / local-Ollama / MCP brains
- [x] Offline demo mode (runs anywhere, powers CI)
- [x] MCP server (works with mcp SDK v1 *and* v2)
- [x] HTTP API + live SSE stream (frames + transcript + pause/resume)
- [x] CI + test suite (demo-mode tests, no browser needed)
- [ ] Dashboard UI (watch the agent live, approve actions)
- [ ] One-line installers (`irm … | iex` / `curl … | sh`)
- [ ] Media + downloads

## Security

Orvima is **loopback-only by default** and stores nothing of yours remotely. It is a
tool for *your* browser and *your* accounts: only run it on machines you trust, and
never expose the API port publicly. Real-mode sessions use your real browser profile —
an agent can act as you on the websites *you* are already logged into, in a browser
**you can physically watch**. Pause it (`browse_control` / the UI), read the
transcript, and let it do one thing at a time.

## License

MIT. Free forever. Self-host it, fork it, run it on your own boxes.

---

Made with care — and a browser that keeps its eyes on the page.