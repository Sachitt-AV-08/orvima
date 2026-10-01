# Changelog

All notable changes to Orvima are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-10-01

### Fixed
- **CORS**: restricted to `http://127.0.0.1` / `localhost` (was `*`)
- **SSE busy-spin**: `asyncio.sleep(0)` → `sleep(0.1)` in event stream
- **Redaction wired**: password fields masked in `_OUTLINE_JS`; `_redact_sensitive` applied in `Session.log` and planner render
- **Demo ref-click**: off-by-two fix (`[20:-2]` → `[18:-2]`); `close_tab` active-tab IndexError fixed
- **ORVIMA_HEADLESS**: proper boolean parsing (`1`/`true`/`yes` only; `0` now means headless=off)
- **Global `--attach`**: works as `orvima --attach URL mcp --mode real` (was subparser-only)
- **Tool names**: `tool_*` → `tool_browse_*` (wire format = `browse_navigate` matching docs)
- **Installers**: corrected PEP 508 syntax, flag parsing order, PowerShell invocation
- **CI**: `playwright install chromium` + skip guard when no browser
- **Release workflow**: single build (wheel+sdist), version guard, substituted body, test+lint gate

### Changed
- Removed `web/` reference (dashboard UI not yet shipped)
- Softened "every tool verified" claim (read tools don't have `verified` field)
- Updated shadow DOM / iframe claims to match reality

## [0.1.1] - 2026-10-01

### Fixed
- Lint: `__future__` import ordering in test file

## [0.1.0] - 2026-09-30

Initial public scaffold:

- `browse_*` tool surface (19 tools): navigate, click, type, fill, press,
  go_back, wait, scroll, snapshot, extract, screenshot, eval, hover,
  select, wait_for, open_tab, list_tabs, switch_tab, close_tab — pure
  dict-in/dict-out over a shared browser contract.
- `BrowserController` (Playwright Chromium, real mode) and `DemoBrowser`
  (offline simulator) behind one interface.
- Agent loop: goal → plan → act → verify; every action is confirmed in the
  DOM before the next step runs.
- Pluggable LLM planner (any OpenAI-compatible `/chat/completions` endpoint)
  with a deterministic offline demo planner as the default.
- FastAPI app + SSE events: sessions, live frames, transcript, pause/resume
  controls.
- MCP (stdio) server; works with mcp SDK v1 and v2.
- CLI: `orvima demo`, `orvima serve`, `orvima mcp`, `orvima run`, `orvima doctor`.