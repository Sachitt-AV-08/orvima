# Orvima

[![M8ven Score](https://m8ven.ai/badge/mcp/sachitt-av-08/orvima)](https://m8ven.ai/mcp/sachitt-av-08/orvima?s=readme)

**Your browser, driven by any AI — with a live viewport you control.**

Orvima is a self-hosted, local-first browser agent. Any MCP-capable AI tool (Claude, Cursor, Copilot, your own agent) gets a full set of `browse_*` hands on **your own Chrome, Edge or Brave** — navigate, click, type, extract, verify, multi-tab — powered by your logins, running on your machine, while you watch every step in a live viewport and stop it whenever you like.

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
| **Human-in-the-loop** | Pause or resume a run at any time. An optional fail-closed approval gate holds risky actions for a human - see [Approvals](#approvals). |
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

Orvima launches **your installed Chrome, MS Edge or Brave** — visible, with a persistent profile at `~/.orvima/profile`, so your logins survive restarts. Your everyday profile is never touched. Want it to drive the browser you already have open?

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

Start that browser with `--remote-debugging-port=<port>` to expose the endpoint.

**Against a browser you actually use every day, add `--attach-tab`.** Chromium's
browser-level `connect_over_cdp` enumerates and auto-attaches to *every* target
before the handshake completes, so a profile with extension service workers,
reCAPTCHA iframes and a dozen open tabs can stall it indefinitely — we measured
one still hanging at 90s with no other client attached. Naming a single tab skips
that enumeration and returns in milliseconds:

```bash
export ORVIMA_ATTACH_TAB=linkedin.com    # substring of the tab url or title
orvima --attach http://127.0.0.1:9335 mcp --mode real
```

If the endpoint answers but the handshake still stalls, attach fails fast rather
than hanging — `ORVIMA_ATTACH_TIMEOUT` (default 10s) bounds the wait, and
`ORVIMA_TYPE_DELAY_MS` (default 0) sets per-character typing delay.

`--browser {chrome,msedge,brave,chromium}`, `--attach <cdp-url>`, `--headless`, `--max-steps` are global flags — they work with any subcommand.

> `--mode demo` = offline simulator (works everywhere, perfect for CI and tours)
> `--mode real` = your own installed browser, streaming frames to the UI
> flags: `--browser {chrome,msedge,brave,chromium}`, `--attach <cdp-url>`, `--headless`, `--max-steps`

---

## Orvima vs. the alternatives

| | Orvima | Playwright MCP | Chrome DevTools MCP | browser-use |
|---|---|---|---|---|
| **Live viewport** | ✅ SSE stream | ❌ | ❌ | ❌ |
| **Human approval** | pause/resume always; optional fail-closed gate holds risky actions | ? | ? | ? |
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
| `browse_type(selector, text)` | type into a field character by character |
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
| `browse_eval(expression, reason)` | run a JS expression - an escape hatch, not a sandbox. Refuses expressions that look irreversible, and reports `mutating` measured from a before/after DOM signature |
| `browse_eval_audit()` | every `browse_eval` this session: expression, reason, effect |
| `browse_download(selector)` | click something that downloads a file and save it locally; fails explicitly when no download starts |
| `browse_set_files(paths, selector)` | attach files to an `<input type=file>`, and report what the page's own FileList ended up holding |
| `browse_open_tab(url)` / `browse_list_tabs()` | multi-tab research |
| `browse_switch_tab(index)` / `browse_close_tab(index)` | move between / close tabs |

`browse_click` and `browse_navigate` also take optional expectations - `expect_url`, `expect_text`, `expect_count` (+ `expect_for`). They are polled for up to `expect_timeout_ms`, because the result of a click is often asynchronous, and an unmet expectation is a **hard error naming every mismatch** rather than a `verified: false` you can ignore. Omit them and behaviour is exactly as before, with no extra keys in the result.

Every mutating tool (`browse_click`, `browse_type`, `browse_fill`, `browse_select`, `browse_press`, `browse_navigate`, `browse_go_back`, `browse_wait_for`, `browse_open_tab`, `browse_switch_tab`, `browse_close_tab`, `browse_download`, `browse_set_files`) returns `{"ok": true, ...}` with a `verified` flag after the page has confirmed the result. Read tools (`browse_snapshot`, `browse_screenshot`, `browse_extract`, `browse_eval_audit`, `browse_hover`, `browse_wait`, `browse_scroll`, `browse_go_back`, `browse_list_tabs`) return `ok: true` without a `verified` field. `browse_eval` returns `mutating` rather than `verified`, because "did anything change" is the wrong question for arbitrary JS.

**What `browse_eval` does not do.** It is not a sandbox. The guard matches destructive API names and guard words in the source text, so an expression that achieves the same effect another way will run. It raises the cost of a mistake; it does not make one impossible. Every call is recorded in the audit trail with the reason you stated, and the point of the audit is that you can read afterwards exactly what ran on a logged-in page.

Refs from a snapshot work anywhere, including inside frames (`f2:e3`), and survive re-render: a ref is a remembered *identity*, not a position. If the original element is gone, Orvima looks for a substitute and **refuses rather than guessing** when two candidates are equally good.

---

## How it's built

| piece | what |
| --- | --- |
| `src/orvima/browser.py` | `BrowserController` — your Chrome/Edge/Brave (persistent profile or CDP attach) with verify-first ops |
| `src/orvima/cdp.py` | page-level CDP client — attaches to a single open tab's own socket, skipping the browser handshake that stalls on busy profiles |
| `src/orvima/demo.py` | `DemoBrowser` — the same surface, scripted, offline, CI-friendly |
| `src/orvima/tools.py` | the `browse_*` tools as plain dict-in/dict-out functions |
| `src/orvima/planner.py` | adaptive step-planner: `LLMPlanner` (any OpenAI-compatible endpoint) + `DemoPlanner` |
| `src/orvima/agent.py` | sessions, the event bus, and the agent loop (snapshot → decide → act → verify) |
| `src/orvima/api.py` | FastAPI app + SSE events (live frames, transcript, controls) |
| `src/orvima/mcp_server.py` | MCP (stdio) binding so any AI tool can drive it |
| `src/orvima/cli.py` | argparse CLI with demo/serve/mcp/run/doctor |

## Roadmap

- [x] Core agent: 22 `browse_*` tools, verify-after-every-step loop
- [x] Drives **your** installed Chrome/Edge/Brave (persistent profile) or attaches to a running browser over CDP
- [x] Adaptive step-planner (snapshot → decide → act) with LLM / local-Ollama / MCP brains
- [x] Classified recovery: transient failures get a second turn, irreversible ones never do
- [x] Refs are element identities, not positions - they survive re-render and refuse on ambiguity
- [x] Iframes and shadow roots are traversed, and unreachable frames are named rather than dropped
- [x] Intent-level verification (`expect_url` / `expect_text` / `expect_count`)
- [x] Bounded planner context - a 50-step run is ~3.8k tokens of prompt, not ~71k
- [x] Downloads, file attachment, and an audited `browse_eval`
- [x] Offline demo mode (runs anywhere, powers CI)
- [x] MCP server (works with mcp SDK v1 *and* v2)
- [x] HTTP API + live SSE stream (frames + transcript, pause/resume)
- [x] CI + test suite (470 tests: demo-mode tests need no browser; real-browser tests skip cleanly when no Chromium is present)
- [x] One-line installers (`irm … | iex` / `curl … | sh`)
- [ ] Dashboard UI (watch the agent live, approve actions)
- [ ] Media playback (file downloads are done: `browse_download`)
- [ ] Cross-platform browser detection (macOS/Linux Chrome/Edge paths)

## Approvals

Whether an action waits for you depends on how you started orvima and what is
installed. This is worth stating plainly, because the three cases behave very
differently and the failure mode in the second one looks like a broken install.

| How you run it | What actually happens |
|----------------|-----------------------|
| `orvima run` (CLI) | **Fully unattended.** No gate is constructed; every action runs without being judged |
| `orvima serve` (HTTP API), `sentinel` not installed | **Every action waits for you**, including reads like `browse_snapshot`. Nothing can be judged, so nothing is auto-approved |
| `orvima serve` with `sentinel` installed | Only actions the gate flags are held for a human verdict |
| `ORVIMA_SENTINEL=off` | **Fully unattended**, deliberately. Reported as `gate: "off"` at `/api/gate/stats` |

`sentinel` is an optional package and is **not** a declared dependency - not even
an extra. So the second row is what a fresh `pip install orvima` gives you: an
API that holds every action for approval because there is no classifier to judge
it. That is the fail-closed default working, and the refusal message tells you
both ways out - install `sentinel`, or set `ORVIMA_SENTINEL=off` and accept that
nothing is being checked.

Check what you have:

```bash
curl -s localhost:8000/api/gate/stats
# {"gate": "degraded", "available": false, ...}   <- nothing is being judged
# {"gate": "on", "available": true, ...}          <- judging is in force
# {"gate": "off", ...}                            <- deliberately unattended
```

`on`, `degraded` and `off` are kept distinct on purpose. "A human switched this
off" and "the gate failed to load" call for opposite responses, and collapsing
them is how a malfunction quietly becomes a policy.

What the gate is not: it is a classifier plus a word list, and it is wrong in
both directions. A genuinely dangerous action behind an innocuously-worded button
may pass; a harmless action may prompt. It reduces how much you have to read
carefully. It does not replace judgement.

## Security

Orvima is **loopback-only by default** and stores nothing of yours remotely. It is a tool for *your* browser and *your* accounts: only run it on machines you trust, and never expose the API port publicly. Real-mode sessions use your real browser profile — an agent can act as you on the websites *you* are already logged into, in a browser **you can physically watch**. Pause it (`browse_control` / the UI), read the transcript, and let it do one thing at a time.

## Known limits

| Area | Status | Notes |
|------|--------|-------|
| CAPTCHAs / 2FA | ❌ Not supported | Human takeover (pause/resume) is the intended workflow |
| File dialogs | ❌ Not supported | Human takeover required |
| Browser updates | may break selectors | Fixture tests catch regressions; update fixtures when needed |
| CAPTCHAs on login | not solvable | Pause, solve manually, resume |
| Media playback | not supported | On roadmap. File *downloads* are supported via `browse_download` |
| Unreachable frames | partial | Same-origin iframes and shadow roots are traversed and get frame-scoped refs (`f2:e3`). A frame Chromium cannot read is listed in `notTraversed` with its src and the reason rather than silently missing |

These are honest constraints — not bugs. Orvima is designed for human-in-the-loop automation where the human handles the hard edge cases.

## License

MIT. Free forever. Self-host it, fork it, run it on your own boxes.

---

Made with care — and a browser that keeps its eyes on the page.