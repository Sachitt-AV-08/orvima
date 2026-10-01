"""Tests for ref identity across a re-render.

The behaviour worth protecting is asymmetric. Silently clicking a *different*
element is much worse than refusing to click: a wrong click can submit a form,
delete a record, or pay someone. So these tests are mostly about refusals.

Run: pytest tests/test_identity.py -q
"""

from __future__ import annotations

from orvima.identity import ElementIdentity, RefRegistry

SNAPSHOT = [
    {"ref": "e1", "tag": "button", "role": "button", "label": "Save draft", "text": "Save draft"},
    {"ref": "e2", "tag": "button", "role": "button", "label": "Publish", "text": "Publish"},
    {"ref": "e3", "tag": "input", "role": "", "label": "Email", "text": ""},
]


def reg() -> RefRegistry:
    r = RefRegistry()
    r.record_snapshot(SNAPSHOT)
    return r


def ident(ref: str, **kw) -> ElementIdentity:
    base = next(i for i in SNAPSHOT if i["ref"] == ref)
    return ElementIdentity(
        ref=ref,
        role=base["role"],
        label=base["label"],
        text=base["text"],
        tag=base["tag"],
    )


# --- the happy path: nothing changed ----------------------------------------


def test_an_unchanged_ref_is_trusted() -> None:
    r = reg()
    out = r.resolve("e2", ident("e2"))
    assert out.safe
    assert "still resolves" in out.reason


def test_an_unknown_ref_is_left_to_the_normal_path() -> None:
    """No record means we never described it, so we cannot call it stale."""
    r = reg()
    out = r.resolve("e99", ElementIdentity(ref="e99", tag="button", role="button"))
    assert out.safe
    assert "no recorded identity" in out.reason


# --- the re-render case ------------------------------------------------------


def test_a_ref_whose_attribute_is_gone_resolves_to_the_same_element() -> None:
    """The whole point: e2 vanished, but 'Publish' is still on the page.

    A framework re-render replaces the node and drops the attribute, so the
    selector matches nothing. The ref must be re-resolved by identity rather
    than left to fail or, worse, land on whatever took its place.
    """
    r = reg()
    out = r.resolve("e2", current=None)
    assert not out.safe, "a missing attribute is a stale ref, not a clean lookup"
    assert out.replacement is not None
    assert out.replacement.label == "publish"


def test_the_substitute_must_be_unambiguous() -> None:
    """Two equally good candidates means the page changed in a way we do not
    understand. Refusing is the correct outcome - picking one could mean
    clicking the wrong button."""
    r = RefRegistry()
    r.record_snapshot(
        [
            {"ref": "e1", "tag": "button", "role": "button", "label": "Delete", "text": "Delete"},
            {"ref": "e2", "tag": "button", "role": "button", "label": "Delete", "text": "Delete"},
        ]
    )
    r.by_ref.pop("e1")  # pretend the registry recorded e1 but the page lost it
    r.by_ref["e1"] = ElementIdentity(
        ref="e1", role="button", label="delete", text="delete", tag="button"
    )
    out = r.resolve("e1", current=None)
    assert not out.safe
    assert out.replacement is None
    assert "no element resembles" in out.reason


def test_a_ref_that_nothing_resembles_is_reported_honestly() -> None:
    r = RefRegistry()
    r.record_snapshot(SNAPSHOT)
    r.by_ref["e1"] = ElementIdentity(
        ref="e1", role="button", label="Nuclear delete", text="Nuclear delete", tag="button"
    )
    out = r.resolve("e1", current=None)
    assert not out.safe
    assert out.replacement is None
    assert "no element resembles it" in out.reason


# --- the hijack case: the dangerous one --------------------------------------


def test_a_ref_pointing_at_a_different_element_is_refused() -> None:
    """e2 was 'Publish'. After re-numbering it points at 'Delete'.

    This is the case that must never click. The selector still resolves, so
    nothing looks wrong to a naive implementation - and the consequence is
    deleting something instead of publishing it.
    """
    r = reg()
    hijacked = ElementIdentity(ref="e2", role="button", label="Delete", text="Delete", tag="button")
    out = r.resolve("e2", hijacked)
    assert not out.safe
    assert "different element" in out.reason
    assert "publish" in out.reason, "the reason should name what was expected"


def test_a_tag_change_is_never_the_same_element() -> None:
    """A button never becomes a textbox."""
    r = reg()
    out = r.resolve("e2", ElementIdentity(ref="e2", role="", label="", text="", tag="input"))
    assert not out.safe


# --- scoring ----------------------------------------------------------------


def test_a_bare_tag_match_is_not_enough_to_substitute() -> None:
    """Otherwise every button on the page would qualify as a replacement."""
    r = RefRegistry()
    r.record_snapshot(
        [
            {"ref": "e1", "tag": "button", "role": "button", "label": "Save", "text": "Save"},
            {"ref": "e2", "tag": "button", "role": "button", "label": "Cancel", "text": "Cancel"},
        ]
    )
    # Record a third ref that the page no longer has, matching only on tag+role.
    r.by_ref["e9"] = ElementIdentity(ref="e9", role="button", label="", text="", tag="button")
    out = r.resolve("e9", current=None)
    assert out.replacement is None, "matched a different button on tag alone"


def test_matching_ignores_whitespace_and_case() -> None:
    r = reg()
    out = r.resolve(
        "e2", ElementIdentity(ref="e2", role="button", label="  PUBLISH  ", text="Publish", tag="button")
    )
    assert out.safe
