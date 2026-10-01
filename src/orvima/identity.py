"""Element identity, so a ref survives a re-render.

The problem
-----------
A snapshot hands the planner refs like ``e7``, which are really the attribute
``data-orvima-ref="e7"``. Those attributes are written at snapshot time by
numbering whatever was visible. If the page re-renders - a React reconciliation,
a virtualised list, an ad script swapping a container - the numbering is
reassigned and ``e7`` now points at whatever landed in seventh place. The click
then lands on a *different element*, silently.

That is worse than a failure. A dead ref that raises is a nuisance; a ref that
silently retargets is a click on the wrong button.

The fix
-------
Record what each element *was* at snapshot time - role, label, text, tag, and
its ordinal - then on lookup, if the ref resolves to something that no longer
matches, re-resolve by identity instead of trusting the number:

1. exact match on role + label + text
2. failing that, role + text
3. failing that, role + label
4. only if exactly one candidate survives

If the ref is gone and nothing matches, that is an honest "element not found"
rather than a click on a neighbour. And if the ref now resolves to an element
that is clearly *not* what the snapshot described, the click is refused rather
than redirected - the plan says a ref pointing at a genuinely different element
must be rejected, not clicked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _norm(value: Any) -> str:
    """Compare on content, not formatting."""
    return " ".join(str(value or "").split()).strip().lower()


@dataclass
class ElementIdentity:
    """What an element was when the snapshot saw it.

    Casing is preserved. Comparison normalises on the way in, so scoring stays
    case- and whitespace-insensitive, but the raw text is what a CSS selector is
    later built from - and Playwright's ``:text-is()`` is case-sensitive, so a
    lowercased label yields a selector that matches nothing and then times out
    for ten seconds.
    """

    ref: str
    role: str = ""
    label: str = ""
    text: str = ""
    tag: str = ""
    ordinal: int = 0
    #: The values as they appeared in the DOM, before normalisation.
    raw_label: str = ""
    raw_text: str = ""

    def __post_init__(self) -> None:
        self.raw_label = self.raw_label or self.label
        self.raw_text = self.raw_text or self.text
        self.role = _norm(self.role)
        self.label = _norm(self.label)
        self.text = _norm(self.text)
        self.tag = _norm(self.tag)

    @property
    def selector_label(self) -> str:
        """The label as it must appear in a selector."""
        return self.raw_label or self.label

    @property
    def selector_text(self) -> str:
        return self.raw_text or self.text

    def matches(self, other: ElementIdentity) -> bool:
        """True when two records plausibly describe the same element."""
        # The tag is the floor: a button never becomes a textbox.
        if self.tag and other.tag and self.tag != other.tag:
            return False
        if self.role and other.role and self.role != other.role:
            return False
        return True

    def score_against(self, other: ElementIdentity) -> int:
        """How well two records match. Higher is better; 0 means incompatible."""
        if not self.matches(other):
            return 0
        score = 1
        if self.label and other.label and _norm(self.label) == _norm(other.label):
            score += 4
        if self.text and other.text and _norm(self.text) == _norm(other.text):
            score += 3
        if self.tag and other.tag and self.tag == other.tag:
            score += 1
        if self.role and other.role and self.role == other.role:
            score += 1
        return score


@dataclass
class RefRegistry:
    """What each ref described, from the last snapshot.

    One of these is kept per browser. It is a cache of *identity*, not of
    elements: nothing here holds a live DOM node, so it cannot go stale in the
    way a cached handle does.
    """

    #: ref -> identity, from the most recent snapshot.
    by_ref: dict[str, ElementIdentity] = field(default_factory=dict)
    #: Everything the last snapshot saw, in document order. Used to re-resolve.
    seen: list[ElementIdentity] = field(default_factory=list)

    def record_snapshot(self, items: list[dict] | None) -> None:
        """Replace the registry's contents with a fresh snapshot."""
        self.by_ref = {}
        self.seen = []
        for i, item in enumerate(items or []):
            identity = ElementIdentity(
                ref=str(item.get("ref", f"e{i + 1}")),
                role=item.get("role") or "",
                label=item.get("label") or "",
                text=item.get("text") or "",
                tag=item.get("tag") or "",
                ordinal=i,
            )
            self.by_ref[identity.ref] = identity
            self.seen.append(identity)

    def identity_for(self, ref: str) -> ElementIdentity | None:
        return self.by_ref.get(ref)

    def resolve(self, ref: str, current: ElementIdentity | None) -> RefResolution:
        """Decide whether ``ref`` still means what the snapshot said it meant.

        ``current`` is what the ``[data-orvima-ref="eN"]`` selector actually
        matches *now* - None when nothing matches at all.
        """
        recorded = self.by_ref.get(ref)

        # No record of this ref: we never described it, so we cannot say it is
        # stale. Let the normal path handle it.
        if recorded is None:
            return RefResolution(ref, True, "no recorded identity; trusting the selector")

        # Nothing matches the attribute any more - the usual re-render case.
        if current is None:
            replacement = self._find_substitute(recorded)
            if replacement is None:
                return RefResolution(
                    ref, False, "the ref no longer matches anything and no element resembles it"
                )
            return RefResolution(
                ref,
                False,
                f"stale ref; the element it described is now {replacement.ref}",
                replacement=replacement,
            )

        # The attribute still resolves. Is it the same element?
        score = recorded.score_against(current)
        if score >= 4:
            return RefResolution(ref, True, "ref still resolves to the element it described")

        # It resolves to *something*, but not what was recorded. Two readings:
        # the page re-numbered, or the ref is pointing at the wrong element
        # entirely. Either way, clicking is unsafe.
        return RefResolution(
            ref,
            False,
            f"ref {ref} now resolves to a different element "
            f"(expected {recorded.tag or recorded.role!r} "
            f"{recorded.label or recorded.text!r}, found {current.tag or current.role!r} "
            f"{current.label or current.text!r})",
        )

    def _find_substitute(self, recorded: ElementIdentity) -> ElementIdentity | None:
        """Find the element in the last snapshot that best stands in for ``recorded``.

        Only used when the attribute is entirely gone. Ties are refused rather
        than guessed: two equally good candidates means the page changed in a
        way we do not understand, and picking one could mean clicking the wrong
        thing.
        """
        scored = [(recorded.score_against(c), c) for c in self.seen]
        # Require more than a bare tag match, or every button would qualify.
        eligible = [(score, c) for score, c in scored if score >= 5]
        if not eligible:
            return None
        best = max(score for score, _ in eligible)
        winners = [c for score, c in eligible if score == best]
        return winners[0] if len(winners) == 1 else None


@dataclass
class RefResolution:
    """The outcome of a ref check."""

    ref: str
    #: False means "do not click this" - the ref is stale or hijacked.
    safe: bool
    reason: str
    #: When the ref was gone, the element that now stands in for it.
    replacement: ElementIdentity | None = None
