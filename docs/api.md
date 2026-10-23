# Orvima API Reference — MCP Tools, Browser Automation, OCR & Vision

> **Meta description:** Orvima API reference for MCP tools: browser automation, mail, WhatsApp, voice, media, compute, Sentinel approval gate, router, and local-first OCR/vision. All tools run on 127.0.0.1.

Orvima exposes **60 MCP tools** across 9 categories. All tools follow the MCP
protocol: input is `{ name, arguments }`, output is a structured JSON object.
Every tool returns an envelope of the form `{"ok": true, ...}` on success and
`{"ok": false, "error": "..."}` on failure; browser tools additionally carry a
`verified` flag that is `true` only when the action was confirmed against the
live DOM.

- **Version:** Orvima `0.2.0` (package `__version__`); SaaS deploy API `0.1.0`.
- **Transport:** `orvima mcp` serves stdio MCP; `orvima serve` serves the HTTP
  API + dashboard at `http://127.0.0.1:8301`; the SaaS deploy API is a
  separate FastAPI app (`orvima.saas_api`).
- **Authentication:** The stdio MCP server runs under the caller's account and has
  no per-call auth. The HTTP API (`orvima serve`) guards acting endpoints with an
  API token: set `ORVIMA_API_TOKEN`; present it as `X-Orvima-Token` or
  `Authorization: Bearer <token>`. With no token configured the acting endpoints
  are open on loopback only — `create_app` refuses to bind to a non-loopback
  host without a token. The SaaS deploy API accepts `X-Api-Key` (default
  `"demo"`). Read-only endpoints (health, sessions list, approvals list, SSE
  stream) are unguarded so a phone/VPN client can observe state.
- **Rate limits / capacity:** No per-tool rate limit is enforced in the MCP
  server. The SaaS deploy API caps concurrent sessions at `MAX_SESSIONS` (default
  10, env `ORVIMA_SAAS_MAX_SESSIONS`) and returns HTTP 429 when full; session
  TTL is 1–1440 minutes (default 60, env `ORVIMA_SAAS_TTL_MINUTES`). Approval
  requests expire after `approval_ttl` (default 300 s).
- **Pagination:** `browse_snapshot` (`limit` 0–500, default 60; `offset`;
  `max_text` 0–40000, default 4000), `browse_extract` (`max_chars` 0–100000,
  default 8000), `mail_read` (`count`, default 10), `whatsapp_list_chats`
  (`limit`, default 50), `youtube_search`/`music_search` (`limit`, default 5),
  `vision_video_frames` (`count`, default 5), `vision_video_ocr`
  (`sample_count`, default 8). Truncated responses set `truncated: true` and
  provide `next_offset` / `total_chars`.
- **Versioning:** Tool names are unversioned (`browse_click`, not `browse_click_v2`).
  New tools may be added; clients should ignore unknown tools rather than fail.
  Behaviour hints (read-only / destructive / idempotent / open-world) are exposed
  via MCP `ToolAnnotations`.

---

## Browser Tools (22)

All browser tools take a hidden `browser`/`session` binding in the MCP server;
callers never pass it. Exposed parameters are listed below. Every browser tool
returns `{ ok, ... }` and, where an action is performed, `verified`.

### `browse_navigate`

**Description:** Open a URL. Waits for the page to be interactive and returns
URL + title. Optional `expect_url` / `expect_text` state what the page should
look like once loaded; if unmet within `expect_timeout_ms` the call fails
instead of reporting success (catches redirects to login / wrong account).

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `url` | string | required | URL to open |
| `expect_url` | string | null | substring the resulting URL must contain |
| `expect_text` | string | null | substring the resulting page must show |
| `expect_timeout_ms` | integer | 5000 | poll deadline for expectations |

**Returns:** `{ ok, url, title, verified }` (or `{ ok: false, error }`).

**Example:**
```json
{"name": "browse_navigate", "arguments": {"url": "https://example.com", "expect_text": "Welcome"}}
```

### `browse_click`

**Description:** Click an element by CSS selector OR stable ref (e.g. `e12` from
a snapshot). Prefer refs — they survive DOM churn. Returns `verified: true` if
the click caused a navigation or DOM mutation. Expectations
(`expect_url`, `expect_text`, `expect_count` + `expect_for`) judge the click
against intent instead of mere change.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `selector` | string | null | CSS selector (one of selector/ref) |
| `ref` | string | null | stable ref like `e12` (one of selector/ref) |
| `expect_url` | string | null | substring resulting URL must contain |
| `expect_text` | string | null | substring resulting page must show |
| `expect_count` | integer | null | exact number of matching elements afterwards |
| `expect_for` | string | null | selector to count (default: clicked element) |
| `expect_timeout_ms` | integer | 5000 | poll deadline |

**Returns:** `{ ok, verified, ... }`.

**Example:**
```json
{"name": "browse_click", "arguments": {"ref": "e12", "expect_url": "/dashboard"}}
```

### `browse_hover`

**Description:** Hover an element by selector or ref.

**Parameters:** `selector` (string, null), `ref` (string, null).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_hover", "arguments": {"selector": "#menu"}}
```

### `browse_select`

**Description:** Pick an option in a `<select>` by value or label, using selector
or ref.

**Parameters:** `value` (string, required), `selector` (string, null),
`ref` (string, null).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_select", "arguments": {"ref": "e5", "value": "US"}}
```

### `browse_wait_for`

**Description:** Wait until an element matching selector or ref exists.

**Parameters:** `selector` (string, null), `ref` (string, null),
`timeout_ms` (integer, default 10000).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_wait_for", "arguments": {"selector": ".loaded", "timeout_ms": 15000}}
```

### `browse_type`

**Description:** Type text into a field at a human-ish pace, by selector or ref.
Returns the field's actual value after typing and `verified`.

**Parameters:** `text` (string, required), `selector` (string, null),
`ref` (string, null).

**Returns:** `{ ok, value, verified }`.

**Example:**
```json
{"name": "browse_type", "arguments": {"ref": "e3", "text": "hello@example.com"}}
```

### `browse_fill`

**Description:** Replace the value of a field wholesale, by selector or ref.
Returns the field's actual value and `verified`.

**Parameters:** `text` (string, required), `selector` (string, null),
`ref` (string, null).

**Returns:** `{ ok, value, verified }`.

**Example:**
```json
{"name": "browse_fill", "arguments": {"selector": "#qty", "text": "2"}}
```

### `browse_press`

**Description:** Press a keyboard key, e.g. `Enter`, `Escape`, `Tab`, `ArrowDown`.

**Parameters:** `key` (string, required).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_press", "arguments": {"key": "Enter"}}
```

### `browse_go_back`

**Description:** Go back one page in history.

**Parameters:** none.

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_go_back", "arguments": {}}
```

### `browse_wait`

**Description:** Pause briefly (e.g. after a submit or before a snapshot).

**Parameters:** `ms` (integer, default 400).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_wait", "arguments": {"ms": 500}}
```

### `browse_scroll`

**Description:** Scroll the viewport: `'down'` or `'up'`.

**Parameters:** `direction` (string, default `"down"`).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_scroll", "arguments": {"direction": "down"}}
```

### `browse_snapshot`

**Description:** Describe the current page: URL, title, interactive elements and
visible text. Bounded by default (60 items / 4000 chars); raises `limit` (≤500)
and `max_text` (≤40000). Returns `total_items`, `returned`, `truncated`,
`next_offset` when more remain.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `limit` | integer | null (60) | max elements to return |
| `offset` | integer | 0 | starting offset |
| `max_text` | integer | null (4000) | max body text chars |

**Returns:** `{ ok, url, title, items, body, total_items, returned, offset,
truncated, next_offset?, body_truncated?, body_total_chars? }`.

**Example:**
```json
{"name": "browse_snapshot", "arguments": {"limit": 100, "max_text": 8000}}
```

### `browse_screenshot`

**Description:** Return the current page screenshot as base64 PNG.

**Parameters:** none.

**Returns:** `{ ok, png_b64 (or bytes/image), ... }`.

**Example:**
```json
{"name": "browse_screenshot", "arguments": {}}
```

### `browse_extract`

**Description:** Extract text from the first element matching a selector or ref.
Bounded at 8000 chars by default (`truncated: true` + `total_chars` when longer;
raise `max_chars` ≤100000).

**Parameters:** `selector` (string, null), `ref` (string, null),
`max_chars` (integer, null).

**Returns:** `{ ok, text/value/html, truncated?, total_chars?, truncated_note? }`.

**Example:**
```json
{"name": "browse_extract", "arguments": {"ref": "e7", "max_chars": 20000}}
```

### `browse_eval`

**Description:** Run a JS expression in the page (escape hatch, not a sandbox).
`reason` is recorded in the audit trail. Irreversible-looking expressions are
refused before running; `mutating` reports whether the page actually changed.

**Parameters:** `expression` (string, required), `reason` (string, null).

**Returns:** `{ ok, result, mutating, ... }`.

**Example:**
```json
{"name": "browse_eval", "arguments": {"expression": "document.title", "reason": "read page title"}}
```

### `browse_eval_audit`

**Description:** Everything `browse_eval` has run this session: expression,
reason, effect. Newest last.

**Parameters:** none.

**Returns:** `{ ok, entries: [...] }`.

**Example:**
```json
{"name": "browse_eval_audit", "arguments": {}}
```

### `browse_download`

**Description:** Click something that downloads a file and save it locally.
Returns `savedTo`, `filename`, `bytes`. Files go to `~/.orvima/downloads`
unless `ORVIMA_DOWNLOAD_DIR`. Fails explicitly when no download starts.

**Parameters:** `selector` (string, null), `ref` (string, null),
`timeout_ms` (integer, default 15000).

**Returns:** `{ ok, savedTo, filename, bytes }`.

**Example:**
```json
{"name": "browse_download", "arguments": {"ref": "e9", "timeout_ms": 20000}}
```

### `browse_set_files`

**Description:** Attach files to an `<input type=file>`. `paths` are local file
paths. Returns `pageSaw` — what the page's own FileList ended up holding.

**Parameters:** `paths` (array of strings, required), `selector` (string, null),
`ref` (string, null).

**Returns:** `{ ok, pageSaw, ... }`.

**Example:**
```json
{"name": "browse_set_files", "arguments": {"ref": "e11", "paths": ["C:/resume.pdf"]}}
```

### `browse_open_tab`

**Description:** Open a URL in a new tab and switch to it.

**Parameters:** `url` (string, required).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_open_tab", "arguments": {"url": "https://example.com"}}
```

### `browse_list_tabs`

**Description:** List open tabs with index, url and which one is active.

**Parameters:** none.

**Returns:** `{ ok, tabs: [{index, url, active}] }`.

**Example:**
```json
{"name": "browse_list_tabs", "arguments": {}}
```

### `browse_switch_tab`

**Description:** Switch to another open tab by its list index.

**Parameters:** `index` (integer, required).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_switch_tab", "arguments": {"index": 1}}
```

### `browse_close_tab`

**Description:** Close a tab by index (never the last remaining one).

**Parameters:** `index` (integer, required).

**Returns:** `{ ok, ... }`.

**Example:**
```json
{"name": "browse_close_tab", "arguments": {"index": 2}}
```

---

## Mail Tools (2)

Credentials fall back to `ORVIMA_MAIL_*` env vars; per-call args override.

### `mail_send`

**Description:** Send an email via SMTP.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `to` | string | required | recipient address |
| `subject` | string | required | subject line |
| `body` | string | required | plain-text body |
| `host` | string | null (env/default `smtp.gmail.com`) | SMTP host |
| `port` | integer | null (env/default 587) | SMTP port |
| `user` | string | null (env) | SMTP username |
| `password` | string | null (env) | SMTP password/app password |
| `use_tls` | boolean | null (env/default true) | STARTTLS |

**Returns:** `{ ok: true, to, subject }` or `{ ok: false, error }`.

**Example:**
```json
{"name": "mail_send", "arguments": {"to": "a@b.com", "subject": "hi", "body": "hello"}}
```

### `mail_read`

**Description:** Read the most recent emails via IMAP from INBOX.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `count` | integer | 10 | number of most recent messages |
| `host` | string | null (env/default `imap.gmail.com`) | IMAP host |
| `port` | integer | null (env/default 993) | IMAP port |
| `user` | string | null (env) | IMAP username |
| `password` | string | null (env) | IMAP password |
| `use_ssl` | boolean | null (env/default true) | IMAP SSL |

**Returns:** `{ ok: true, messages: [{uid, subject, from, date, preview}] }`.

**Example:**
```json
{"name": "mail_read", "arguments": {"count": 5}}
```

---

## WhatsApp Tools (5)

parley-backed; WhatsApp Desktop must be running (or `PARLEY_DEMO=1`).
Config: `PARLEY_CDP_HOST`, `PARLEY_CDP_PORT`, `PARLEY_ALLOW_TO`.

### `whatsapp_status`

**Description:** Return WhatsApp attach health and login state.

**Parameters:** `demo` (boolean, null).

**Returns:** `{ ok, ...health }`.

**Example:**
```json
{"name": "whatsapp_status", "arguments": {}}
```

### `whatsapp_list_chats`

**Description:** List recent WhatsApp conversations (id, name, unread, pinned, last
message).

**Parameters:** `limit` (integer, default 50), `unread_only` (boolean, default
false), `demo` (boolean, null).

**Returns:** `{ ok, chats: [{id, name, is_group, unread, pinned, last_message, last_timestamp}] }`.

**Example:**
```json
{"name": "whatsapp_list_chats", "arguments": {"unread_only": true, "limit": 20}}
```

### `whatsapp_read`

**Description:** Read recent messages from one WhatsApp chat. `chat` accepts a
chat id, contact name, group subject, or phone number.

**Parameters:** `chat` (string, required), `limit` (integer, default 50),
`demo` (boolean, null).

**Returns:** `{ ok, chat, name, messages: [{id, chat, author, text, timestamp, from_me, kind}] }`.

**Example:**
```json
{"name": "whatsapp_read", "arguments": {"chat": "Alice", "limit": 30}}
```

### `whatsapp_send`

**Description:** Send a text message via WhatsApp Desktop. Recipients resolved by
name, number, or chat id. Requires `PARLEY_ALLOW_TO` allowlist for sends.

**Parameters:** `to` (string, required), `text` (string, required),
`demo` (boolean, null).

**Returns:** `{ ok, chat, id, text }`.

**Example:**
```json
{"name": "whatsapp_send", "arguments": {"to": "Alice", "text": "on my way"}}
```

### `whatsapp_react`

**Description:** React to a WhatsApp message with an emoji (empty string clears).

**Parameters:** `message_id` (string, required), `emoji` (string, default `""`),
`demo` (boolean, null).

**Returns:** `{ ok, message, emoji }`.

**Example:**
```json
{"name": "whatsapp_react", "arguments": {"message_id": "msg-1", "emoji": "👍"}}
```

---

## Voice Tools (4)

Edge TTS + Ultron modulation; STT uses local Whisper.

### `voice_say`

**Description:** Speak text using Orvima's voice (Edge TTS + Ultron modulation).
Styles: `ultron` (default), `neutral`, `calm`. `play`: if true, plays audio
through speakers.

**Parameters:** `text` (string, required), `style` (string, null),
`play` (boolean, default true).

**Returns:** `{ ok, audio_path, style, text }`.

**Example:**
```json
{"name": "voice_say", "arguments": {"text": "Systems online.", "style": "ultron"}}
```

### `voice_listen`

**Description:** Listen for speech and transcribe using Whisper (local). Records
`duration` seconds then transcribes.

**Parameters:** `duration` (number, default 5.0).

**Returns:** `{ ok, text, language }`.

**Example:**
```json
{"name": "voice_listen", "arguments": {"duration": 8.0}}
```

### `voice_set_style`

**Description:** Set the current voice style: `ultron`, `neutral`, or `calm`.

**Parameters:** `style` (string, required).

**Returns:** `{ ok, style }`.

**Example:**
```json
{"name": "voice_set_style", "arguments": {"style": "calm"}}
```

### `voice_list_styles`

**Description:** List available voice styles.

**Parameters:** none.

**Returns:** `{ ok, styles: [...], current }`.

**Example:**
```json
{"name": "voice_list_styles", "arguments": {}}
```

---

## Media Tools (4)

yt-dlp based (local). `music_play` opens the system media player.

### `youtube_transcript`

**Description:** Fetch the transcript/subtitles of a YouTube video.

**Parameters:** `url` (string, required), `language` (string, default `"en"`).

**Returns:** `{ ok, title, duration, transcript }` (transcript capped at 5000
chars).

**Example:**
```json
{"name": "youtube_transcript", "arguments": {"url": "https://youtube.com/watch?v=...", "language": "en"}}
```

### `youtube_search`

**Description:** Search YouTube and return top results (title, url, duration,
channel).

**Parameters:** `query` (string, required), `limit` (integer, default 5).

**Returns:** `{ ok, query, results: [{title, url, duration, channel, views}] }`.

**Example:**
```json
{"name": "youtube_search", "arguments": {"query": "rust async", "limit": 5}}
```

### `music_search`

**Description:** Search YouTube for music and return playable results.

**Parameters:** `query` (string, required), `limit` (integer, default 5).

**Returns:** `{ ok, query, results: [{title, url, duration, channel, views}] }`.

**Example:**
```json
{"name": "music_search", "arguments": {"query": "lofi beats"}}
```

### `music_play`

**Description:** Play a YouTube video's audio using the system player (downloads
audio to a temp file).

**Parameters:** `url` (string, required).

**Returns:** `{ ok, url, file }`.

**Example:**
```json
{"name": "music_play", "arguments": {"url": "https://youtube.com/watch?v=..."}}
```

---

## Compute Tools (7)

sympy/scipy backed; all local.

### `math_solve`

**Description:** Solve a symbolic equation or expression. Examples:
`"x**2 - 4"`, `"sin(x) - 0.5"`, `"2*x + 3 = 7"`.

**Parameters:** `expression` (string, required), `variable` (string, default
`"x"`).

**Returns:** `{ ok, expression, variable, solutions: [string] }`.

**Example:**
```json
{"name": "math_solve", "arguments": {"expression": "x**2 - 4"}}
```

### `math_simplify`

**Description:** Simplify a mathematical expression.

**Parameters:** `expression` (string, required).

**Returns:** `{ ok, original, simplified }`.

**Example:**
```json
{"name": "math_simplify", "arguments": {"expression": "(x**2 - 1)/(x - 1)"}}
```

### `math_derivative`

**Description:** Compute the derivative of an expression.

**Parameters:** `expression` (string, required), `variable` (string, default
`"x"`), `order` (integer, default 1).

**Returns:** `{ ok, expression, derivative }`.

**Example:**
```json
{"name": "math_derivative", "arguments": {"expression": "x**3", "order": 2}}
```

### `math_integral`

**Description:** Compute the indefinite integral of an expression.

**Parameters:** `expression` (string, required), `variable` (string, default
`"x"`).

**Returns:** `{ ok, expression, integral }`.

**Example:**
```json
{"name": "math_integral", "arguments": {"expression": "2*x"}}
```

### `math_plot_data`

**Description:** Generate (x, y) data points for plotting an expression.

**Parameters:** `expression` (string, required), `x_min` (number, default -10),
`x_max` (number, default 10), `points` (integer, default 100).

**Returns:** `{ ok, expression, x: [number], y: [number] }`.

**Example:**
```json
{"name": "math_plot_data", "arguments": {"expression": "sin(x)", "x_min": -6.28, "x_max": 6.28, "points": 200}}
```

### `unit_convert`

**Description:** Convert between common units (length, mass, temperature, volume,
time).

**Parameters:** `value` (number, required), `from_unit` (string, required),
`to_unit` (string, required).

**Returns:** `{ ok, value, from, to, result }` or `{ ok: false, error }`.

**Example:**
```json
{"name": "unit_convert", "arguments": {"value": 100, "from_unit": "cm", "to_unit": "m"}}
```

### `science_constants`

**Description:** Look up physical/scientific constants. With no `name`, returns
the full table.

**Parameters:** `name` (string, default `""`).

**Returns:** `{ ok, name, value, unit, symbol }` or `{ ok, constants: {...} }`.

**Example:**
```json
{"name": "science_constants", "arguments": {"name": "speed_of_light"}}
```

---

## Gate Tools (3)

sentinel-backed risk classifier for browser actions.

### `gate_classify`

**Description:** Classify the risk of a browser action. Returns the risk tier
(`safe`/`low`/`outward`/`destructive`), whether a human is needed, confidence,
and reason.

**Parameters:** `tool` (string, required), `args` (object, null),
`page_url` (string, default `""`), `mode` (string, default `"advisory"` —
`off`/`advisory`/`blocking`).

**Returns:** `{ ok, tool, risk, needs_human, confidence, reason, floor, degraded }`.

**Example:**
```json
{"name": "gate_classify", "arguments": {"tool": "browse_click", "args": {"selector": "button.pay"}, "page_url": "https://example.com/checkout"}}
```

### `gate_describe_action`

**Description:** Describe what a tool call does as text (for risk matching).

**Parameters:** `tool` (string, required), `args` (object, null).

**Returns:** `{ ok, tool, description }`.

**Example:**
```json
{"name": "gate_describe_action", "arguments": {"tool": "browse_click", "args": {"selector": "Place order"}}}
```

### `gate_risk_concepts`

**Description:** Check if text matches any risk concept from sentinel's concept
list.

**Parameters:** `text` (string, required).

**Returns:** `{ ok, text, matched_concept, matched_weak, is_risky }`.

**Example:**
```json
{"name": "gate_risk_concepts", "arguments": {"text": "place your order"}}
```

---

## Router Tools (2)

errands recipe matching for goal routing.

### `goal_list_recipes`

**Description:** List all available errand recipes (name, triggers, description,
tags).

**Parameters:** `recipe_dir` (string, default `""`).

**Returns:** `{ ok, count, recipes: [{name, triggers, description, tags, match_threshold, step_count}] }`.

**Example:**
```json
{"name": "goal_list_recipes", "arguments": {}}
```

### `goal_route`

**Description:** Match a goal to a reviewed recipe or refuse. Returns the matched
recipe name, steps, and confidence; or `{ ok: false, refused: true, reason }`.

**Parameters:** `goal` (string, required), `recipe_dir` (string, default `""`).

**Returns:** `{ ok, goal, recipe, description, confidence, steps, step_count }`
or refusal.

**Example:**
```json
{"name": "goal_route", "arguments": {"goal": "buy the cheapest laptop"}}
```

---

## Vision Tools (11)

Local-first OCR + image/video recognition (Tesseract 5 + OpenCV + Pillow). No
API keys, no network. 10 file-based tools (`VISION_TOOLS_SIMPLE`) plus 1
browser-bound tool (`vision_ocr_screenshot`, registered like `browse_*`).

### `vision_ocr`

**Description:** OCR an image file and return the extracted text. Auto-preprocessed
(denoise, sharpen, Otsu threshold, deskew) with multiple PSM modes; highest
confidence wins. Returns text, word count, confidence (0–100), and per-word
boxes when `detail=true`.

**Parameters:** `image_path` (string, required), `lang` (string, default
`"eng"`), `detail` (boolean, default true).

**Returns:** `{ ok, image, size, text, word_count, confidence, mode, alternatives, boxes? }`.

**Example:**
```json
{"name": "vision_ocr", "arguments": {"image_path": "C:/shot.png", "detail": true}}
```

### `vision_ocr_region`

**Description:** OCR a rectangular region of an image in pixel coordinates. Use
after a screenshot to read one area with lower noise.

**Parameters:** `image_path` (string, required), `x`, `y`, `width`, `height`
(integers, required), `lang` (string, default `"eng"`).

**Returns:** `{ ok, text, word_count, confidence, mode, region, boxes? }`.

**Example:**
```json
{"name": "vision_ocr_region", "arguments": {"image_path": "C:/shot.png", "x": 10, "y": 20, "width": 200, "height": 60}}
```

### `vision_find_text`

**Description:** Find whether `query` appears in the image; returns its location.

**Parameters:** `image_path` (string, required), `query` (string, required),
`lang` (string, default `"eng"`), `case_sensitive` (boolean, default false).

**Returns:** `{ ok, query, found, match_count, matches, ocr_confidence }`.

**Example:**
```json
{"name": "vision_find_text", "arguments": {"image_path": "C:/shot.png", "query": "Submit"}}
```

### `vision_describe`

**Description:** Compact description of an image: dimensions, dominant colors,
edge density, complexity, horizontal lines.

**Parameters:** `image_path` (string, required).

**Returns:** `{ ok, image, width, height, aspect, edge_density, complexity,
dominant_colors, horizontal_lines }`.

**Example:**
```json
{"name": "vision_describe", "arguments": {"image_path": "C:/shot.png"}}
```

### `vision_match_template`

**Description:** Locate `template_path` inside `image_path`; return match center
coords.

**Parameters:** `image_path` (string, required), `template_path` (string,
required), `threshold` (number, default 0.8).

**Returns:** `{ ok, image, template, threshold, match_count, matches: [{center_x, center_y, top_left_x, top_left_y, confidence}] }`.

**Example:**
```json
{"name": "vision_match_template", "arguments": {"image_path": "C:/scene.png", "template_path": "C:/btn.png", "threshold": 0.85}}
```

### `vision_detect_faces`

**Description:** Detect faces with OpenCV Haar cascade; returns count + boxes only.
Privacy-safe: no identity, no recognition, no image data uploaded.

**Parameters:** `image_path` (string, required).

**Returns:** `{ ok, image, face_count, faces: [{x, y, w, h}], engine }`.

**Example:**
```json
{"name": "vision_detect_faces", "arguments": {"image_path": "C:/photo.jpg"}}
```

### `vision_video_frames`

**Description:** Extract N evenly-spaced frames from a video to disk.

**Parameters:** `video_path` (string, required), `count` (integer, default 5),
`output_dir` (string, null — defaults to `~/.orvima/video_frames`).

**Returns:** `{ ok, video, total_frames, fps, duration_s, requested, saved, frames: [{index, frame_no, timestamp_s, path, size}] }`.

**Example:**
```json
{"name": "vision_video_frames", "arguments": {"video_path": "C:/clip.mp4", "count": 8}}
```

### `vision_video_ocr`

**Description:** Per-frame OCR with timestamps (samples frames then OCRs each).

**Parameters:** `video_path` (string, required), `sample_count` (integer, default
8), `lang` (string, default `"eng"`).

**Returns:** `{ ok, video, frames_sampled, aggregate_text, frames: [{frame_index, timestamp_s, text, confidence, ok, error}] }`.

**Example:**
```json
{"name": "vision_video_ocr", "arguments": {"video_path": "C:/clip.mp4", "sample_count": 6}}
```

### `vision_video_scene_changes`

**Description:** Detect scene cuts by frame diff.

**Parameters:** `video_path` (string, required), `threshold` (number, default
0.35).

**Returns:** `{ ok, video, frames_sampled, scene_cuts_found, cuts: [{frame_no, timestamp_s, diff_score}], threshold }`.

**Example:**
```json
{"name": "vision_video_scene_changes", "arguments": {"video_path": "C:/clip.mp4", "threshold": 0.4}}
```

### `vision_compare_ocr`

**Description:** OCR an image 4 rotations × 3 modes (last-resort for
sideways/upside-down screenshots). Returns best + per-attempt scores and which
orientation read best.

**Parameters:** `image_path` (string, required), `lang` (string, default
`"eng"`).

**Returns:** `{ ok, text, word_count, confidence, mode, rotation_deg, boxes, alternatives, all_attempts }`.

**Example:**
```json
{"name": "vision_compare_ocr", "arguments": {"image_path": "C:/sideways.png"}}
```

### `vision_ocr_screenshot`

**Description:** Screenshot the bound browser's current page and OCR it.
Equivalent to `browse_screenshot` + `vision_ocr` combined; reads text that lives
in images (Canvas, embedded PDFs, image-based UI).

**Parameters:** none (browser-bound).

**Returns:** `{ ok, url, size, text, word_count, confidence, mode, boxes, alternatives }`.

**Example:**
```json
{"name": "vision_ocr_screenshot", "arguments": {}}
```

---

## Sentinel Gate Behavior

The Sentinel gate (`sentinel_gate.SentinelGate`) decides which browser actions
may run unattended and queues the rest for human approval. It is shared across
sessions and built lazily (`api.get_gate`); `ORVIMA_SENTINEL=off` disables it
entirely (fully unattended) and is reported via `gate_status()` / `/api/gate/stats`.

- **Risk tiers** (least → most severe): `safe` (reversible, private, nothing
  leaves the machine), `low` (local state change, trivially undone), `outward`
  (visible to other people), `destructive` (irreversible or financial).
- **Classifier modes:** `off` (default, deterministic layer decides alone),
  `advisory` (classifier reports an opinion, deterministic layer decides),
  `blocking` (classifier may gate; requires a calibrated classifier). Default is
  `off`/`advisory` because the classifier's top-2 margin scores AUC ≈ 0.50
  (coin flip) on the labelled set, so it is not trusted to gate.
- **Floor computation** (`Policy._floor_for`): starts from `TOOL_BASELINE` per
  tool (e.g. `browse_click` = `low`, `browse_eval` = `destructive`,
  `browse_snapshot` = `safe`); raised by risky concepts (`RISK_CONCEPTS`),
  broad-recall weak words (`WEAK_RISK_WORDS`, unless a benign suppressor applies),
  transactional URL arguments, a transactional current page URL for submitting
  tools, and plan context. The plan can only raise the floor, never lower it.
- **Ref resolution:** when an action addresses an element by `ref`, the gate
  snapshots the page to resolve it to text; if the element's text changed since
  last seen (ref reused/moved), the action is escalated regardless of how safe
  it looked.
- **Fail closed:** missing/broken Sentinel, degraded embedder, or a thrown policy
  all yield a non-allow result; a malfunction never becomes permission. With no
  policy the gate refuses everything.
- **Approval TTL:** queued requests expire after `approval_ttl` (default 300 s);
  expired requests are dropped and reported as lapsed rather than answered.
- **Audit:** every verdict carries risk, reason, confidence, degraded flag, and
  `classifier_said`; override decisions are appended to `_override_log`.

## Approval Memory

When a human approves a queued action, its signature is stored in
`_approval_memory` (`set[str]`). On subsequent identical actions the gate
auto-approves without re-running the classifier, returning
`risk: "remembered"`, `confidence: 1.0`.

- **Signature** (`_approval_signature`): `tool::selector=...::ref=...::url=...::value=...::text=...`
  (only the fields present in `args` are included). Only the *exact* same
  tool + same selector/text/etc. matches — approving "place your order" does not
  auto-approve "delete account".
- Memory is in-process and not persisted across restarts.
- Denied actions are not memorised (only approved ones).

## Strong-Request Override

`SentinelGate.check(..., user_requested=True)` models a strong, explicit user
order (Jev's `user_requested` semantics):

- If the gate would otherwise ask (not allowed) and the risk is **not**
  `destructive`, the override lifts ask→allow: returns `allowed: true`,
  `risk: "overridden"`, `confidence: 1.0`, and logs the override.
- If the risk is **`destructive`**, the override is refused: returns
  `allowed: false` with reason
  `"strong user request cannot override destructive risk: ..."`, increments
  `override_denied`, and logs it. Destructive actions are never overridable.
- Every override (allowed or denied) is appended to `_override_log` with tool,
  args, original risk, allowed flag, reason, and timestamp.

## Vision Module Architecture

- **Local-first:** Tesseract 5.x for OCR, OpenCV for image/video processing,
  Pillow for image I/O. No API keys, no network calls. Tesseract binary is
  auto-detected (PATH, common install dirs, env `ORVIMA_TESSERACT_PATH` /
  `TESSERACT_CMD`); every tool fails gracefully with a clear message when a
  dependency is missing so the MCP server never fails to load.
- **OCR pipeline** (`_best_ocr`): grayscale + denoise (fastNlMeans) + unsharp
  mask + Otsu threshold + deskew (minAreaRect), then multi-source
  (binary/grayscale) × multi-PSM (3, 6, 11); highest score (confidence +
  word count) wins. Returns `text`, `word_count`, `confidence`, `boxes`,
  `alternatives`.
- **Tools split:** `VISION_TOOLS_SIMPLE` (10 file-based tools, no browser) are
  registered without session binding; `VISION_TOOLS_BROWSER` (`vision_ocr_screenshot`)
  is registered bound to the session like `browse_*` tools, because it screenshots
  the live browser.
- **Image ops:** `vision_describe` (dimensions, palette via k-means, edge
  density, complexity, horizontal lines), `vision_match_template` (matchTemplate),
  `vision_detect_faces` (Haar cascade, count + boxes only — privacy-safe).
- **Video ops:** `vision_video_frames` (evenly-spaced frame extraction to disk),
  `vision_video_ocr` (per-frame OCR with timestamps + aggregate text),
  `vision_video_scene_changes` (scene cuts via inter-frame pixel diff).
- **Last-resort:** `vision_compare_ocr` runs 4 rotations × 3 modes for
  sideways/upside-down screenshots and reports which orientation read best.
- **Browser-bound:** `vision_ocr_screenshot` combines `browse_screenshot` +
  `vision_ocr` to read text in images (Canvas, embedded PDFs, image-based UI)
  where the accessibility tree has nothing to say.

---

## Session Management (HTTP API)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/deploy` (SaaS) | POST | Launch browser session, return CDP URL |
| `/api/sessions` | GET/POST | List / create sessions |
| `/api/sessions/{id}` | GET/DELETE | Get session details + TTL / destroy |
| `/api/sessions/{id}/frame` | GET | Screenshot of current page |
| `/api/sessions/{id}/events` | GET (SSE) | Live event stream |
| `/api/sessions/{id}/goal` | POST | Run an agent goal |
| `/api/sessions/{id}/result` | GET | Outcome of last run |
| `/api/sessions/{id}/tools` | POST | Run one browse tool directly (token-guarded) |
| `/api/sessions/{id}/control` | POST | pause / resume / cancel (token-guarded) |
| `/api/approvals` | GET | Pending approval queue (`?gate=1` includes gate health) |
| `/api/approvals/{id}` | POST | Resolve an approval (token-guarded) |
| `/api/gate/stats` | GET | Gate health + stats |
| `/api/health` | GET | Health check |
| `/api/tools` | GET | List tool names |

**Deploy returns:** `{ session_id, cdp_url, ws_url, port, expires_in_minutes, connect_example }`.

## Related Documentation

- [README](../README.md) — overview, quick start, and install.
- [Launch Announcements](launch.md) — release notes and announcement drafts.
- [Security Policy](../SECURITY.md) — supported versions and reporting.
- [Disclaimer](../DISCLAIMER.md) — liability and warranty.

## Not documented here (unstable / private / internal)

- Internal browser controller methods, `SessionStore`, `AgentLoop`, and the
  ref registry — implementation details, not part of the tool contract.
- Dashboard (`/`), phone (`/phone`), and owner (`/owner`) HTML pages and their
  supporting endpoints; owner analytics requires `X-Orvima-Owner` passphrase.
- Errands recipes directory layout and matching internals; `goal_route` only
  exposes matched steps.
- Sentinel internals (embedder selection, calibration, `observe` training data)
  beyond the gate behaviour described above.
- SaaS deploy API internals (port allocation, Chromium launch flags).
