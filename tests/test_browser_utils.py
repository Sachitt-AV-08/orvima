"""Tests for orvima.browser utility functions."""

from orvima.browser import detect_channel, _bare_ref, _cdp_endpoint_alive, bundled_chromium_path


def test_detect_channel_returns_string_or_none():
    result = detect_channel()
    assert result is None or isinstance(result, str)


def test_bare_ref():
    result = _bare_ref("ref_123")
    assert isinstance(result, str)


def test_cdp_endpoint_alive_false():
    result = _cdp_endpoint_alive("http://localhost:99999")
    assert result is False


def test_bundled_chromium_path():
    result = bundled_chromium_path()
    assert result is None or isinstance(result, str)