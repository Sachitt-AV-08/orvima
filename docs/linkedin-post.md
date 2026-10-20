# LinkedIn Launch Post — Orvima

## Headline
I built a browser agent that refuses to act unless it's sure.

## Body

Most browser automation tools report `ok: true` the moment a click is dispatched. They never check if anything actually changed.

I built Orvima — 49 MCP tools across 8 domains (browser, mail, WhatsApp, voice, media, math, science, safety gate) that run entirely on your machine.

The key difference: every action is DOM-verified. After a click, Orvima re-reads the page and reports `verified: true` or `verified: false`. If it can't confirm, it says so instead of guessing.

The safety gate is the part I'm most proud of. When the agent encounters a delete button or payment form, it stops, classifies the risk (safe/low/outward/destructive), and waits for a human. Approvals expire. Stale approvals are refused. It fails closed — even on a broken install.

It also has a voice. Edge TTS + pitch shift + reverb + metallic EQ = a voice that sounds like Ultron. Because why not.

MIT licensed. Self-hosted. No cloud. No API key.

🔗 GitHub: github.com/Sachitt-AV-08/orvima
🌐 Website: orvima.in

## Hashtags
#AI #MCP #BrowserAutomation #OpenSource #SelfHosted #LocalFirst #DeveloperTools #AIagents

## Media
- Attach: viral/refusal.gif (gate refusing a delete click)
- Optional: voice demo clip (Ultron voice)
