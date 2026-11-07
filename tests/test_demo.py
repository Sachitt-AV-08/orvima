"""Tests for orvima.demo module."""

from orvima.demo import DemoBrowser


def test_demo_browser_class():
    assert DemoBrowser is not None


def test_demo_browser_instantiation():
    backend = DemoBrowser()
    assert backend is not None