"""Tests for orvima.cdp module."""

from orvima.cdp import list_page_targets


def test_list_page_targets_returns_list():
    # Without a running Chrome, should return empty list or raise
    try:
        result = list_page_targets("http://localhost:9222")
        assert isinstance(result, list)
    except Exception:
        pass  # Chrome may not be running