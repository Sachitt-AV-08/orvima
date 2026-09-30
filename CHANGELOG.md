# Changelog

All notable changes to Orvima are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-30

Initial public scaffold:

- `browse_*` tool surface (12 tools): navigate, click, type, fill, press,
  go_back, wait, scroll, snapshot, extract, screenshot, eval — pure
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
- CLI: `orvima demo`, `orvima serve`, `orvima mcp`, `orvima run`.