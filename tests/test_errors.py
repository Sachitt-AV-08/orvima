"""Tests for orvima.errors module."""

from orvima.errors import (
    ApprovalDenied,
    BrowserError,
    OrvimaError,
    SessionNotFoundError,
    ToolNotFoundError,
)


def test_orvima_error_is_exception():
    assert issubclass(OrvimaError, Exception)


def test_browser_error_inherits_orvima_error():
    assert issubclass(BrowserError, OrvimaError)


def test_session_not_found_inherits_orvima_error():
    assert issubclass(SessionNotFoundError, OrvimaError)


def test_tool_not_found_inherits_orvima_error():
    assert issubclass(ToolNotFoundError, OrvimaError)


def test_approval_denied_inherits_orvima_error():
    assert issubclass(ApprovalDenied, OrvimaError)


def test_errors_can_be_raised_and_caught():
    for exc_cls in (OrvimaError, BrowserError, SessionNotFoundError,
                    ToolNotFoundError, ApprovalDenied):
        try:
            raise exc_cls("test message")
        except OrvimaError as e:
            assert str(e) == "test message"


def test_errors_are_distinct():
    assert BrowserError is not SessionNotFoundError
    assert ToolNotFoundError is not ApprovalDenied
    assert OrvimaError is not BrowserError