# Changelog

All notable changes to Orvima are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Everything below was developed against a written plan with falsifiable gates.
Each phase was verified load-bearing by breaking the fix in turn and confirming
the test count moved — a green test that cannot detect its own bug is worse than
no test. Numbers are measured, not estimated.

The gate and documentation work below extends that method past the code: the
false claims in `SECURITY.md` and `README.md` were found by checking each
documented claim against the running program, and are now pinned by tests that
fail if the docs drift back.

### Fixed
- **A sticky or fixed header could make an element permanently unclickable, and
  the failure never mentioned the header.** Playwright scrolls an element into
  view by *centring* it, so an element near the top of a page can end up under a
  pinned header. Playwright's actionability check correctly refuses - the pointer
  would land on the header - but it refuses by spinning out its full 10s timeout
  and reporting a call log that names no header, so the failure read as flakiness
  rather than as a layout problem with a known fix. Measured across seven
  constructions first: sticky headers are usually harmless (Playwright re-centres
  and lands correctly), and the real failure is narrow - the element is occluded
  *and* the page cannot be scrolled to clear it. A new `occlusion.uncover`
  measures the obstruction and scrolls by the minimum amount needed, and where no
  scroll can help it reports that immediately, naming the occluder, rather than
  waiting out a timeout it had already resolved.
- **Six actions inherited that timeout, and two were worse than failing.**
  `click`, `type`, `fill`, `hover`, `select` and `download` now uncover first and
  fail fast on a fixed obstruction. `fill` and `select` are the notable pair:
  measured, both *succeeded* on a header-covered field, because `fill` and
  `select_option` set values through the DOM rather than by clicking. A credential
  went into an invisible box and a dropdown changed a value the user never chose,
  both reported as `verified: true`. `download` was the worst offender of the
  failing cases: it spent 10s on the click plus 15s waiting for a download, then
  blamed the link ("may be expired, or the site may be waiting on a permission
  prompt") when the cause was a header. Costs 2.8 ms median per action on an
  800-row table, against the 10s timeout it exists to avoid.
- **The occlusion probe itself refused real sign-in forms.** Pointed at Google's
  sign-in page, it reported the email field as covered by an in-flow element and
  orvima declined to type. Two defects, both from reasoning about `z-index`
  instead of asking the browser: the walk continued *past* the target and scanned
  the whole stack, so elements painted *underneath* counted as walls - which is
  exactly what Google's outlined-text-field border divs are; and the guard meant
  to discard exactly those was `Number(style.zIndex) <= elZ`, where
  `z-index: auto` parses to `NaN` and every comparison against `NaN` is false,
  so it never fired for the `z-index: auto` that most elements carry. The probe
  now follows the browser's own rule - `elementsFromPoint` returns paint order
  with the topmost first, so the first node that can receive a pointer is where
  the click lands - and no longer compares z-indices at all. `pointer-events:
  none` overlays are seen through, since they intercept nothing however large they
  are. Google's flow was then driven end to end with a reserved `.invalid`
  address and answered normally: no challenge, no refusal.
- **The approval gate's fail-closed promise held at one layer and not the next.
  `sentinel_gate.py` refused every action when its classifier was missing, but
  `api.get_gate()` returned `None` when the gate module itself could not be
  imported — and `None` means *no gate*, which `_authorise` treats as allow
  everything. A syntax error or partial install silently converted a gated agent
  into a fully autonomous one: the guarantee was reachable only by breaking the
  module that implements it. `get_gate` now returns a self-contained
  `_RefusingGate` that refuses, and `gate_status()` reports `on` / `degraded` /
  `off` at `/api/gate/stats` so "a human switched this off" and "this broke"
  stop looking the same.
- **The refusal explained itself only halfway.** When nothing can be judged, the
  message said `sentinel not loaded; refusing to auto-approve` — naming the
  problem but not the two ways out. It now names both: install `sentinel`, or set
  `ORVIMA_SENTINEL=off` and accept that nothing is being checked.

### Documentation
- **Three comments described the fail-open as safe**, which is the dangerous kind
  of wrong: they survive audit by reading true. `agent.py` claimed "the pause
  event at the top of the loop is the only gate", `api.py` claimed disabling
  Sentinel "restores the original behaviour of pausing at every step". Neither is
  true — `Session.__post_init__` sets the `_paused` event, so `wait()` returns
  immediately. It is an operator pause control, not an approval gate. All three
  now say what is actually true. The `gate is None` branch itself is unchanged:
  `bench.py` and `cli.py` construct a loop with no gate and expect autonomy.
- **SECURITY.md claimed protections that do not exist**: "control of every
  action", and "read-only mode by default" as a mitigation for prompt injection.
  There is no read-only mode. `browse_eval` measures a before/after DOM signature
  and refuses obviously mutating JS, which is a weaker and different thing.
- **SECURITY.md and README listed file dialogs as unsupported.** `browse_set_files`
  attaches files to an `<input type=file>` directly; the native OS picker is still
  not driven, and that is now the limit that is written down.
- **README claimed "approve any action before it commits."** Whether a gate is in
  force depends on how orvima was started and whether `sentinel` is installed —
  and `sentinel` is not a declared dependency, not even an extra, so a fresh
  install holds *every* action (including `browse_snapshot`) for a human. A new
  `## Approvals` section states the three run modes and how to check which one
  you are in.

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