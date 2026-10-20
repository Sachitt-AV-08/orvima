"""mail_* tools: send and read email via SMTP/IMAP, no browser needed.

These run against the local machine's network, not a browser. Credentials come
from tool arguments or environment variables so secrets are never baked into
code. Environment fallback (per-call args override):

    ORVIMA_MAIL_HOST       SMTP host (default smtp.gmail.com)
    ORVIMA_MAIL_PORT       SMTP port (default 587)
    ORVIMA_MAIL_USER       SMTP username / email address
    ORVIMA_MAIL_PASS       SMTP password or app password
    ORVIMA_MAIL_USE_TLS    "1" to use STARTTLS (default 1)
    ORVIMA_MAIL_IMAP_HOST  IMAP host (default imap.gmail.com)
    ORVIMA_MAIL_IMAP_PORT  IMAP port (default 993)
    ORVIMA_MAIL_IMAP_USE_SSL "1" to use IMAP SSL (default 1)
"""

from __future__ import annotations

import imaplib
import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _smtp_config(args: dict) -> dict:
    return {
        "host": args.get("host") or _env("ORVIMA_MAIL_HOST") or "smtp.gmail.com",
        "port": int(args.get("port") or _env("ORVIMA_MAIL_PORT") or "587"),
        "user": args.get("user") or _env("ORVIMA_MAIL_USER") or "",
        "password": args.get("password") or _env("ORVIMA_MAIL_PASS") or "",
        "use_tls": (args.get("use_tls")
                    if "use_tls" in args
                    else (_env("ORVIMA_MAIL_USE_TLS", "1") == "1")),
    }


def _imap_config(args: dict) -> dict:
    return {
        "host": args.get("host") or _env("ORVIMA_MAIL_IMAP_HOST")
                or _env("ORVIMA_MAIL_HOST") or "imap.gmail.com",
        "port": int(args.get("port") or _env("ORVIMA_MAIL_IMAP_PORT") or "993"),
        "user": args.get("user") or _env("ORVIMA_MAIL_USER") or "",
        "password": args.get("password") or _env("ORVIMA_MAIL_PASS") or "",
        "use_ssl": (args.get("use_ssl")
                    if "use_ssl" in args
                    else (_env("ORVIMA_MAIL_IMAP_USE_SSL", "1") == "1")),
    }


def _need_creds(cfg: dict) -> dict | None:
    if not cfg["user"] or not cfg["password"]:
        return {
            "ok": False,
            "error": "no mail credentials configured. set ORVIMA_MAIL_USER and "
                     "ORVIMA_MAIL_PASS (or pass user/password in the call)",
        }
    return None


def mail_send(
    to: str,
    subject: str,
    body: str,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    use_tls: bool | None = None,
) -> dict:
    """Send an email via SMTP.

    Returns {"ok": True, "to": ..., "subject": ...} on success, or
    {"ok": False, "error": ...} on failure. Credentials fall back to
    ORVIMA_MAIL_* environment variables.
    """
    cfg = _smtp_config({
        "host": host, "port": port, "user": user, "password": password,
        "use_tls": use_tls,
    })
    problem = _need_creds(cfg)
    if problem:
        return problem

    try:
        msg = EmailMessage()
        msg["From"] = cfg["user"]
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg.set_content(body)

        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
                smtp.starttls()
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30) as smtp:
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)

        return {"ok": True, "to": to, "subject": subject}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def mail_read(
    count: int = 10,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    use_ssl: bool | None = None,
) -> dict:
    """Read the most recent emails via IMAP from INBOX.

    Returns {"ok": True, "messages": [...]} where each message has
    uid, subject, from, date, and a body preview. Credentials fall back to
    ORVIMA_MAIL_* environment variables.
    """
    cfg = _imap_config({
        "host": host, "port": port, "user": user, "password": password,
        "use_ssl": use_ssl,
    })
    problem = _need_creds(cfg)
    if problem:
        return problem

    try:
        if cfg["use_ssl"]:
            m = imaplib.IMAP4_SSL(cfg["host"], cfg["port"], timeout=30)
        else:
            m = imaplib.IMAP4(cfg["host"], cfg["port"], timeout=30)
        m.login(cfg["user"], cfg["password"])
        m.select("INBOX")
        _, data = m.search(None, "ALL")
        uids = data[0].split()[-int(count):] if data[0] else []
        messages = []
        for uid in uids:
            _, fetch_data = m.fetch(uid, "(RFC822)")
            for response_part in fetch_data:
                if isinstance(response_part, tuple):
                    raw = response_part[1]
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    msg = EmailMessage()
                    msg.set_payload(raw)
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_content()
                                break
                    else:
                        body = msg.get_content()
                    messages.append({
                        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                        "subject": msg.get("Subject", ""),
                        "from": msg.get("From", ""),
                        "date": msg.get("Date", ""),
                        "preview": body[:300],
                    })
        m.logout()
        return {"ok": True, "messages": messages}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


MAIL_TOOLS = (
    mail_send,
    mail_read,
)
