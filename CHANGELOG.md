# Changelog

All notable changes to Orvima will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-26

### Added
- 60 MCP tools across 9 domains (Browse, Mail, WhatsApp, Voice, Media, Compute, Gate, Router, Vision)
- Sentinel probability score (0.0-1.0 calibrated approval likelihood) in GateResult
- Errands recipe-first routing in agent loop (cached plan replay before generative planning)
- Ollama planner fallback (independent AI assistant mode without cloud keys)
- Plan-aware gating: plan text flows through to Sentinel's risk escalation
- Voice personas: 5 (ultron, vision, crisp, calm, neutral), all male; SSML emotions via post-processing
- Vision module: 11 tools (OCR 92%+ conf, template match, faces, video frames/OCR/scene changes)
- Tesseract 5.5.3 + OpenCV 5.0.0 + Pillow vision stack
- Strong-request override (Jev-style user_requested) wired into agent loop
- Approval memory: exact previously-human-approved actions auto-approve
- Disclaimer.md + Security.md liability declarations
- Promo video: 35s master + 30s/15s/9:16 cuts + subtitles burned + VO mixed
- Branding guide (docs/branding.md), launch announcements (docs/launch.md)
- Starlette TestClient replaced with _SyncASGIClient shim (9 test files)
- Annotation tests expanded to all 60 tools
- W7/W9/W10-W20 audit warnings fixed

### Changed
- OCR confidence threshold 40 → 50 (92%+ on clean English text)
- Voice default persona: ultron → vision (BrianNeural male warm)
- Tool count: 49 → 60

## [0.2.0] - 2026-10-21

### Added
- 49 MCP tools across 8 categories (Browser, Mail, WhatsApp, Voice, Media, Compute, Science, Gate, Router)
- DOM-verified browser actions (`verified: true/false` in every response)
- Safety gates: automatic classification of destructive actions, human approval required, auto-expiry
- SaaS API: `/api/deploy` endpoint for on-demand browser sessions with CDP URLs
- MCP server with `--mode real` and `--browser chromium` support
- MCP server with `nest_asyncio` fix and running-loop fix
- Edge TTS voice tools with 3 styles and Ultron modulation (pitch -2.5st, reverb, metallic EQ)
- WhatsApp Web automation (send, read, media, contacts, groups)
- SMTP/IMAP mail tools with Brevo API fallback
- Self-hosted deployment support (Docker, Railway, VPS)

### Fixed
- MCP server async loop issues with `nest_asyncio.apply()`
- Browser launch race conditions
- Memory leaks in session management

### Security
- Safety gates enabled by default
- Destructive action classification (payments, deletes, form submits)
- Human approval required for destructive actions
- Auto-expiring approval requests
- No cloud dependencies by default

## [0.1.0] - 2026-10-15

### Added
- Initial MCP server implementation
- Basic browser tools (navigate, click, type, snapshot)
- Basic mail tools (SMTP/IMAP)
- Demo mode for testing
- Basic CLI interface

---

## Upgrade Guide

### From 0.1.x to 0.2.0

1. Update dependencies: `pip install -e . --upgrade`
2. Review new safety gate configuration
3. Update any custom tool integrations to handle `verified` field in responses
4. Configure environment variables for mail/WhatsApp/voice tools
## [0.2.1] - 2026-10-23

### Added
- vision_* module (11 tools): OCR + image recognition + video analysis, all local.
  - vision_ocr (multi-pass preprocessed + PSM auto-selection)
  - vision_ocr_region, vision_find_text, vision_describe, vision_match_template,
  vision_detect_faces (privacy-safe Haar-cascade)
  - vision_video_frames, vision_video_ocr, vision_video_scene_changes
  - vision_compare_ocr, vision_ocr_screenshot
- Local-first: Tesseract 5 + OpenCV, no network, no API keys. Tesseract
  binary auto-detected (env override ORVIMA_TESSERACT_PATH).
- Sentinel approval memory: exact actions previously approved by a human are
  auto-approved without re-prompting (risk=remembered); strong user requests
  can lift ask->allow but never block (jev-style user_requested).
- DISCLAIMER.md + liability section in SECURITY.md.
- Safety gate documented, fail-closed fallback preserved.

### Improved
- Sentinel integration: orvima.sentinel imports fixed (no longer requires
  top-level sentinel package; runs from bundled location).
- pyproject.toml adds opencv-python-headless, pytesseract, Pillow deps.
- All new tools carry full four-annotation hint sets.

## Unreleased
