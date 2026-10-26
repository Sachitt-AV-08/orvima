"""Tests for orvima.whatsapp module."""

from orvima.whatsapp import whatsapp_status, whatsapp_list_chats, whatsapp_read, whatsapp_send, whatsapp_react


def test_whatsapp_status_returns_dict():
    result = whatsapp_status()
    assert isinstance(result, dict)


def test_whatsapp_list_chats_returns_dict():
    result = whatsapp_list_chats()
    assert isinstance(result, dict)


def test_whatsapp_read_returns_dict():
    result = whatsapp_read("test chat")
    assert isinstance(result, dict)


def test_whatsapp_send_returns_dict():
    result = whatsapp_send("test chat", "hello")
    assert isinstance(result, dict)


def test_whatsapp_react_returns_dict():
    result = whatsapp_react("test chat", "hello")
    assert isinstance(result, dict)