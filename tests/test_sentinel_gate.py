"""Tests for the Sentinel gate inside orvima.

The property that matters most is not "does it classify correctly" - Sentinel's
own suite covers that - but **what happens when Sentinel is absent, broken, or
slow**. A gate that fails open is worse than no gate, because it is trusted.
Every degradation path here is asserted to refuse.
"""

from __future__ import annotations

import pytest

from orvima.sentinel_gate import GateResult, SentinelGate, make_gate

sentinel = pytest.importorskip("sentinel", reason="sentinel not on path")

from sentinel import Classifier, ClassifierMode, HashingEmbedder, Policy  # noqa: E402


@pytest.fixture
def policy() -> Policy:
    # Classifier off: the deterministic layer is what the gate should rely on,
    # and it is fast enough to test without a model in the loop.
    return Policy(Classifier(HashingEmbedder()), classifier_mode=ClassifierMode.OFF)


@pytest.fixture
def gate(policy: Policy) -> SentinelGate:
    return SentinelGate(policy)


# --------------------------------------------------------------- the basics ----


def test_read_only_actions_run_unattended(gate: SentinelGate) -> None:
    for tool, args in (
        ("browse_snapshot", {}),
        ("browse_navigate", {"url": "https://example.com/docs"}),
        ("browse_extract", {"selector": "main"}),
        ("browse_list_tabs", {}),
        ("browse_scroll", {"direction": "down"}),
    ):
        result = gate.check(tool, args)
        assert result.allowed is True, f"{tool} was gated: {result}"


def test_purchase_asks(gate: SentinelGate) -> None:
    result = gate.check("browse_click", {"selector": "Place your order"})
    assert result.allowed is False
    assert result.risk in ("outward", "destructive")


def test_eval_always_asks(gate: SentinelGate) -> None:
    result = gate.check("browse_eval", {"expression": "fetch('/exfil', {body: document.cookie})"})
    assert result.allowed is False
    assert result.risk == "destructive"


def test_every_decision_explains_itself(gate: SentinelGate) -> None:
    """An approval a human cannot reason about is an approval they rubber-stamp."""
    for tool, args in (
        ("browse_click", {"selector": "Delete account"}),
        ("browse_navigate", {"url": "https://example.com"}),
    ):
        assert gate.check(tool, args).reason


# --------------------------------------------------------- fail-closed paths ----


def test_missing_sentinel_refuses_everything() -> None:
    """The most important test in this file.

    A gate with no classifier must not silently become a no-op. If Sentinel
    fails to import, every action needs a human - degraded, not permissive.
    """
    gate = SentinelGate(policy=None)
    for tool, args in (("browse_snapshot", {}), ("browse_click", {"selector": "Next"})):
        result = gate.check(tool, args)
        assert result.allowed is False
        assert result.degraded is True
        assert "not loaded" in result.reason


def test_a_policy_that_raises_refuses_everything(policy: Policy) -> None:
    """A gate that crashes must not become a gate that permits."""

    class Exploding:
        def evaluate(self, *a, **kw):
            raise RuntimeError("model backend died")

    gate = SentinelGate(Exploding())
    result = gate.check("browse_click", {"selector": "Next page"})
    assert result.allowed is False
    assert result.degraded is True
    assert "refusing to auto-approve" in result.reason


def test_a_policy_returning_nonsense_is_not_trusted(policy: Policy) -> None:
    """A missing decision attribute must not read as permission."""

    class Useless:
        def evaluate(self, *a, **kw):
            return object()  # no needs_human, no risk

    gate = SentinelGate(Useless())
    with pytest.raises(AttributeError):
        gate.check("browse_click", {"selector": "Next page"})


def test_snapshot_failure_while_resolving_a_ref_refuses(policy: Policy) -> None:
    def boom():
        raise RuntimeError("page closed")

    gate = SentinelGate(policy, snapshot=boom)
    result = gate.check("browse_click", {"ref": "e3"})
    assert result.allowed is False, "an unresolvable ref must not be auto-approved"


def test_page_url_lookup_failure_degrades_quietly(policy: Policy) -> None:
    """A broken page lookup must not crash the gate.

    The ref path still refuses on its own, so the action is gated anyway - the
    point is that losing page context narrows the check rather than widening it.
    """

    def boom():
        raise RuntimeError("no page")

    gate = SentinelGate(policy, page_url=boom, snapshot=lambda: None)
    result = gate.check("browse_click", {"selector": "Place your order"})
    assert result.allowed is False


def test_disabled_gate_allows_everything(gate_policy_for_disable: Policy) -> None:
    gate = SentinelGate(gate_policy_for_disable, enabled=False)
    result = gate.check("browse_eval", {"expression": "1"})
    assert result.allowed is True
    assert "disabled" in result.reason


@pytest.fixture
def gate_policy_for_disable(policy: Policy) -> Policy:
    return policy


# ----------------------------------------------------------------- ref paths ----


def test_ref_with_no_snapshot_refuses(policy: Policy) -> None:
    """orvima recommends refs, so this is the common path, not an edge case."""
    gate = SentinelGate(policy)
    result = gate.check("browse_click", {"ref": "e7"})
    assert result.allowed is False


def test_resolvable_ref_is_classified(policy: Policy) -> None:
    page = {
        "url": "https://shop.example.com/cart",
        "title": "Cart",
        "items": [{"ref": "e4", "tag": "button", "role": "button", "label": "Checkout", "text": ""}],
    }
    gate = SentinelGate(policy, snapshot=lambda: page)
    result = gate.check("browse_click", {"ref": "e4"})
    # "Checkout" is not itself destructive, but the gate resolved the element,
    # so the decision is at least grounded rather than a bare baseline.
    assert result.reason


def test_risky_ref_is_caught_after_resolution(policy: Policy) -> None:
    page = {
        "url": "https://shop.example.com/cart",
        "title": "Cart",
        "items": [{"ref": "e9", "tag": "button", "role": "button", "label": "Delete account", "text": ""}],
    }
    gate = SentinelGate(policy, snapshot=lambda: page)
    result = gate.check("browse_click", {"ref": "e9"})
    assert result.allowed is False


def test_benign_ref_is_allowed_after_resolution(policy: Policy) -> None:
    page = {
        "url": "https://example.com/list",
        "title": "List",
        "items": [{"ref": "e2", "tag": "button", "role": "button", "label": "Next page", "text": ""}],
    }
    gate = SentinelGate(policy, snapshot=lambda: page)
    result = gate.check("browse_click", {"ref": "e2"})
    assert result.allowed is True, f"benign ref was gated: {result}"


def test_ref_that_moved_between_snapshots_asks(policy: Policy) -> None:
    """orvima renumbers refs by document order, so a re-render repoints them.

    The decision was made about one button; if the page shifted, the click lands
    on another. This must ask even when the remembered text looks harmless.
    """
    pages = [
        {"url": "https://example.com", "title": "A",
         "items": [{"ref": "e3", "tag": "button", "role": "button", "label": "Next page", "text": ""}]},
        {"url": "https://example.com", "title": "A",
         "items": [{"ref": "e3", "tag": "button", "role": "button", "label": "Next page", "text": "page 2"}]},
    ]
    state = {"i": 0}

    def snap():
        page = pages[min(state["i"], len(pages) - 1)]
        state["i"] += 1
        return page

    gate = SentinelGate(policy, snapshot=snap)
    assert gate.check("browse_click", {"ref": "e3"}).allowed is True  # first look: fresh
    second = gate.check("browse_click", {"ref": "e3"})
    assert second.allowed is False, "a ref whose element changed must ask"
    assert "moved" in second.reason


def test_forget_refs_resets_staleness(policy: Policy) -> None:
    page = {
        "url": "https://example.com", "title": "A",
        "items": [{"ref": "e3", "tag": "button", "role": "button", "label": "Next", "text": ""}],
    }
    gate = SentinelGate(policy, snapshot=lambda: page)
    gate.check("browse_click", {"ref": "e3"})
    gate.forget_refs()
    assert gate.check("browse_click", {"ref": "e3"}).allowed is True


# ------------------------------------------------------------- page context ----


def test_enter_on_a_checkout_page_asks(policy: Policy) -> None:
    """Identical call, opposite outcomes, decided by the page it happens on."""
    on_docs = SentinelGate(policy, page_url=lambda: "https://example.com/docs")
    on_checkout = SentinelGate(policy, page_url=lambda: "https://shop.example.com/checkout")
    assert on_docs.check("browse_press", {"key": "Enter"}).allowed is True
    assert on_checkout.check("browse_press", {"key": "Enter"}).allowed is False


# ------------------------------------------------------------- approvals ------


def test_request_and_resolve_round_trip(policy: Policy) -> None:
    gate = SentinelGate(policy)
    request_id = gate.request_approval(
        "sess1", "browse_click", {"selector": "Place your order"},
        GateResult(allowed=False, risk="destructive", reason="financial"),
    )
    assert [r.id for r in gate.pending("sess1")] == [request_id]
    resolved = gate.resolve(request_id, approved=True)
    assert resolved is not None and resolved.tool == "browse_click"
    assert gate.pending() == []


def test_pending_is_scoped_by_session(policy: Policy) -> None:
    gate = SentinelGate(policy)
    gate.request_approval("sess1", "browse_click", {}, GateResult(allowed=False))
    gate.request_approval("sess2", "browse_click", {}, GateResult(allowed=False))
    assert len(gate.pending("sess1")) == 1
    assert len(gate.pending()) == 2


def test_resolving_an_unknown_id_is_harmless(policy: Policy) -> None:
    assert SentinelGate(policy).resolve("nope", approved=True) is None


def test_approval_detail_includes_the_element(policy: Policy) -> None:
    """A human cannot judge a click they are not told what is being clicked on."""
    gate = SentinelGate(policy)
    snapshot = {
        "url": "https://shop.example.com", "title": "Shop",
        "items": [{"ref": "e1", "tag": "button", "role": "button", "label": "Buy", "text": "Buy now"}],
    }
    request_id = gate.request_approval(
        "s", "browse_click", {"ref": "e1"}, GateResult(allowed=False), snapshot=snapshot
    )
    request = gate.resolve(request_id, approved=False)
    assert request.detail["element"]["label"] == "Buy"
    assert request.detail["page_title"] == "Shop"


def test_stats_track_the_decision_mix(policy: Policy) -> None:
    gate = SentinelGate(policy)
    gate.check("browse_snapshot", {})
    gate.check("browse_click", {"selector": "Delete account"})
    stats = gate.snapshot_stats()
    assert stats["evaluated"] == 2
    assert stats["auto_approved"] == 1
    assert stats["prompted"] == 1


# ------------------------------------------------------------- construction ----


def test_make_gate_builds_a_working_policy() -> None:
    gate = make_gate(classifier_mode="off")
    assert gate.available is True
    assert gate.check("browse_snapshot", {}).allowed is True
    assert gate.check("browse_click", {"selector": "Delete account"}).allowed is False


def test_make_gate_never_raises() -> None:
    """Construction must not be able to take the server down."""
    gate = make_gate(classifier_mode="nonsense", page_url=lambda: None, snapshot=lambda: None)
    assert isinstance(gate, SentinelGate)
