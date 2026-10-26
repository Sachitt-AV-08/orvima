"""Tests for orvima.occlusion module."""

from orvima.occlusion import uncover


def test_uncover_callable():
    assert callable(uncover)