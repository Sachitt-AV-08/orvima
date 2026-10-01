"""Tests for failure classification.

The behaviour these lock down is asymmetric on purpose. Recovering from a slow
panel is worth a lot; double-charging someone is worth nothing. So the tests
spend most of their effort on the *refusals* - they assert that actions which
could commit something, and failures that cannot be understood, are left alone.

Run: pytest tests/test_recovery.py -q
"""

from __future__ import annotations

import pytest

from orvima.recovery import (
    RETRYABLE,
    FailureClass,
    classify,
    describe,
    looks_irreversible,
)

# --- what may be retried ----------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        "element not visible: #row-1",
        "no element matches selector '#panel'",
        "could not find #submit-button",
        "Timeout 10000ms exceeded waiting for #chart",
        "navigation failed: net::ERR_CONNECTION_RESET",
    ],
)
def test_transient_failures_are_retryable(error: str) -> None:
    verdict = classify(error)
    assert verdict.retryable, f"{error!r} classified as {verdict.cls.value}"
    assert verdict.cls in RETRYABLE


# --- what must never be retried --------------------------------------------

IRREVERSIBLE_ACTIONS = [
    ("browse_click", {"selector": "#submit"}),
    ("browse_click", {"selector": "button:has-text('Send')"}),
    ("browse_click", {"selector": "#pay-now"}),
    ("browse_click", {"selector": "a[href*='checkout']"}),
    ("browse_click", {"selector": "button:has-text('Place Order')"}),
    ("browse_click", {"selector": "#confirm"}),
    ("browse_click", {"selector": "button:has-text('Sign in')"}),
    ("browse_click", {"selector": "#delete-account"}),
    ("browse_click", {"selector": "#unsubscribe"}),
    ("browse_click", {"selector": "#donate"}),
    ("browse_press", {"key": "Enter"}),
]


@pytest.mark.parametrize("tool,args", IRREVERSIBLE_ACTIONS)
def test_committing_actions_are_never_retryable(tool: str, args: dict) -> None:
    found, why = looks_irreversible(tool, args)
    assert found, f"{tool} {args} was not recognised as irreversible"

    # And the reason survives, so a refusal can be explained rather than silent.
    assert why


@pytest.mark.parametrize("tool,args", IRREVERSIBLE_ACTIONS)
def test_an_irreversible_action_stays_unsafe_even_when_the_error_looks_transient(
    tool: str, args: dict
) -> None:
    """The dangerous case: a one-way action that *also* produced a retryable error.

    A timeout on "Pay" is exactly the situation where a naive loop retries and
    charges twice. Irreversibility is checked before the error is even read.
    """
    verdict = classify("Timeout 10000ms exceeded", tool=tool, args=args)
    assert verdict.cls is FailureClass.IRREVERSIBLE
    assert not verdict.retryable


@pytest.mark.parametrize(
    "error",
    [
        "something nobody has ever seen before",
        "Traceback (most recent call last): ...",
        "",
    ],
)
def test_unrecognised_failures_are_not_retried(error: str) -> None:
    """The asymmetry, stated as a test: unknown means do not touch it."""
    verdict = classify(error)
    assert not verdict.retryable
    assert verdict.cls in (FailureClass.UNKNOWN, FailureClass.FATAL)


# --- fatal still fails fast -------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        "unknown tool browse_teleport",
        "ApprovalDenied",
        "no active page - call start() first",
    ],
)
def test_fatal_errors_are_not_retryable(error: str) -> None:
    verdict = classify(error)
    assert verdict.cls is FailureClass.FATAL
    assert not verdict.retryable


# --- ordinary navigation stays retryable ------------------------------------


def test_plain_read_only_actions_are_not_flagged_irreversible() -> None:
    for args in (
        {"selector": "#search"},
        {"selector": "input[name='email']"},
        {"selector": "#row-1"},
        {"selector": "a[href*='pricing']"},
    ):
        found, _ = looks_irreversible("browse_click", args)
        assert not found, f"{args} was wrongly flagged irreversible"


def test_typing_text_that_merely_contains_a_word_is_not_flagged() -> None:
    """'order' in the *message body* is not an order.

    Only the fields that identify the action are inspected, so typing "pay my
    invoice" into a support box does not get the run frozen.
    """
    found, _ = looks_irreversible("browse_type", {"selector": "#message", "text": "I want to pay my invoice"})
    assert not found


def test_describe_says_whether_a_retry_is_allowed() -> None:
    retryable = describe(classify("Timeout 5000ms exceeded"))
    refused = describe(classify("who knows", tool="browse_click", args={"selector": "#submit"}))
    assert "may retry" in retryable
    assert "not retried" in refused
