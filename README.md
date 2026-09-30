# Orvima

**The browser your AI drives — and you can watch.**

Orvima is a self-hosted, local-first browser agent for any AI tool. Claude, Cursor,
Copilot, or any MCP client gets a full set of `browse_*` hands on a real Chromium on
your machine — navigate, click, type, extract, verify — while you watch every single
step in a live viewport and stop it whenever you like.

```
  any AI tool            MCP / stdio            +--------------------+
  (Claude, Copilot,         │                   |  Orvima (localhost) |
   Cursor, your agent)      └────browse_*──────▶|   Chromium agent   |
                                                |   live viewport    |
                                                |   pause / approve  |
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

**Use a real browser (real mode):**

```bash
playwright install chromium      # one-time
orvima serve --mode real         # open http://127.0.0.1:8301 and watch it work
```

> `--mode demo` = offline simulator (works everywhere, perfect for CI and tours)
> `--mode real` = a live Chromium on your machine, streaming frames to the UI

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
- **Bring your own brain.** Orvima is tool surface + planner; plug in any
  OpenAI-compatible model for the planner (`ORVIMA_LLM_BASE/KEY/MODEL`), or none at all
  to stay fully offline.
- **Boring primitives for smart agents.** `snapshot()` returns a compact,
  LLM-friendly outline of the page (roles, labels, headings, text) — not a wall of HTML.

## The tools

| tool | does |
| --- | --- |
| `browse_navigate(url)` | open a URL and wait for it to be interactive |
| `browse_click(selector)` | click the first element matching a selector |
| `browse_type(selector, text)` | type into a field, human-ish pace |
| `browse_fill(selector, text)` | replace a field’s value wholesale |
| `browse_press(key)` | press Enter / Escape / Tab / … |
| `browse_go_back()` | one page back |
| `browse_wait(ms)` | breathe (after submits, before verifying) |
| `browse_scroll(direction)` | down / up |
| `browse_snapshot()` | the compact DOM outline agents plan from |
| `browse_extract(selector)` | pull text out of one element |
| `browse_screenshot()` | base64 PNG of the live viewport |
| `browse_eval(expression)` | run a small JS expression (read-only where possible) |

Every tool returns `{"ok": true, ...}` only after the page has confirmed the result.

## How it’s built

| piece | what |
| --- | --- |
| `src/orvima/browser.py` | `BrowserController` — Playwright Chromium with verify-first ops |
| `src/orvima/demo.py` | `DemoBrowser` — the same surface, scripted, offline, CI-friendly |
| `src/orvima/tools.py` | the `browse_*` tools as plain dict-in/dict-out functions |
| `src/orvima/agent.py` | sessions, the event bus, and the agent loop (plan → act → verify) |
| `src/orvima/api.py` | FastAPI app + SSE events (live frames, transcript, controls) |
| `src/orvima/mcp_server.py` | MCP (stdio) binding so any AI tool can drive it |
| `web/` | the dashboard UI (Next.js/React) — *on the way* |

## Roadmap

- [x] Core agent: 12 `browse_*` tools, verify-after-every-step loop
- [x] Offline demo mode (runs anywhere, powers CI)
- [x] MCP server (works with mcp SDK v1 *and* v2)
- [x] HTTP API + live SSE stream (frames + transcript + pause/resume)
- [ ] Dashboard UI (watch the agent live, approve actions)
- [ ] CI + test suite (demo-mode tests, no browser needed)
- [ ] One-line installers (`irm … | iex` / `curl … | sh`)
- [ ] Media + downloads, persistent profiles

## Security

Orvima is **loopback-only by default** and stores nothing of yours remotely. It is a
tool for *your* browser and *your* accounts: only run it on machines you trust, and
never expose the API port publicly. Real-mode sessions use your existing browser
profile and permissions — an agent can act as you on the websites *you* are already
logged into. Pause it, watch it, and read the transcript before you let it loose.

## License

MIT. Free forever. Self-host it, fork it, run it on your own boxes.

---

Made with care — and a browser that keeps its eyes on the page.