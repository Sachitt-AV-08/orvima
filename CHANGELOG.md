# Changelog

All notable changes to Orvima are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Everything below was developed against a written plan with falsifiable gates.
Each phase was verified load-bearing by breaking the fix in turn and confirming
the test count moved — a green test that cannot detect its own bug is worse than
no test. Numbers are measured, not estimated.

### Added
- **Benchmark** (`bench.py`, `bench_site.py`): 11 tasks against a simulated site
  with a scripted planner, plus a safety gate graded on a fixture ledger.
  Pass rate 5/10 → 11/11, safety 4/4 → 5/5. The CLI prints, every run, that this
  is not evidence orvima can drive a real site.
- **Classified recovery** (`recovery.py`): transient failures get a second turn;
  irreversible ones never do. Irreversibility is decided from the *action* before
  the error is read, so a "Pay" click that reports a timeout — the shape where a
  real payment lands and then looks transient — is refused. `unknown` is not
  retried. Separate `max_attempts` (work) and `max_steps` (progress) budgets.
- **Element identity** (`identity.py`): a ref is a remembered identity
  (role/label/text/tag), not a position, so it survives re-render. A stale ref
  resolves to a substitute confirmed against the live page, and refuses outright
  when two candidates are equally good.
- **Iframe and shadow-DOM traversal**, with per-frame ref namespacing (`f2:e3`).
  Frames are walked through Playwright's frame API, not `contentDocument` — a
  `file://` origin is opaque, so `contentDocument` is null for a frame that is
  genuinely reachable. Frames Chromium will not expose are named in
  `notTraversed` with their src and reason, never silently dropped.
- **Intent-level verification**: optional `expect_url`, `expect_text` and
  `expect_count` (+ `expect_for`) on `browse_click` / `browse_navigate`. Unmet
  expectations are a hard error naming every mismatch, not a `verified: false`
  flag. Strictly additive — omit them and behaviour is identical, with no extra
  keys in the result.
- **Bounded planner context** (`context.py`): a 50-step run went from 285,449
  characters (~71k tokens) to 15,375 (~3.8k), measured. The newest steps are
  never dropped, and every truncation is announced in the transcript.
- **Downloads, file attachment, and an audited `browse_eval`**
  (`browse_download`, `browse_set_files`, `browse_eval_audit`; `browse_eval`
  gains a `reason`). Tool surface 19 → 22, all additive.

### Fixed
- **The LLM planner was never sent the current page.** `_render` tested
  `row["tool"] == "snapshot"`; no tool has that name — it is `browse_snapshot` —
  so `last_snapshot` was always empty and the `if last_snapshot:` guard meant
  the planner re-planned blind, contrary to the module's own docstring. Nothing
  caught it: the only planner test called `_parse`, and every end-to-end test
  drives a scripted planner that renders nothing.
- **Frame-scoped refs were rejected by the tool layer.** `_resolve` validated
  against `^e\d+$`, so the `f1:e3` refs the snapshot handed out for frame content
  raised "invalid ref". The traversal worked perfectly at the browser layer and
  was completely unreachable from a tool call.
- **`browse_eval` claimed "read-only where possible" and enforced nothing.** It
  now refuses expressions that look irreversible *before* they run, reports
  `mutating` measured from a before/after DOM signature, and records every call
  with its reason in a bounded audit trail. It is still not a sandbox.
- **Redaction matched substrings**, so it destroyed ordinary page content
  (`author`, `keyword`, `keynote`, `monkey`, `authorship`) while missing
  `bearer` entirely. Now matched on whole key tokens.
- `set_input_files` was called on the page rather than the locator.
- `accept_downloads` was never set explicitly on the persistent context.
- A bare `e3` ref became the selector `[data-orvima-ref=""]` and timed out for
  ten seconds on a perfectly readable page: `partition(":")[2]` returns `""` when
  there is no separator.

### Not claimed
- The benchmark's 100% is a statement about the loop's control flow against a
  simulator with a scripted planner. Phases 2–6 have zero benchmark coverage by
  construction; their evidence is the real-browser tests and the load-bearing
  mutations.
- The `browse_eval` guard is pattern matching on source text, not a sandbox.
  Closed shadow roots remain unreachable, and cross-origin frames are reported as
  unreachable rather than worked around.
- The context transcript still grows, one line per old step. The slope is now a
  small constant rather than a whole result per step, and a hard ceiling catches
  the pathological case, but it is not flat.

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