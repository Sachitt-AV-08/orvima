# Changelog

All notable changes to Orvima will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
## Unreleased

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
