# Orvima

One AI tool gets eyes and hands on the web - on your machine. Open-source, local-first browser automation MCP server: 60 tools across 9 domains, a Sentinel safety gate, local OCR/vision, Edge TTS voice, and CDP real-profile attach. Runs at `127.0.0.1`.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Version 0.2.1](https://img.shields.io/badge/version-0.2.1-blue.svg)](pyproject.toml)
[![CI](https://github.com/Sachitt-AV-08/orvima/actions/workflows/ci.yml/badge.svg)](https://github.com/Sachitt-AV-08/orvima/actions/workflows/ci.yml)

## Why Orvima

- **Live viewport** - frames stream to a local dashboard (`http://127.0.0.1:8301`) you can watch.
- **Human-in-the-loop** - pause/resume always; an optional fail-closed Sentinel gate holds risky actions.
- **Verified steps** - every mutating action confirms the DOM result before the agent proceeds.
- **Local-first** - cookies, sessions, and scrapes stay on your machine. Loopback only by default.
- **Any brain** - Claude, Cursor, Copilot, or any OpenAI-compatible model including local Ollama.

## Quick start

Install from source (verified against a clean checkout):

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima
python -m pip install -e ".[mcp]"
orvima doctor
```

One-line installers are also provided:

```bash
# Windows (PowerShell)
irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex

# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh
```

Try it with no browser, no internet, and no keys:

```bash
orvima run "send a message to Acme support" --mode demo
```

Drive your own browser:

```bash
orvima serve                 # dashboard + API at http://127.0.0.1:8301
orvima mcp                   # stdio MCP server for any AI tool
```

Attach to a browser you already have running (CDP):

```bash
orvima --attach http://127.0.0.1:9222 mcp
```

Autonomous runs need a brain - any OpenAI-compatible endpoint:

```bash
export ORVIMA_LLM_BASE=http://localhost:11434/v1   # or https://api.openai.com/v1
export ORVIMA_LLM_KEY=sk-...
export ORVIMA_LLM_MODEL=llama3.1                     # default gpt-4o-mini
```

## MCP client configuration

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "orvima": {
      "command": "orvima",
      "args": ["mcp"],
      "type": "stdio"
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add orvima orvima mcp
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "orvima": {
      "command": "orvima",
      "args": ["mcp"],
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
        "args": ["mcp"],
        "type": "stdio"
      }
    }
  }
}
```

To run against the offline simulator instead of a real browser, add `"--mode", "demo"` to `args`.

## Feature categories (60 MCP tools)

| Category | Count | Highlights |
|----------|-------|------------|
| browse | 22 | navigation, click, hover, type, fill, select, press, scroll, snapshot, screenshot, extract, eval (audited), tabs, download, set files |
| mail | 2 | `mail_send`, `mail_read` via SMTP/IMAP |
| whatsapp | 5 | status, list chats, read, send, react (via WhatsApp Desktop/parley) |
| voice | 4 | `voice_say` (Edge TTS + Ultron modulation), `voice_listen` (Whisper STT), styles |
| media | 4 | YouTube transcript, YouTube search, music search, music play |
| compute | 7 | math solve/simplify/derivative/integral/plot data, unit conversion, science constants |
| gate | 3 | classify risk, describe action, risk concepts (Sentinel-backed) |
| router | 2 | list recipes, route a goal to a reviewed recipe or refuse |
| vision | 11 | OCR, region OCR, find text, image description, template match, face detection (boxes only), video frames, video OCR, scene changes, multi-pass OCR, browser-screenshot OCR |

All tools are plain dict-in/dict-out. Credentials come from arguments or environment variables, never hardcoded.

## Browser tool reference

| Tool | Does |
|------|------|
| `browse_navigate(url)` | open a URL and wait for it to be interactive |
| `browse_click(selector)` / `browse_hover(selector)` | click / hover |
| `browse_type` / `browse_fill` / `browse_select` / `browse_press` | input fields, dropdowns, keys |
| `browse_go_back()` / `browse_wait(ms)` / `browse_wait_for(selector)` / `browse_scroll` | navigation and timing |
| `browse_snapshot()` / `browse_extract(selector)` / `browse_screenshot()` | read page |
| `browse_eval(expression, reason)` / `browse_eval_audit()` | audited JS escape hatch (not a sandbox) |
| `browse_download(selector)` / `browse_set_files(paths, selector)` | downloads and file attachment |
| `browse_open_tab` / `browse_list_tabs` / `browse_switch_tab` / `browse_close_tab` | multi-tab |

Mutating tools return `{"ok": true, ...}` with a `verified` flag. Read tools return `ok: true` without `verified`. `browse_eval` returns `mutating` instead. `browse_click` and `browse_navigate` accept optional `expect_url`, `expect_text`, `expect_count` (+ `expect_for`) polled up to `expect_timeout_ms`; an unmet expectation is a hard error.

## Architecture overview

| File | Role |
|------|------|
| `src/orvima/mcp_server.py` | MCP stdio server binding all 60 tools |
| `src/orvima/tools.py` | `browse_*` tools as dict-in/dict-out functions |
| `src/orvima/browser.py` | real browser controller (persistent profile or CDP attach) |
| `src/orvima/cdp.py` | page-level CDP client attaching to a single open tab's socket |
| `src/orvima/demo.py` | offline simulator with the same tool surface |
| `src/orvima/planner.py` | adaptive step planner (`LLMPlanner` any OpenAI endpoint + `DemoPlanner`) |
| `src/orvima/agent.py` | sessions, event bus, and agent loop (snapshot -> decide -> act -> verify) |
| `src/orvima/api.py` | FastAPI app + SSE events; serves dashboard at `/` |
| `src/orvima/dashboard.py` | self-served control dashboard (no framework/CDN) |
| `src/orvima/cli.py` | `demo`, `serve`, `mcp`, `run`, `bench`, `doctor` |
| `src/orvima/sentinel_gate.py` + `src/orvima/sentinel/` | safety gate: risk classification, approval memory, override |
| `src/orvima/vision.py` | local OCR, image matching/description, video analysis |
| `src/orvima/compute.py` / `media.py` / `mail.py` / `whatsapp.py` / `voice.py` | domain modules |
| `src/orvima/errands/` (core/recipes/router) | goal-to-reviewed-recipe router, used by `router` tools |
| `src/orvima/voice.py` | Edge TTS + Ultron modulation (pitch shift, reverb, metallic EQ) + Whisper STT |

Everything runs on `127.0.0.1`; no cloud dependency for core operation.

## Safety gate (Sentinel)

Sentinel is an **optional** package and is not a declared dependency. When it is missing or broken the gate is **fail-closed**: no action can be judged, so no action is auto-approved. Modes:

| How you run it | What happens |
|----------------|--------------|
| `orvima run` (CLI) | fully unattended; no gate constructed |
| `orvima serve`, Sentinel not installed | every action waits for a human (including reads) |
| `orvima serve`, Sentinel installed | only flagged actions are held for a human verdict |
| `ORVIMA_SENTINEL=off` | fully unattended, deliberately; reported as `gate: "off"` |

Check state:

```bash
curl -s localhost:8301/api/gate/stats
# {"gate":"degraded","available":false,...}  <- nothing is being judged
# {"gate":"on","available":true,...}          <- judging is in force
# {"gate":"off",...}                         <- deliberately unattended
```

Key mechanisms:

- **Local, no LLM, no network on the decision path.** Default `classifier_mode=off` decides in ~0.1 ms via pure string matching.
- **Fail closed, loudly.** A throwing classifier, missing policy, or timeout returns `allowed: false` with `degraded: true` - a classifier bug never becomes permission.
- **Approval memory.** After a human approves an action, its exact signature (tool + selector/ref/url/value/text) is stored and matching actions are auto-approved without re-running the classifier. Approving "place your order" does not auto-approve "delete account".
- **Strong-request override.** An explicit user request can lift an outward-risk hold to allow, but can never override a destructive-risk denial.
- **Revalidation.** A queued approval can expire while the page changes; the gate rechecks that the referenced element has not moved and the risk has not increased before honouring it (`approval_ttl` default 300 s).
- **Auditable.** Every decision (risk, reason, classifier output) lands in the session transcript; overrides are appended to an override log.

The gate is a classifier plus a word list - it is wrong in both directions. It reduces reading load; it does not replace judgement.

## Approvals

The three run modes and what they mean for approvals:

| Mode | Command | Gate status | Behaviour |
|------|---------|-------------|-----------|
| CLI unattended | `orvima run "goal"` | **none** (no gate constructed) | Every action runs without approval. No pauses, no gate. |
| API serve (Sentinel missing) | `orvima serve` | **degraded** (fail-closed) | Every action is refused until a human approves via the dashboard or `/api/gate/approve`. |
| API serve (Sentinel installed) | `orvima serve` | **on** | Only flagged actions wait for approval; reads and safe actions proceed. |
| Explicit off | `ORVIMA_SENTINEL=off orvima serve` | **off** | Every action runs without approval. Deliberate escape hatch. |

Check the current mode at any time:

```bash
curl -s localhost:8301/api/gate/stats
# {"gate":"on","available":true,...}       <- judging is in force
# {"gate":"degraded","available":false,...} <- nothing is being judged, fail-closed
# {"gate":"off",...}                       <- deliberately unattended
```

If a session appears stuck, check `/api/gate/stats` first. A `degraded` gate means Sentinel is not installed or failed to load - install it or set `ORVIMA_SENTINEL=off` if you intentionally want no gate.

## Vision module

All vision operations are local-first: Tesseract 5.x for OCR, OpenCV for image/video processing, Pillow for image I/O. No API keys, no network calls.

- **OCR**: grayscale, denoise, unsharp-mask, Otsu threshold, deskew, then multi-source x multi-PSM passes; best-confidence result wins. Low-confidence output is flagged.
- **Region OCR** reads one rectangle (price badge, button label) instead of the whole page.
- **Text find** reports whether a query appears and where.
- **Image describe** returns dimensions, dominant colors, and edge density.
- **Template match** locates a template image inside a page and returns center coords.
- **Face detection** returns count + bounding boxes only. No identity, no recognition, no image data uploaded.
- **Video**: adaptive frame sampling; OCR per sampled frame; scene changes via inter-frame pixel diff.
- **Multi-pass OCR** tries 4 rotations x 3 modes and reports which orientation read best - use as a last resort for sideways screenshots.
- **Browser-screenshot OCR**: screenshots the bound browser's current page and OCRs it in one call (`vision_ocr_screenshot`).

Dependencies: Tesseract binary is auto-detected from PATH and common install dirs. If missing, every tool returns a clear `not available` message rather than making the server fail to load. Install via `winget install tesseract-ocr.tesseract` on Windows or your package manager elsewhere.

## CLI reference

```text
orvima [--browser {chrome,msedge,brave,chromium}] [--attach CDP_URL] [--headless] {demo,serve,mcp,run,bench,doctor}
```

- `orvima demo` - offline tour.
- `orvima serve` - local API + UI at `http://127.0.0.1:8301`.
- `orvima mcp` - stdio MCP server (`--mode {demo,real}`).
- `orvima run "goal"` - headless agent loop (`--mode`, `--max-steps`).
- `orvima bench` - measure agent-loop task pass rate (no browser).
- `orvima doctor` - health check for browser, profile, port, LLM, MCP.

Global flags work with any subcommand. `--headless` is CI/pod-friendly. `ORVIMA_ATTACH_TAB` names a single browser tab to avoid CDP handshake stalls on busy profiles.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima
python -m pip install -e ".[dev,mcp]"

# Quality checks
ruff format .
ruff check .
pytest                                    # coverage gate: 75% line
```

- Python 3.10+ (3.11 preferred).
- Type hints and docstrings for public functions.
- New MCP tool: create it under `src/orvima/`, register in the module tool list, add tests in `tests/`, document in `docs/api.md`.

Report bugs and feature requests via GitHub Issues. Include reproduction steps, environment details (OS, Python, browser), and logs.

## License

MIT. Free forever. Self-host it, fork it, run it on your own boxes. See [LICENSE](LICENSE).

## Documentation

- [API Reference (MCP Tools)](docs/api.md)
- [Launch Announcements](docs/launch.md)
- [Security Policy](SECURITY.md)
- [Disclaimer](DISCLAIMER.md)
