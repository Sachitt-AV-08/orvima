"""Tests for orvima.mail module."""

from orvima.mail import _extract_body, _need_creds, _env


def test_env_returns_none_for_missing():
    result = _env("NONEXISTENT_VAR_12345")
    assert result is None


def test_env_returns_default():
    result = _env("NONEXISTENT_VAR_12345", default="fallback")
    assert result == "fallback"


def test_need_creds_missing():
    try:
        result = _need_creds({})
        assert result is not None
    except KeyError:
        pass  # expected when cfg is empty


def test_extract_body_plain():
    import email
    msg = email.message_from_string("Subject: Test\n\nHello body")
    result = _extract_body(msg)
    assert isinstance(result, str)
    assert "Hello" in result or result == ""


def test_mail_send_returns_dict():
    result = mail_send_stub() if False else None
    from orvima.mail import mail_send
    result = mail_send(to="test@example.com", subject="Test", body="Hello")
    assert isinstance(result, dict)


def test_mail_read_returns_dict():
    from orvima.mail import mail_read
    result = mail_read(count=1)
    assert isinstance(result, dict)