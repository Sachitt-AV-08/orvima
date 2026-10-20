"""whatsapp_* tools: drive your installed WhatsApp Desktop via parley.

Wraps parley's Session (CDP attach to WhatsApp Desktop) into the same
dict-in/dict-out contract as browse_*/mail_*. All tools are read-only by
default; sending requires WhatsApp Desktop running and PARLEY_ALLOW_TO set
for recipient allowlisting.

Credentials/config come from environment variables:
    PARLEY_DEMO=1          use the offline simulator (no WhatsApp Desktop needed)
    PARLEY_CDP_HOST        CDP host (default 127.0.0.1)
    PARLEY_CDP_PORT        CDP port (default 9222)
    PARLEY_ALLOW_TO        comma-separated recipient allowlist for sends
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make parley importable without installing it into orvima's venv.
_PARLEY_SRC = Path(__file__).resolve().parents[3] / "parley" / "src"
if _PARLEY_SRC.exists() and str(_PARLEY_SRC) not in sys.path:
    sys.path.insert(0, str(_PARLEY_SRC))

try:
    from parley.session import parley_connect
    _PARLEY_AVAILABLE = True
except ImportError:
    _PARLEY_AVAILABLE = False


def _session(demo: bool | None = None):
    if not _PARLEY_AVAILABLE:
        raise RuntimeError("parley not found; install parley-wa or set PARLEY_SRC")
    return parley_connect(demo=demo)


def whatsapp_status(demo: bool | None = None) -> dict:
    """Return WhatsApp attach health and login state."""
    try:
        s = _session(demo)
        st = s.status()
        s.close() if hasattr(s, "close") else None
        return {"ok": True, **st}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_list_chats(limit: int = 50, unread_only: bool = False, demo: bool | None = None) -> dict:
    """List recent WhatsApp conversations (id, name, unread, pinned, last message)."""
    try:
        s = _session(demo)
        chats = s.chats(limit=limit, unread_only=unread_only)
        out = []
        for c in chats:
            out.append({
                "id": c.id, "name": c.name, "is_group": c.is_group,
                "unread": c.unread, "pinned": c.pinned,
                "last_message": c.last_message, "last_timestamp": c.last_timestamp,
            })
        s.close() if hasattr(s, "close") else None
        return {"ok": True, "chats": out}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_read(chat: str, limit: int = 50, demo: bool | None = None) -> dict:
    """Read recent messages from one WhatsApp chat.

    `chat` accepts a chat id, contact name, group subject, or phone number.
    """
    try:
        s = _session(demo)
        chat_id, name = s.resolve_recipient(chat)
        msgs = s.messages(chat_id, limit=limit)
        out = []
        for m in msgs:
            out.append({
                "id": m.id, "chat": m.chat, "author": m.author,
                "text": m.text, "timestamp": m.timestamp,
                "from_me": m.from_me, "kind": m.kind,
            })
        s.close() if hasattr(s, "close") else None
        return {"ok": True, "chat": chat_id, "name": name, "messages": out}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_send(to: str, text: str, demo: bool | None = None) -> dict:
    """Send a text message via WhatsApp Desktop.

    Requires WhatsApp Desktop running (or PARLEY_DEMO=1). Recipients are
    resolved by name, number, or chat id.
    """
    try:
        s = _session(demo)
        sent = s.send(to, text)
        s.close() if hasattr(s, "close") else None
        return {"ok": True, "chat": sent.chat, "id": sent.id, "text": sent.text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_react(message_id: str, emoji: str = "", demo: bool | None = None) -> dict:
    """React to a WhatsApp message with an emoji (empty string clears)."""
    try:
        s = _session(demo)
        s.react(message_id, emoji or None)
        s.close() if hasattr(s, "close") else None
        return {"ok": True, "message": message_id, "emoji": emoji}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


WHATSAPP_TOOLS = (
    whatsapp_status,
    whatsapp_list_chats,
    whatsapp_read,
    whatsapp_send,
    whatsapp_react,
)
