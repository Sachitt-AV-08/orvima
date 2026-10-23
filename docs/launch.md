# Orvima Launch Announcements — Open Source Browser Automation MCP

> **Meta description:** Orvima launch announcements and release notes for an open-source, local-first browser automation MCP server (Playwright alternative) with DOM-verified steps, Sentinel approval gate, OCR/vision, and 60 MCP tools.

> Drafted from the shipped code and `CHANGELOG.md`. Every capability below was verified against `src/orvima/` before being written. See "Release facts" and "Claims softened" at the end.

## Before you post: version caveat

- Current `main` registers **60 MCP tools** (code-verified). `CHANGELOG.md` labels the `vision_*` module (11 tools) under **"Unreleased"**, and the latest git tag is `v0.1.6` (no `v0.2.0` tag exists even though a `0.2.0` section is documented).
- If you are cutting the announcement from the tagged release, drop the vision claims and say **49 tools**.
- Recommended before posting: tag a release that includes vision (e.g. `v0.2.1`), and update `README.md` which still says "49 tools".
- Orvima is **not on PyPI** (the `pyproject.toml` comment notes it was never published). Install is via the one-line GitHub installer or `pip install -e .` from a clone. Do not write `pip install orvima`.

---

## 1. Reddit — r/programming

**Headline:** Show r/programming: Orvima — a 60-tool MCP server that drives your real browser, with DOM-verified steps and a local safety gate

**Body:**

Most "browser agent" tools report success when the click landed, not when the page actually changed. Orvima does the opposite: every mutating action (`browse_click`, `browse_type`, `browse_fill`, `browse_navigate`, ...) returns `{"ok": true, "verified": true|false}` after the DOM confirms the result. An unmet expectation (`expect_url`, `expect_text`, `expect_count`) is a hard error naming every mismatch, not a flag you can ignore.

It is an MCP (stdio) server, so any MCP-capable client (Claude, Cursor, Copilot, your own agent) can drive it. 60 tools across 9 domains: browser (22), mail (2), WhatsApp (5), voice (4), media (4), compute (7), gate (3), router (2), vision (11). Everything runs on `127.0.0.1`; no cloud, no required API key for the core loop.

Things that are actually different from Playwright/DevTools MCP:

- Refs are element *identities*, not positions. `e12` survives re-render; if the original element is gone Orvima looks for a substitute and **refuses rather than guessing** when two candidates are equally good. Refs work inside frames (`f2:e3`).
- `browse_eval` is an audited escape hatch, not a sandbox. It refuses expressions that look irreversible, reports `mutating` from a before/after DOM signature, and every call is recorded via `browse_eval_audit`.
- Attach to a browser you already have open, over CDP — but page-level, not browser-level. Playwright's `connect_over_cdp` enumerates every target and stalls on real profiles; Orvima opens one page's own debugger socket and returns in milliseconds. Only `127.0.0.1` is accepted.

Safety: a Sentinel gate classifies destructive actions (payments, deletes, submits) and holds them for human approval; reads and safe clicks pass through. The gate is optional, runs with zero network by default (hashing embedder, ~0.1ms), and fails closed if it misbehaves. `orvima run` (CLI) is fully unattended; `orvima serve` holds everything for approval when Sentinel is not installed.

Vision is local too: Tesseract 5 OCR with multi-pass preprocessing, template matching, face detection (Haar cascade), video frame sampling + scene-change detection. No API keys.

Install (not on PyPI):

```
# Windows
irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh
```

Then point your client at `orvima mcp`. Repo: https://github.com/Sachitt-AV-08/orvima (MIT). Honest limits: no CAPTCHA/2FA, no native file dialogs, media playback not supported (downloads are), and the gate is a classifier + word list — it is wrong in both directions.

**Key talking points:**
- Verified steps, not guessed success (`verified` flag, hard errors on unmet expectations)
- Refs are identities; refuse on ambiguity
- Page-level CDP attach that does not stall on busy profiles
- Audited `browse_eval`
- Optional local safety gate, fail-closed
- 60 tools, 9 domains, MIT, loopback only

**What NOT to say:**
- Do not call it "the best" or "the only" — comparison is on verifiable features only
- Do not claim it solves CAPTCHAs or 2FA
- Do not imply `browse_eval` is a sandbox — it is a guard, not a guarantee
- Do not say it is on PyPI
- No urgency/scarcity ("limited", "act now")
- No references to AI-generated art or raster images

---

## 2. Reddit — r/opensource

**Headline:** Show r/opensource: Orvima — local-first browser automation MCP, MIT, 60 tools, no cloud, optional safety gate

**Body:**

Orvima is an open-source (MIT) MCP server that gives any AI tool a browser on your own machine. 60 tools across 9 domains, everything on `127.0.0.1`, no telemetry, no account, no required API key for the core loop. Your cookies and sessions never leave your computer.

Why it exists: I wanted an agent that drives the browser I am actually logged into, that I can watch, pause, and stop — and that tells me whether each step worked instead of guessing. So: a live viewport over SSE, pause/resume/cancel, and DOM-verified actions.

What is in the repo:

- `src/orvima/browser.py` — `BrowserController`: your Chrome/Edge/Brave (persistent profile at `~/.orvima/profile`) or CDP attach, verify-first ops
- `src/orvima/cdp.py` — page-level CDP client (single tab socket, skips the browser handshake that stalls on busy profiles)
- `src/orvima/mcp_server.py` — MCP stdio binding (works with mcp SDK v1 and v2)
- `src/orvima/sentinel/` + `sentinel_gate.py` — optional local classifier, zero network by default, fail-closed
- `src/orvima/vision.py` — local OCR (Tesseract), template matching, face detection, video frames + scene changes
- `src/orvima/voice.py` — Edge TTS + Ultron modulation (3 styles) + Whisper STT
- `src/orvima/dashboard.py` — self-served control dashboard, no framework, no CDN

License is MIT, free forever, self-host, fork, run on your own boxes. Contributions welcome — the codebase has 782 tests with a 75% coverage gate, and demo-mode tests need no browser.

Two things I want feedback on: (1) the CDP page-socket approach vs. Playwright's browser-level attach, and (2) whether the approval-gate UX (fail-closed by default when Sentinel is missing) is the right default for a fresh install.

Install: `irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex` (Windows) or the curl equivalent. Repo: https://github.com/Sachitt-AV-08/orvima.

**Key talking points:**
- MIT, local-first, loopback only, no telemetry
- 60 tools, 9 domains, real browser profiles
- Optional safety gate, fail-closed
- 782 tests, 75% coverage gate, CI
- Self-served dashboard, no CDN

**What NOT to say:**
- Do not claim it is production-ready or enterprise-grade
- Do not imply Sentinel is installed by default (it is optional)
- Do not state telemetry/privacy guarantees beyond "loopback only, nothing sent remotely by default"
- No hype adjectives ("revolutionary", "game-changing")
- No AI raster art references

---

## 3. Reddit — r/LocalLLaMA

**Headline:** Show r/LocalLLaMA: Orvima — drive your real browser with a local LLM brain, zero API keys for the safety gate

**Body:**

If you run Ollama locally and want an agent that actually uses your logged-in browser instead of a fresh sandbox, Orvima is built for that. It is an MCP server (stdio) with 60 tools; the brain can be any OpenAI-compatible endpoint, including `http://localhost:11434/v1`.

```
export ORVIMA_LLM_BASE=http://localhost:11434/v1
export ORVIMA_LLM_MODEL=llama3.1
orvima run "summarize the top story on hacker news"
```

Or skip the built-in planner entirely and let Claude/Cursor be the brain over MCP — same tools, same verified steps.

Local-first pieces that matter for this sub:

- Safety gate uses a **hashing embedder by default** — deterministic, dependency-free, zero network, ~0.1ms per decision. No model to load, no API key. If you want better paraphrase matching, plug in Ollama's `nomic-embed-text` via `OllamaEmbedder`.
- Vision is fully local: Tesseract 5 for OCR, OpenCV for images/video. Tesseract binary is auto-detected; env override `ORVIMA_TESSERACT_PATH`. No cloud vision API.
- Voice: Edge TTS base (free, no key) + local modulation pipeline; Whisper STT when available.
- Browser attaches to your real Chrome/Edge/Brave via persistent profile or CDP. Nothing leaves `127.0.0.1`.

The gate is fail-closed: with no Sentinel installed, `orvima serve` holds *every* action (including reads) for human approval. Set `ORVIMA_SENTINEL=off` for fully unattended local runs — deliberately, and it is reported as `gate: "off"` so you can tell "switched off" from "failed to load".

Honest limits: the hashing embedder is weaker than a trained model on paraphrase (it separates lexically similar text well, but `describe()` reports which backend is live so you always know). CAPTCHAs/2FA are not solved — pause, solve, resume. Media playback is not supported (downloads are).

Install: `curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh`. Repo: https://github.com/Sachitt-AV-08/orvima (MIT).

**Key talking points:**
- Any OpenAI-compatible brain, including local Ollama
- Safety gate: zero network, no API key by default
- Local vision (Tesseract + OpenCV), local voice (Edge TTS + Whisper)
- Loopback only, real browser profiles
- Fail-closed gate with explicit off switch

**What NOT to say:**
- Do not claim the hashing embedder matches a trained model on paraphrase
- Do not imply Ollama is required (it is optional)
- Do not claim offline-only for everything (Edge TTS and Whisper may need network/model downloads)
- No hype; no AI raster art references

---

## 4. Hacker News — Show HN

**Show HN: Orvima — local-first browser automation MCP (60 tools, DOM-verified steps, optional safety gate)**

Orvima is an MCP (stdio) server that gives any AI tool 60 tools across 9 domains — browser, mail, WhatsApp, voice, media, compute, gate, router, vision — all on `127.0.0.1`, against your real browser and your logins.

The part I think is actually useful: every mutating browser action returns a `verified` flag after the DOM confirms the result, and `expect_url`/`expect_text`/`expect_count` turn an unmet expectation into a hard error instead of a flag you ignore. Refs are element identities, not positions — they survive re-render and Orvima refuses rather than guesses on ambiguity.

It drives your installed Chrome/Edge/Brave (persistent profile at `~/.orvima/profile`) or attaches to a running browser over CDP. The CDP path is page-level (one tab's own debugger socket) because Playwright's browser-level `connect_over_cdp` enumerates every target and stalls on real profiles — measured hanging at 90s on Brave with 18 targets.

Safety gate is optional and local: a classifier (hashing embedder by default, zero network, ~0.1ms) holds destructive actions (payments, deletes, submits) for human approval; reads pass through. Fail-closed if the gate is missing or misbehaving. `ORVIMA_SENTINEL=off` for deliberate unattended runs.

Vision is local Tesseract + OpenCV. Voice is Edge TTS + modulation. Brain is any OpenAI-compatible endpoint or your MCP client.

Not on PyPI. Install: `curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh` then `orvima mcp` in your client config. Repo: https://github.com/Sachitt-AV-08/orvima (MIT).

Honest limits: no CAPTCHA/2FA, no file dialogs, media playback not supported (downloads are), cross-platform browser detection is partial (macOS/Linux Chrome/Edge paths on the roadmap), and the gate is a classifier + word list — wrong in both directions.

**Key talking points:**
- Verified steps + hard errors on unmet expectations
- Refs as identities
- Page-level CDP attach
- Optional local gate, fail-closed
- 60 tools, MIT, loopback only

**What NOT to say:**
- Do not oversell safety ("safe", "secure by default" beyond loopback + fail-closed)
- Do not imply CAPTCHA/2FA support
- Do not claim PyPI availability
- No hype; no AI raster art references

---

## 5. Dev.to

**Headline:** Orvima: 60 browser tools for your AI agent, with verified steps and a local safety gate

**Body:**

### The problem

When an AI agent drives a browser, "it clicked the button" is not the same as "the page changed." Most tooling returns success on the action, not on the result, so a stale selector or a slow redirect silently looks like a win. Orvima's rule: every mutating action confirms the DOM before it reports back.

### What Orvima is

Orvima is an MCP (stdio) server. Any MCP-capable client — Claude Desktop, Claude Code, Cursor, Copilot, or your own agent — gets 60 tools across 9 domains, all running on `127.0.0.1` against your real browser and your logins. MIT licensed, no cloud, no required API key for the core loop.

### Install

```
# Windows (PowerShell)
irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex

# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh
```

Orvima is not on PyPI; the installer puts `orvima` on your PATH. From a clone you can also `pip install -e .`.

### Wire it to your client

Claude Desktop (`claude_desktop_config.json`):

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

Cursor (`.cursor/mcp.json`) is the same shape. Claude Code: `claude mcp add orvima orvima mcp`.

### Your first task

Ask your assistant: "open the top Hacker News story and summarize the comments." It calls `browse_navigate`, `browse_snapshot`, and reports back — verified, not guessed. A snapshot looks like a compact DOM outline the agent plans from; refs like `e12` are element identities, not positions, so they survive re-render.

### Verified steps

Every mutating tool returns `{"ok": true, ...}` with a `verified` flag after the page confirms the result:

```
browse_click(selector="button.submit")
# -> {"ok": true, "verified": true, ...}

browse_click(selector="button.submit", expect_text="Order placed")
# unmet expectation -> hard error naming every mismatch
```

Read tools (`browse_snapshot`, `browse_screenshot`, `browse_extract`, ...) return `ok` without `verified`. `browse_eval` returns `mutating` instead, because "did anything change" is the wrong question for arbitrary JS.

### Attach to a browser you already have open

```
# start Chrome/Edge/Brave with --remote-debugging-port=9335
export ORVIMA_ATTACH_TAB=linkedin.com   # substring of tab url or title
orvima --attach http://127.0.0.1:9335 mcp
```

The attach is page-level: it opens one tab's own debugger socket instead of Playwright's browser-level `connect_over_cdp`, which enumerates every target and can stall indefinitely on a busy profile. Only `127.0.0.1` is accepted. `ORVIMA_ATTACH_TIMEOUT` (default 10s) bounds the wait.

### Vision (all local)

`vision_ocr`, `vision_ocr_region`, `vision_find_text`, `vision_describe`, `vision_match_template`, `vision_detect_faces` (privacy-safe Haar cascade), `vision_video_frames`, `vision_video_ocr`, `vision_video_scene_changes`, `vision_compare_ocr`, and `vision_ocr_screenshot` (browser-bound). Tesseract 5 with multi-pass preprocessing and PSM auto-selection; OpenCV for images/video. No API keys. Set `ORVIMA_TESSERACT_PATH` if Tesseract is not on PATH.

### Safety gate

Sentinel classifies destructive actions (payments, deletes, form submits) and holds them for human approval; safe actions pass through. It is optional and not a declared dependency. By default it uses a hashing embedder: zero network, no API key, ~0.1ms. Fail-closed if it is missing or misbehaving — `orvima serve` without Sentinel holds *every* action for approval, including reads. `orvima run` (CLI) is fully unattended. Set `ORVIMA_SENTINEL=off` for deliberate unattended API runs.

### Voice

Edge TTS (free, no key) plus an Ultron modulation pipeline (pitch -2.5st, reverb, metallic EQ) with three styles: `ultron`, `neutral`, `calm`. Whisper STT when available. Modulation needs `scipy`/`sounddevice`/`soundfile`.

### Honest limits

- No CAPTCHA or 2FA solving — pause, solve, resume.
- No native file dialogs.
- Media playback not supported (file downloads are, via `browse_download`).
- `browse_eval` is not a sandbox — it raises the cost of a mistake, it does not make one impossible. Every call is audited.
- The gate is a classifier plus a word list; wrong in both directions.

Repo: https://github.com/Sachitt-AV-08/orvima

**Key talking points:**
- Verified steps with hard errors on unmet expectations
- Refs as identities, refuse on ambiguity
- Page-level CDP attach
- Local vision + voice
- Optional fail-closed gate

**What NOT to say:**
- Do not present `browse_eval` as a sandbox
- Do not imply CAPTCHA/2FA or media playback support
- Do not say "production-ready" or "enterprise"
- No hype; no AI raster art references

---

## 6. IndieHackers

**Headline:** I'm an under-18 student who shipped a 60-tool browser automation MCP with zero budget — Orvima

**Body:**

I'm Sachitt, and I'm under 18. Orvima is the thing I've been building: an open-source (MIT) MCP server that gives any AI tool a real browser on your own machine — 60 tools, verified steps, an optional local safety gate. Zero budget, no funding, no team. Just me, a laptop, and a lot of weekends.

### Why I built it

I wanted an agent that drives the browser I'm actually logged into, that I can watch and stop, and that tells me whether each step worked instead of guessing. The existing tools either ran in a fresh sandbox (losing my logins) or reported success on the action rather than the result. So Orvima: persistent profile, live viewport over SSE, pause/resume/cancel, and DOM-verified actions.

### What it does

- 60 tools across 9 domains: browser (22), mail, WhatsApp, voice, media, compute, gate, router, vision
- Drives your installed Chrome/Edge/Brave or attaches to a running browser over CDP
- Every mutating action returns a `verified` flag; unmet expectations are hard errors
- Local safety gate (Sentinel) holds destructive actions for human approval; zero network by default
- Local vision (Tesseract + OpenCV), local voice (Edge TTS + Ultron modulation)
- Offline demo mode for CI and tours

### Money

The product is free. I make money from a flat-scope services menu: MCP server wrapping, fixing flaky MCP servers, browser automation scripts, Orvima setup on your machine, custom recipes + gates. INR pricing, paid by UPI, 48-hour turnaround. Retainer option too. A parent or guardian is the contracting party since I'm under 18 — the tech is mine, the paperwork is theirs.

### What I learned

- Shipping a fail-closed default is uncomfortable but right: `orvima serve` with no Sentinel holds *everything* for approval. It looks broken until you explain it. The docs now explain it plainly.
- Page-level CDP attach exists because browser-level attach stalls on real profiles. That bug took longer to diagnose than to fix.
- "Verified" is a smaller feature than it sounds and a bigger deal than it looks. Returning `verified: false` instead of guessing changed how the agent plans.

### Ask

If you try it, the feedback I want most: does the default approval behavior make sense on a fresh install? And is the CDP attach story (page socket vs. browser enumeration) worth a write-up on its own?

Repo: https://github.com/Sachitt-AV-08/orvima (MIT). Install: `curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh`.

**Key talking points:**
- Under-18 founder, zero budget, open source
- Free product + paid services revenue model
- Fail-closed default as a deliberate, documented choice
- Real user pain (verified steps, real profiles)

**What NOT to say:**
- Do not inflate revenue or user numbers
- Do not claim investors, team, or funding
- Do not use urgency/scarcity
- No hype adjectives; no AI raster art references

---

## 7. Product Hunt

**Tagline:** Orvima — your browser, driven by any AI, on your machine

**Description:**

Orvima is a local-first MCP server that gives any AI tool 60 tools across 9 domains — browser, mail, WhatsApp, voice, media, compute, gate, router, vision — all on `127.0.0.1`, against your real browser and your logins. Every mutating action is DOM-verified, an optional Sentinel safety gate holds destructive actions for human approval, and a live viewport lets you watch, pause, and stop. MIT licensed, no cloud, no required API key for the core loop.

**Features:**
- 60 MCP tools, 9 domains
- DOM-verified steps (`verified` flag; hard errors on unmet expectations)
- Refs are element identities, not positions (survive re-render; refuse on ambiguity)
- Drives your installed Chrome/Edge/Brave (persistent profile) or attaches over CDP (page-level, no stall on busy profiles)
- Live viewport over SSE with pause/resume/cancel
- Optional Sentinel safety gate: zero network by default, fail-closed, remembers approved actions
- Local vision: Tesseract OCR, template matching, face detection, video frames + scene changes
- Edge TTS voice with Ultron modulation (3 styles) + Whisper STT
- Any OpenAI-compatible brain (incl. local Ollama) or your MCP client as the brain
- Offline demo mode for CI and tours
- One-line installers (Windows/macOS/Linux); self-hosted Docker/Railway/VPS
- MIT licensed

**Maker comment:**

Hey Product Hunt — I'm Sachitt, and I'm under 18. I built Orvima because I wanted an agent that drives the browser I'm actually logged into, that I can watch and stop, and that reports whether each step worked instead of guessing. It's free and MIT-licensed; I earn from a small services menu (MCP wrapping, fixing flaky servers, browser automation scripts, setup, custom gates). Two things I'd love feedback on: (1) whether the fail-closed default (holding *everything* for approval when Sentinel isn't installed) is the right first-run experience, and (2) whether page-level CDP attach is worth a standalone post. Honest limits: no CAPTCHA/2FA, no file dialogs, no media playback (downloads are), and the gate is a classifier + word list — wrong in both directions. Repo: https://github.com/Sachitt-AV-08/orvima.

**Key talking points:**
- Verified steps, real profiles, local-first
- Optional fail-closed gate
- Local vision + voice
- Free + MIT; services fund it

**What NOT to say:**
- Do not claim PyPI availability
- Do not imply CAPTCHA/2FA or media playback support
- Do not use scarcity/urgency
- No hype; no AI raster art references

---

## Release facts each draft rests on

| Fact | Source |
|------|--------|
| 60 MCP tools registered (browser 22, mail 2, whatsapp 5, voice 4, media 4, compute 7, gate 3, router 2, vision 11) | `src/orvima/mcp_server.py` registration; verified by importing each module's tool tuple |
| Vision module exists and registered (10 simple + 1 browser-bound) | `src/orvima/vision.py` (`VISION_TOOLS_SIMPLE`, `VISION_TOOLS_BROWSER`) |
| Sentinel optional, zero-network default, fail-closed | `src/orvima/sentinel/__init__.py`, `src/orvima/sentinel_gate.py`, `src/orvima/sentinel/embed.py` |
| Sentinel memory + user_requested lift | `CHANGELOG.md` "Unreleased" section |
| Page-level CDP attach, only 127.0.0.1, timeout default 10s | `src/orvima/cdp.py`, README |
| Edge TTS + Ultron modulation (pitch -2.5st, reverb 0.3, metallic, speed 0.95), 3 styles | `src/orvima/voice.py` |
| Whisper STT when available | `src/orvima/voice.py` |
| DOM-verified mutating tools + `verified` flag | README "The tools" section |
| Refs as identities, refuse on ambiguity | README |
| Audited `browse_eval` (not a sandbox) | README |
| Expectations (`expect_url`/`expect_text`/`expect_count`) hard errors | README |
| Persistent profile `~/.orvima/profile` | README |
| Loopback only by default | README, SECURITY.md |
| Approvals table (run/serve/sentinel/off) | README "Approvals" |
| Installers (irm/curl) | README quick start |
| Not on PyPI | `pyproject.toml` comment |
| 782 tests, 75% coverage gate | README |
| MIT license | LICENSE, pyproject |
| Repo URL, author Sachitt under 18 | pyproject, README "Hire me" |
| Known limits (CAPTCHA/2FA, file dialogs, media playback, partial cross-platform) | README "Known limits" |
| SaaS API `/api/deploy`, self-hosted Docker/Railway/VPS | CHANGELOG 0.2.0 |
| Version 0.2.0 documented; vision under "Unreleased"; latest tag v0.1.6 | CHANGELOG.md, `git tag` |

## Related Documentation

- [README](../README.md) — overview and quick start.
- [API Reference](api.md) — full MCP tools reference.
- [Security Policy](../SECURITY.md)
- [Disclaimer](../DISCLAIMER.md)

## Claims softened because evidence was thin

- **"60 tools"** — code confirms 60 registered, but `CHANGELOG.md` labels vision as "Unreleased" and the latest tag is `v0.1.6`. If launching from the tagged release, change to **49 tools** and drop vision. Tag a release including vision before posting, and fix `README.md` (still says 49).
- **"zero network, no API key" (Sentinel)** — true for the default hashing embedder; an optional `OllamaEmbedder` does use a local model. Sentinel is also not a declared dependency, so a fresh install may have no gate at all. Phrased as "zero network by default."
- **"real browser profiles"** — true for Chrome/Edge/Brave; cross-platform browser detection is partial (macOS/Linux paths on the roadmap). Avoid claiming all three OSes are equally supported.
- **"Edge TTS voice"** — base TTS needs `edge-tts`; modulation needs `scipy`/`sounddevice`/`soundfile`; playback needs audio libs. Phrased to imply the modulation pipeline is optional.
- **"vision/OCR/image/video recognition"** — requires Tesseract binary + OpenCV; degrades gracefully with a clear "not available" message. Not a hosted service.
- **"safety gate" strength** — explicitly documented as a classifier + word list, wrong in both directions. Never describe as "guaranteed safe" or "sandbox."
- **"no cloud"** — core loop is local; an optional SaaS API (`/api/deploy`) and optional Ollama embedder exist. Phrased as "no cloud required for the core loop."
- **Install command** — not on PyPI; must use the GitHub installer or `pip install -e .`. Never write `pip install orvima`.
- **"782 tests"** — taken from README; not re-run in this draft. Verify before posting if quoting.
- **Under-18 founder / services** — taken from README "Hire me" section; keep the parent/guardian contracting note whenever pricing is mentioned.
- **No urgency/scarcity** — none of the drafts claim limited availability, deadlines, or exclusivity; the product is free and MIT.
- **No AI raster art references** — drafts contain no image/art claims; only text, code, and the repo link.
