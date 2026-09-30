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
- **Human-in-the-loop** — pause/resume/approve controls keep you in control of every action
- **Redaction** — password fields, API keys, and obvious secrets are masked in snapshots, screenshots, and transcripts

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Local process drives your browser session | Loopback-only binding; run `orvima doctor` to verify |
| Prompt injection via page content | Redaction in snapshots; human approval gate; read-only mode by default |
| Malware running as your user | Not covered — don't run on untrusted machines |
| Exposed API port | Loopback-only binding; firewall recommended |
| Secrets in snapshots/transcripts | Automatic redaction of passwords, tokens, API keys |

## Known Limits

- **CAPTCHAs / 2FA** — Orvima cannot solve these; human takeover (pause/resume) is the intended workflow
- **File dialogs** — Not supported; human takeover required
- **Iframes / Shadow DOM** — Not supported in snapshot; flagged in output
- **CAPTCHAs on login pages** — Pause, solve manually, resume
- **Browser updates** — Chrome/Edge updates may break selectors; fixture tests catch regressions

## Disclosure Timeline

- Day 0: Vulnerability reported
- Day 1-2: Acknowledgment and triage
- Day 7: Fix timeline communicated
- Day 30: Target for fix release (sooner for critical issues)