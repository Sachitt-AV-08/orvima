"""Per-tool MCP annotations, derived from what each handler actually does.

m8ven's review flagged `orvima` as exposing one tool with no annotations, and
OpenAI's directory rejects tools where any of the four hints are missing or
non-boolean. The values here are not inferred from names: each was read off the
handler in `tools.py`, and the reasoning is recorded per tool so a later edit can
tell whether the hint still matches the code.

The four hints mean:

- `read_only_hint`    the call cannot change remote or local state
- `destructive_hint`  the call can delete, spend, send, or submit
- `idempotent_hint`   repeating it is safe and has no additional effect
- `open_world_hint`   the call reaches systems the user did not name up front
  (the open web, or any site whose content is attacker-influenced)

`browse_eval` is the interesting one and is deliberately not read-only: it runs
arbitrary JavaScript on a logged-in page, so it can do anything a script can do,
and its own docstring calls it "an escape hatch, not a sandbox". Marking it
read-only would be the single most misleading annotation in the set.
"""

from __future__ import annotations

from typing import NamedTuple


class ToolBehaviour(NamedTuple):
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool
    why: str


# Read-only: nothing is sent and nothing is stored.
# Destructive: can submit, spend, send, or delete.
# Idempotent: repeating reaches the same state, rather than compounding.
# Open world: the response is a live third-party page.
_BEHAVIOUR: dict[str, ToolBehaviour] = {
    "browse_snapshot": ToolBehaviour(
        True, False, True, True,
        "reads the accessibility tree and text; writes nothing to the page",
    ),
    "browse_extract": ToolBehaviour(
        True, False, True, True,
        "reads text from the page; writes nothing to the page",
    ),
    "browse_screenshot": ToolBehaviour(
        True, False, True, True,
        "renders the viewport to an image; writes nothing to the page",
    ),
    "browse_list_tabs": ToolBehaviour(
        True, False, True, False,
        "reads orvima's own tab list; touches no remote system",
    ),
    "browse_hover": ToolBehaviour(
        True, False, True, True,
        "moves the pointer, which can fire hover handlers but submits nothing",
    ),
    "browse_wait": ToolBehaviour(
        True, False, True, False,
        "sleeps; cannot affect any system",
    ),
    "browse_wait_for": ToolBehaviour(
        True, False, True, True,
        "polls for a selector until it appears; writes nothing",
    ),
    # Navigation changes browser state and reaches an untrusted site, but a
    # GET does not submit a purchase. Idempotent in effect, not in request:
    # repeating it re-fetches, which servers may treat as a new request.
    "browse_navigate": ToolBehaviour(
        False, False, False, True,
        "changes the current page and loads a URL the caller did not verify",
    ),
    "browse_go_back": ToolBehaviour(
        False, False, False, True,
        "changes history and re-requests a page; not safely repeatable",
    ),
    "browse_open_tab": ToolBehaviour(
        False, False, False, True,
        "creates a tab and loads a URL; changes browser state",
    ),
    "browse_close_tab": ToolBehaviour(
        False, False, False, False,
        "closes a tab, discarding its state; not repeatable once gone",
    ),
    "browse_switch_tab": ToolBehaviour(
        False, False, True, False,
        "changes which tab is active; a repeat is a no-op",
    ),
    "browse_scroll": ToolBehaviour(
        False, False, False, True,
        "changes scroll position only; repeating just moves further",
    ),
    "browse_press": ToolBehaviour(
        False, True, False, True,
        "sends a key; Enter on a focused control can submit a form or a purchase",
    ),
    "browse_click": ToolBehaviour(
        False, True, False, True,
        "a click can submit, pay, or delete; the most destructive common action",
    ),
    "browse_type": ToolBehaviour(
        False, True, False, True,
        "enters text into a live page; on a checkout field this writes a credential",
    ),
    "browse_fill": ToolBehaviour(
        False, True, False, True,
        "sets a field value; same credential exposure as typing",
    ),
    "browse_select": ToolBehaviour(
        False, True, False, True,
        "changes a select's value, which can fire change handlers that submit",
    ),
    "browse_set_files": ToolBehaviour(
        False, True, False, True,
        "hands files to an upload control, sending them off the machine",
    ),
    "browse_download": ToolBehaviour(
        False, True, False, True,
        "writes a file to disk and fetches it from a remote host",
    ),
    # Arbitrary JS on a logged-in page: can delete, spend, or exfiltrate.
    "browse_eval": ToolBehaviour(
        False, True, False, True,
        "runs arbitrary JS on the page; its own docstring says escape hatch, not sandbox",
    ),
    # The one genuinely read-only member of the eval family.
    "browse_eval_audit": ToolBehaviour(
        True, False, True, True,
        "reads orvima's own audit log; sentinel tests assert it cannot perform an action",
    ),
    # Mail tools are protocol-level: they speak SMTP/IMAP directly, no browser.
    "mail_send": ToolBehaviour(
        False, True, False, True,
        "sends an email to an external mail server; repeating sends duplicates",
    ),
    "mail_read": ToolBehaviour(
        True, False, True, True,
        "reads mailbox contents via IMAP; no state changes, safe to repeat",
    ),
    # WhatsApp tools (parley-backed, local WhatsApp Desktop)
    "whatsapp_status": ToolBehaviour(True, False, True, False, "reads WhatsApp attach health; no remote system"),
    "whatsapp_list_chats": ToolBehaviour(True, False, True, False, "reads chat list; no state changes"),
    "whatsapp_read": ToolBehaviour(True, False, True, False, "reads messages; no state changes"),
    "whatsapp_send": ToolBehaviour(False, True, False, True, "sends a WhatsApp message; repeating sends duplicates"),
    "whatsapp_react": ToolBehaviour(False, True, False, True, "reacts to a message; changes chat state"),
    # Voice tools
    "voice_say": ToolBehaviour(False, True, False, False, "speaks text aloud; plays audio through speakers"),
    "voice_listen": ToolBehaviour(True, False, True, False, "records and transcribes speech; read-only capture"),
    "voice_set_style": ToolBehaviour(False, False, True, False, "changes voice style setting; idempotent"),
    "voice_list_styles": ToolBehaviour(True, False, True, False, "lists available voice styles"),
    "voice_set_emotion": ToolBehaviour(False, False, True, False, "changes voice emotion; idempotent"),
    "voice_list_emotions": ToolBehaviour(True, False, True, False, "lists available emotions; read-only"),
    "voice_sample": ToolBehaviour(False, True, False, False, "generates voice sample audio; writes file"),
    # Voice call tools (free, local audio + WebRTC)
    "voice_call_speak": ToolBehaviour(False, True, False, False, "speaks text aloud to caller; plays audio"),
    "voice_call_listen": ToolBehaviour(True, False, True, False, "records and transcribes caller speech; read-only"),
    "voice_call_local": ToolBehaviour(False, True, False, False, "starts local audio conversation; uses mic/speaker"),
    "voice_call_hangup": ToolBehaviour(False, True, False, False, "ends active call; releases audio resources"),
    "voice_call_transcript": ToolBehaviour(True, False, True, False, "returns conversation transcript; read-only"),
    "voice_call_status": ToolBehaviour(True, False, True, False, "returns call status; read-only"),
    "voice_call_webrtc": ToolBehaviour(False, True, False, True, "opens WebRTC peer-to-peer call in browser"),
    # Media tools
    "youtube_transcript": ToolBehaviour(True, False, True, True, "fetches YouTube transcript; read-only"),
    "youtube_search": ToolBehaviour(True, False, True, True, "searches YouTube; read-only"),
    "music_search": ToolBehaviour(True, False, True, True, "searches for music; read-only"),
    "music_play": ToolBehaviour(False, True, False, True, "plays audio; opens system media player"),
    # Vision tools (OCR + image + video recognition, all local, no network)
    "vision_ocr": ToolBehaviour(True, False, True, False, "reads text from an image on disk; writes no state"),
    "vision_ocr_region": ToolBehaviour(True, False, True, False, "OCR of one image region; read-only"),
    "vision_find_text": ToolBehaviour(True, False, True, False, "finds a string in an image; read-only"),
    "vision_describe": ToolBehaviour(True, False, True, False, "summarises an image (size, palette, edges); read-only"),
    "vision_match_template": ToolBehaviour(True, False, True, False, "finds a template inside an image; read-only"),
    "vision_detect_faces": ToolBehaviour(True, False, True, False, "face count via Haar cascade; no identity"),
    "vision_video_frames": ToolBehaviour(False, False, False, False, "extracts frames to disk; writes files"),
    "vision_video_ocr": ToolBehaviour(False, False, False, False, "samples frames + per-frame OCR; writes frame PNGs"),
    "vision_video_scene_changes": ToolBehaviour(True, False, True, False, "detects scene cuts; read-only"),
    "vision_compare_ocr": ToolBehaviour(True, False, True, False, "runs OCR 4 rotations; read-only"),
    "vision_ocr_screenshot": ToolBehaviour(True, False, True, True, "OCR of live browser screenshot; read-only"),
    # Compute tools
    "math_solve": ToolBehaviour(True, False, True, False, "solves equations; pure computation"),
    "math_simplify": ToolBehaviour(True, False, True, False, "simplifies expressions; pure computation"),
    "math_derivative": ToolBehaviour(True, False, True, False, "computes derivatives; pure computation"),
    "math_integral": ToolBehaviour(True, False, True, False, "computes integrals; pure computation"),
    "math_plot_data": ToolBehaviour(True, False, True, False, "generates plot data; pure computation"),
    "unit_convert": ToolBehaviour(True, False, True, False, "converts units; pure computation"),
    "science_constants": ToolBehaviour(True, False, True, False, "looks up constants; read-only"),
    # Gate tools (sentinel-backed risk classifier)
    "gate_classify": ToolBehaviour(True, False, True, False, "classifies action risk; read-only analysis"),
    "gate_describe_action": ToolBehaviour(True, False, True, False, "describes action as text; read-only"),
    "gate_risk_concepts": ToolBehaviour(True, False, True, False, "checks risk concepts; read-only"),
    # Router tools (errands recipe matching)
    "goal_list_recipes": ToolBehaviour(True, False, True, False, "lists available recipes; read-only"),
    "goal_route": ToolBehaviour(True, False, True, False, "matches goal to recipe; read-only"),
}


def for_tool(name: str) -> ToolBehaviour:
    """Behaviour for a bare tool name such as ``browse_click``.

    Raises rather than defaulting, so a new tool cannot ship unannotated by
    omission: adding a handler without adding it here fails loudly.
    """
    try:
        return _BEHAVIOUR[name]
    except KeyError:
        raise KeyError(
            f"{name} has no annotation. Add it to _BEHAVIOUR with a reason - "
            "OpenAI's directory rejects tools missing any of the four hints, and "
            "a default would be a guess about whether an action can spend money."
        ) from None


def all_names() -> tuple[str, ...]:
    return tuple(sorted(_BEHAVIOUR))
