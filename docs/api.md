# Orvima API Reference

Orvima exposes 49 MCP tools across 8 categories. All tools follow the MCP protocol: `{ name, arguments }` input, structured output.

## Browser Tools (22)

| Tool | Description | Key Params |
|------|-------------|------------|
| `browse_navigate` | Navigate to a URL | `url`, `session_id` |
| `browse_click` | Click an element (DOM-verified) | `selector`, `session_id` |
| `browse_type` | Type text into an element | `selector`, `text`, `session_id` |
| `browse_snapshot` | Get LLM-friendly DOM outline | `session_id` |
| `browse_screenshot` | Capture page as base64 PNG | `session_id` |
| `browse_scroll` | Scroll page or element | `selector`, `session_id` |
| `browse_wait` | Wait for element or condition | `selector`, `timeout`, `session_id` |
| `browse_eval` | Execute JavaScript in page | `script`, `session_id` |
| `browse_back` | Navigate back | `session_id` |
| `browse_forward` | Navigate forward | `session_id` |
| `browse_refresh` | Reload page | `session_id` |
| `browse_close` | Close tab/browser | `session_id` |
| `browse_new_tab` | Open new tab | `url`, `session_id` |
| `browse_switch_tab` | Switch to tab | `tab_index`, `session_id` |
| `browse_download` | Download file | `url`, `session_id` |
| `browse_upload` | Upload file to input | `selector`, `file_path`, `session_id` |
| `browse_hover` | Hover over element | `selector`, `session_id` |
| `browse_select` | Select option in dropdown | `selector`, `value`, `session_id` |
| `browse_check` | Check/uncheck checkbox | `selector`, `checked`, `session_id` |
| `browse_focus` | Focus element | `selector`, `session_id` |
| `browse_blur` | Blur element | `selector`, `session_id` |
| `browse_drag` | Drag element to another | `from_selector`, `to_selector`, `session_id` |

**Return format:** Every browser tool returns `{ ok, verified, data, error }`. `verified: true` means the action was confirmed against the actual DOM.

---

## Mail Tools (2)

| Tool | Description |
|------|-------------|
| `mail_send` | Send email via SMTP or Brevo API |
| `mail_read` | Read emails via IMAP |

**Config:** `ORVIMA_MAIL_HOST`, `ORVIMA_MAIL_PORT`, `ORVIMA_MAIL_USER`, `ORVIMA_MAIL_PASS`, `ORVIMA_MAIL_USE_TLS`

---

## WhatsApp Tools (5)

| Tool | Description |
|------|-------------|
| `whatsapp_send` | Send message via WhatsApp Web |
| `whatsapp_read` | Read unread messages |
| `whatsapp_media` | Download media attachments |
| `whatsapp_contacts` | List contacts |
| `whatsapp_groups` | Manage group chats |

---

## Voice Tools (4)

| Tool | Description |
|------|-------------|
| `voice_speak` | Text-to-speech (Edge TTS) |
| `voice_styles` | List available voice styles |
| `voice_ssml` | Custom SSML synthesis |
| `voice_clone` | Voice cloning (if available) |

**Styles:** 3 presets with Ultron modulation (pitch -2.5st, reverb, metallic EQ)

---

## Media Tools (4)

| Tool | Description |
|------|-------------|
| `media_download` | Download file from URL |
| `media_upload` | Upload file to server |
| `media_convert` | Convert file format |
| `media_thumbnail` | Generate thumbnail |

---

## Compute Tools (7)

| Tool | Description |
|------|-------------|
| `compute_add` | Add two numbers |
| `compute_subtract` | Subtract two numbers |
| `compute_multiply` | Multiply two numbers |
| `compute_divide` | Divide two numbers |
| `compute_power` | Exponentiation |
| `compute_sqrt` | Square root |
| `compute_abs` | Absolute value |

---

## Science Tools (4)

| Tool | Description |
|------|-------------|
| `science_physics_force` | F = ma |
| `science_physics_energy` | E = mc² |
| `science_chemistry_molar_mass` | Calculate molar mass |
| `science_chemistry_ph` | Calculate pH |

---

## Gate Tools (3)

| Tool | Description |
|------|-------------|
| `gate_classify` | Classify action as destructive/safe |
| `gate_approve` | Human approval for destructive ops |
| `gate_expire` | Auto-expire pending approvals |

---

## Router Tools (2)

| Tool | Description |
|------|-------------|
| `route_request` | Smart tool selection based on intent |
| `route_fallback` | Fallback when primary tool fails |

---

## Session Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/deploy` | POST | Launch browser session, return CDP URL |
| `/api/sessions` | GET | List active sessions |
| `/api/sessions/{id}` | GET | Get session details + TTL |
| `/api/sessions/{id}` | DELETE | Destroy session |

**Deploy returns:** `{ session_id, cdp_url, ws_url, port, expires_in_minutes, connect_example }`