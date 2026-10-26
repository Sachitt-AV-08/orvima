"""Tests for orvima.backend module."""

from orvima.backend import NavigationBackend, ExpectationChecker, ExpectationSet, BrowserError


def test_navigation_backend_class():
    assert NavigationBackend is not None


def test_expectation_checker_class():
    assert ExpectationChecker is not None


def test_expectation_set_class():
    assert ExpectationSet is not None


def test_browser_error_is_exception():
    from orvima.errors import OrvimaError
    assert issubclass(BrowserError, OrvimaError)


def test_default_expect_timeout():
    from orvima.backend import DEFAULT_EXPECT_TIMEOUT_MS
    assert isinstance(DEFAULT_EXPECT_TIMEOUT_MS, int)
    assert DEFAULT_EXPECT_TIMEOUT_MS > 0