"""Tests for orvima.phone module."""

from orvima.phone import phone_page


def test_phone_page_callable():
    assert callable(phone_page)