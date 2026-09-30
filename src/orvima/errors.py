"""Shared errors for orvima."""

from __future__ import annotations


class OrvimaError(Exception):
    """Base error: something orvima controlled went wrong."""


class BrowserError(OrvimaError):
    """The browser could not start, or a page action failed."""


class SessionNotFoundError(OrvimaError):
    """A session id was unknown."""


class ToolNotFoundError(OrvimaError):
    """An agent asked for a tool that does not exist."""


class ApprovalDenied(OrvimaError):
    """A human denied an agent action."""
