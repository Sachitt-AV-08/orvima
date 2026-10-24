"""Pins orvima.mail tool behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from orvima import mail


def test_need_creds_missing():
    cfg = {"user": "", "password": "p", "host": "h", "port": 25, "use_tls": True}
    assert mail._need_creds(cfg)["ok"] is False
    cfg = {"user": "u", "password": "", "host": "h", "port": 25, "use_tls": True}
    assert mail._need_creds(cfg)["ok"] is False
    cfg = {"user": "u", "password": "p", "host": "h", "port": 25, "use_tls": True}
    assert mail._need_creds(cfg) is None


def test_smtp_config_env_fallback_and_none(monkeypatch):
    monkeypatch.delenv("ORVIMA_MAIL_HOST", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_PORT", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_USER", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_PASS", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_USE_TLS", raising=False)
    cfg = mail._smtp_config({"host": None, "port": None, "user": None, "password": None, "use_tls": None})
    assert cfg["host"] == "smtp.gmail.com"
    assert cfg["port"] == 587
    assert cfg["use_tls"] is True

    monkeypatch.setenv("ORVIMA_MAIL_HOST", "smtp.example.com")
    monkeypatch.setenv("ORVIMA_MAIL_PORT", "2525")
    monkeypatch.setenv("ORVIMA_MAIL_USE_TLS", "0")
    cfg = mail._smtp_config({"host": "h", "port": "123", "user": "u", "password": "p", "use_tls": False})
    assert cfg == {"host": "h", "port": 123, "user": "u", "password": "p", "use_tls": False}


def test_imap_config_env_and_ssl_default(monkeypatch):
    monkeypatch.delenv("ORVIMA_MAIL_IMAP_HOST", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_IMAP_PORT", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_IMAP_USE_SSL", raising=False)
    monkeypatch.setenv("ORVIMA_MAIL_HOST", "smtp.example.com")
    cfg = mail._imap_config({"host": None, "port": None, "user": None, "password": None, "use_ssl": None})
    assert cfg["host"] == "smtp.example.com"
    assert cfg["port"] == 993
    assert cfg["use_ssl"] is True

    monkeypatch.setenv("ORVIMA_MAIL_IMAP_USE_SSL", "0")
    cfg = mail._imap_config({"host": "imap.x", "port": 143, "user": "u", "password": "p", "use_ssl": None})
    assert cfg["host"] == "imap.x"
    assert cfg["port"] == 143
    assert cfg["use_ssl"] is False


def test_mail_send_no_creds(monkeypatch):
    monkeypatch.delenv("ORVIMA_MAIL_USER", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_PASS", raising=False)
    res = mail.mail_send("to@example.com", "subj", "body")
    assert res["ok"] is False
    assert "credentials" in res["error"]


def test_mail_read_no_creds(monkeypatch):
    monkeypatch.delenv("ORVIMA_MAIL_USER", raising=False)
    monkeypatch.delenv("ORVIMA_MAIL_PASS", raising=False)
    res = mail.mail_read()
    assert res["ok"] is False
    assert "credentials" in res["error"]


def test_mail_send_smtp_error():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.starttls.side_effect = RuntimeError("boom")
    with patch("orvima.mail.smtplib.SMTP", return_value=smtp):
        res = mail.mail_send("to@example.com", "s", "b", user="u", password="p", use_tls=True)
    assert res["ok"] is False
    assert "boom" in res["error"]


def test_mail_send_success_tls():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch("orvima.mail.smtplib.SMTP", return_value=smtp):
        res = mail.mail_send("to@example.com", "subj", "body", user="u", password="p", host="h", port=587, use_tls=True)
    assert res == {"ok": True, "to": "to@example.com", "subject": "subj"}
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("u", "p")
    smtp.send_message.assert_called_once()


def test_mail_send_ssl_path():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch("orvima.mail.smtplib.SMTP_SSL", return_value=smtp):
        res = mail.mail_send("to@example.com", "s", "b", user="u", password="p", use_tls=False)
    assert res["ok"] is True
    smtp.login.assert_called_once()


def test_mail_read_imap_error():
    m = MagicMock()
    m.login.side_effect = Exception("auth fail")
    with patch("orvima.mail.imaplib.IMAP4_SSL", return_value=m):
        res = mail.mail_read(user="u", password="p")
    assert res["ok"] is False
    assert "auth fail" in res["error"]


def test_mail_read_empty_inbox():
    m = MagicMock()
    m.search.return_value = (None, [b""])
    m.select.return_value = None
    with patch("orvima.mail.imaplib.IMAP4_SSL", return_value=m):
        res = mail.mail_read(user="u", password="p", count=5)
    assert res["ok"] is True
    assert res["messages"] == []
    m.logout.assert_called_once()


def test_mail_read_success_parse():
    raw = (
        b"From: sender@example.com\r\n"
        b"Subject: Hello\r\n"
        b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Body text here"
    )
    fetch_data = [(b"1 (RFC822)", raw)]
    m = MagicMock()
    m.search.return_value = (None, [b"1"])
    m.fetch.return_value = (None, fetch_data)
    with patch("orvima.mail.imaplib.IMAP4_SSL", return_value=m):
        res = mail.mail_read(user="u", password="p", count=10)
    assert res["ok"] is True
    assert len(res["messages"]) == 1
    msg = res["messages"][0]
    assert msg["subject"] == "Hello"
    assert msg["from"] == "sender@example.com"
    assert "Body text here" in msg["preview"]


def test_extract_body_multipart():
    import email
    msg = email.message_from_bytes(
        b"Content-Type: multipart/alternative; boundary=\"b\"\r\n"
        b"\r\n"
        b"--b\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"plain part\r\n"
        b"--b--\r\n"
    )
    assert mail._extract_body(msg) == "plain part"


def test_extract_body_empty_on_exception():
    class BadMsg:
        def is_multipart(self):
            raise RuntimeError("boom")
    assert mail._extract_body(BadMsg()) == ""


def test_mail_read_count_invalid_defaults():
    m = MagicMock()
    m.search.return_value = (None, [b""])
    with patch("orvima.mail.imaplib.IMAP4_SSL", return_value=m):
        res = mail.mail_read(user="u", password="p", count="abc")
    assert res["ok"] is True


def test_mail_tools_tuple():
    assert set(mail.MAIL_TOOLS) == {mail.mail_send, mail.mail_read}
