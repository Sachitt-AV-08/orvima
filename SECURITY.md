# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Orvima, please report it responsibly:

1. **Do not** open a public issue.
2. Email the maintainer at `sachittav@gmail.com` with details.
3. Include steps to reproduce, impact assessment, and any suggested fix.
4. We aim to acknowledge within 48 hours and provide a fix timeline.

## Security Model

Orvima is designed with a local-first, loopback-only security model:

- **No cloud dependencies** — everything runs on your machine at `127.0.0.1`
- **No credentials stored** — Orvima never sees, stores, or transmits your browser credentials, cookies, or session state
- **Loopback-only by default** — the HTTP API and MCP server bind to `127.0.0.1` only
- **Your browser, your profile** — Orvima uses a dedicated persistent profile (`~/.orvima/profile`) that never touches your everyday browser profile
- **You can stop it at any time** - `browse_control` (or the UI) pauses a run; the viewport streams live so you can watch and intervene
- **Redaction** - password fields, API keys, and obvious secrets are masked in snapshots, screenshots, and transcripts

On approvals, precisely: whether an action needs your sign-off depends on how
orvima was started and what is installed. It is not always on, and it is not
"every action".

| How you run it | What happens |
|----------------|--------------|
| `orvima run` (CLI) or the benchmark | **Fully unattended.** No gate; every action runs without being judged |
| `orvima serve` (HTTP API), no `sentinel` package installed | **Every action waits for you.** Nothing can be judged, so nothing is auto-approved - including reads like `browse_snapshot` |
| `orvima serve` with `sentinel` installed | Only actions the gate flags are held for approval |
| `ORVIMA_SENTINEL=off` | **Fully unattended**, deliberately. Reported as `gate: "off"` at `/api/gate/stats` |

The gate is fail-closed: if it cannot load or its classifier errors, the action
is refused rather than permitted. `GET /api/gate/stats` reports `on`, `degraded`
or `off` so "a human switched this off" and "this broke" are distinguishable.

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Local process drives your browser session | Loopback-only binding; run `orvima doctor` to verify |
| Prompt injection via page content | Redaction in snapshots; optional fail-closed approval gate; `browse_eval` measures a before/after DOM signature and refuses obviously mutating JS. **There is no read-only mode** - if you need one, do not expose the API to a page you do not trust |
| Malware running as your user | Not covered — don't run on untrusted machines |
| Exposed API port | Loopback-only binding; firewall recommended |
| Secrets in snapshots/transcripts | Automatic redaction of passwords, tokens, API keys |

## Known Limits

- **CAPTCHAs / 2FA** — Orvima cannot solve these; human takeover (pause/resume) is the intended workflow
- **File dialogs** - the native OS picker is never automated, but `browse_set_files` attaches files to an `<input type=file>` directly and reports what the page's own `FileList` ended up holding. Use pause/resume for anything a page opens in a native dialog
- **Frames** - iframes and shadow roots are traversed and their elements get frame-scoped refs like `f2:e3`. Frames that cannot be reached are listed in `notTraversed` with the src and the reason, rather than silently missing
- **CAPTCHAs on login pages** — Pause, solve manually, resume
- **Browser updates** — Chrome/Edge updates may break selectors; fixture tests catch regressions

## Disclosure Timeline

- Day 0: Vulnerability reported
- Day 1-2: Acknowledgment and triage
- Day 7: Fix timeline communicated
- Day 30: Target for fix release (sooner for critical issues)