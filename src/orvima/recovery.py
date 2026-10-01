"""Failure classification for the agent loop.

The loop used to treat every failed step as fatal, so a stale ref or a slow panel
ended the run. The obvious fix - retry everything - is worse than the bug:
retrying is how you double-submit. A recovery loop that re-clicks "Pay" or
"Send" can charge someone twice, which is strictly worse than the failure it set
out to fix.

So this module answers one question, and the answer is deliberately biased:

    Is this specific failure safe to try again?

Anything not confidently recognised as transient is treated as irreversible and
left alone. A missed recovery costs one failed run; a duplicated payment costs
money and trust. When those are the two options, the asymmetry decides it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FailureClass(str, Enum):
    """What kind of failure this is, and therefore whether retrying is safe."""

    #: The element the action referred to no longer exists, or moved.
    STALE_REF = "stale-ref"
    #: Nothing matched the selector. Usually the same thing, seen from the other side.
    ELEMENT_NOT_FOUND = "element-not-found"
    #: The page or element was not ready yet. Genuinely worth waiting on.
    TIMEOUT = "timeout"
    #: The page moved under the action - a redirect, a frame swap, a load event.
    NAVIGATION = "navigation"
    #: Paying, sending, submitting, deleting. Never retried.
    IRREVERSIBLE = "irreversible"
    #: The tool does not exist, arguments are wrong, a human said no. Retrying
    #: would produce the identical failure, so it fails fast as it always has.
    FATAL = "fatal"
    #: Unrecognised. Deliberately lumped in with the do-not-retry classes.
    UNKNOWN = "unknown"


#: Classes that may be retried. Everything else stops the run.
RETRYABLE = frozenset(
    {
        FailureClass.STALE_REF,
        FailureClass.ELEMENT_NOT_FOUND,
        FailureClass.TIMEOUT,
        FailureClass.NAVIGATION,
    }
)

#: Selector and argument text that marks an action as one-way. Deliberately
#: broad: a false positive here means a form is not submitted, which the user
#: retries by hand. A false negative means a duplicate charge.
#: Selector and argument text that marks an action as one-way. Deliberately
#: broad: a false positive here means a form is not submitted, which the user
#: retries by hand. A false negative means a duplicate charge.
_IRREVERSIBLE_WORDS = (
    "submit",
    "send",
    "pay",
    "purchase",
    "checkout",
    "buy",
    "order",
    "confirm",
    "place-order",
    "sign-in",
    "signin",
    "sign in",
    "log-in",
    "login",
    "log in",
    "register",
    "subscribe",
    "donate",
    "charge",
    "transfer",
    "withdraw",
    "delete",
    "remove",
    "destroy",
    "drop",
    "revoke",
    "cancel-subscription",
    "post-submit",
)

#: Tools that can commit something even without a suggestive selector, because
#: pressing a key or submitting a form is often the irreversible half of a step.
_IRREVERSIBLE_TOOLS = frozenset({"browse_press"})

# Enter inside a form is a submit, which is why browse_press is treated as
# irreversible above rather than being retried like a click.

# Playwright and CDP phrase these differently, and the browser layer wraps them
# in its own message, so the patterns have to tolerate a prefix like
# "click '#submit' failed: ...".
_PATTERNS: tuple[tuple[FailureClass, re.Pattern[str]], ...] = (
    # A human said no. Nothing about waiting changes that.
    (
        FailureClass.FATAL,
        re.compile(
            r"approvaldenied|approval denied|denied by|not allowed|forbidden|permission",
            re.I,
        ),
    ),
    (
        FailureClass.FATAL,
        re.compile(r"unknown tool|missing .*argument|invalid argument|required", re.I),
    ),
    (FailureClass.FATAL, re.compile(r"no active page|call start\(\) first", re.I)),
    (
        FailureClass.FATAL,
        re.compile(r"browser ?.*(closed|not connected|disconnected)", re.I),
    ),
    (FailureClass.FATAL, re.compile(r"toolnotfound|orvimaerror|browserr?error", re.I)),
    (FailureClass.NAVIGATION, re.compile(r"navigation failed|net::|frame was detached|redirect", re.I)),
    (FailureClass.STALE_REF, re.compile(r"stale|detached|no longer (?:attached|in the)|node.*(?:gone|removed)", re.I)),
    (
        FailureClass.ELEMENT_NOT_FOUND,
        re.compile(r"not visible|no element|not found|element .*not|could not find|waiting for", re.I),
    ),
    (FailureClass.TIMEOUT, re.compile(r"timeout|timed out|exceeded|not loaded|still (?:fetching|loading)", re.I)),
)


@dataclass(frozen=True)
class Verdict:
    """The classification, plus why - so a refusal to retry can be explained."""

    cls: FailureClass
    reason: str

    @property
    def retryable(self) -> bool:
        return self.cls in RETRYABLE


def looks_irreversible(tool: str, args: dict | None) -> tuple[bool, str]:
    """Decide whether an *action* is one-way, before any failure is considered.

    This is checked against the action being attempted, not against the error it
    produced, because by the time an error exists the click may already have
    landed. Asking "was this click one-way?" has to happen first.

    Returns (is_irreversible, reason).
    """
    args = args or {}
    if tool in _IRREVERSIBLE_TOOLS:
        return True, f"{tool} can commit a form submission"

    # Only the arguments that *identify the action* are inspected. ``text`` and
    # ``value`` are deliberately excluded for browse_type and browse_fill: they
    # are what the user is saying, not what the agent is doing. Typing "I want
    # to pay my invoice" into a support box would otherwise read as a payment,
    # and the run would refuse to ever fill that field.
    #
    # For browse_click, ``text`` is not user content but a Playwright
    # has-text() filter, so it does describe the target and is included.
    identifying = ("selector", "ref", "key", "url")
    if tool in ("browse_click", "browse_hover"):
        identifying += ("text", "value")
    # For browse_eval the expression *is* the action - there is no other argument
    # that identifies what will happen. Without this the whole escape hatch runs
    # unclassified, which is the opposite of what the guard is for.
    if tool == "browse_eval":
        js_unsafe, why = looks_irreversible_js(args.get("expression"))
        if js_unsafe:
            return True, why
        identifying += ("expression",)

    haystack = " ".join(
        str(v) for k, v in args.items() if k in identifying and v is not None
    ).lower()

    for word in _IRREVERSIBLE_WORDS:
        if word in haystack:
            return True, f"action mentions {word!r}"
    return False, ""


#: JS that destroys state with no undo, matched on the expression itself.
#:
#: A separate list from :data:`_IRREVERSIBLE_WORDS` on purpose. That list matches
#: words in *page text* - a button called "Clear cart" - so "clear" cannot be
#: added to it without refusing an ordinary click. In an expression there is no
#: button involved, only an API call, and ``localStorage.clear()`` really does
#: destroy the page's state irrecoverably.
_IRREVERSIBLE_JS = (
    "localstorage.clear",
    "sessionstorage.clear",
    "indexeddb.deletedatabase",
    ".submit()",
    "method:'delete'",
    'method:"delete"',
    "method: 'delete'",
    'method: "delete"',
    "method:'put'",  # a destructive upsert is still a write
    "caches.delete",
    ".removechild(",
    "document.write(",
    "truncate(",
    "sendbeacon(",
    "paymentgateway.charge",
    "gateway.charge",
    ".charge(",
)


def looks_irreversible_js(expression: str) -> tuple[bool, str]:
    """Whether a JS expression destroys something with no undo.

    Checked against the expression *before* it runs, for the same reason the
    click guard checks the action before the error: once ``localStorage.clear()``
    has run, deciding it was a mistake is too late.
    """
    text = str(expression or "").lower()
    for pattern in _IRREVERSIBLE_JS:
        if pattern in text:
            return True, f"the expression contains {pattern!r}"
    return False, ""


def classify(error: object, tool: str = "", args: dict | None = None) -> Verdict:
    """Classify one failure and decide whether the loop may try again.

    The order matters. An irreversible action is checked *first* and wins even
    when the error text looks transient: a "Pay" click that timed out might well
    have gone through, and re-clicking it is how you charge someone twice. The
    error would then be the least important fact about the failure.
    """
    irreversible, why = looks_irreversible(tool, args)
    if irreversible:
        return Verdict(FailureClass.IRREVERSIBLE, why)

    text = str(error or "")

    for cls, pattern in _PATTERNS:
        if pattern.search(text):
            return Verdict(cls, f"matched {cls.value}")

    # An error that matches nothing might be anything, including a partial
    # success. Treating it as transient would be a guess; guessing here can
    # duplicate an action, so it is not a guess this module makes.
    return Verdict(FailureClass.UNKNOWN, "no pattern matched; refusing to guess")


def describe(verdict: Verdict) -> str:
    """A one-line explanation suitable for a log or a planner message."""
    if verdict.retryable:
        return f"{verdict.cls.value} ({verdict.reason}) - may retry"
    return f"{verdict.cls.value} ({verdict.reason}) - not retried"
