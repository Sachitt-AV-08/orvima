"""Sentinel-gated approvals: ask a human only when the action warrants it.

Why this exists
---------------
An approval prompt on every step is safe and useless: a snapshot and a "place
your order" click get the same treatment, so the gate trains people to approve
without reading. This module makes the gate *conditional*, so it is asked about
the actions that deserve attention and left alone otherwise.

There was never a per-step human approval gate underneath this one to fall back
on. `Session.__post_init__` sets the `_paused` event, so the `wait()` at the top
of the run loop returns immediately; it is an operator pause control for a live
run, not a check. So "no gate" means **fully unattended**, and the callers that
supply a gate are responsible for never quietly omitting one - see
`api.get_gate`, which returns a refusing gate rather than `None` when this
module cannot be built.

Design commitments
------------------
1. **Optional dependency.** orvima runs with no Sentinel installed. Import is
   lazy and failure is a normal mode, not a crash.
2. **Fail closed, loudly.** If Sentinel is present but misbehaving - throws,
   times out, returns nonsense - the action is *not* auto-approved. The gate
   reports why. A classifier bug must never become permission. This holds at
   every layer: the gate refuses when its policy is missing, and `api.get_gate`
   refuses when *this module* is missing, so the chain has no permissive end.
3. **No LLM, no network on the decision path.** The default configuration
   (`classifier_mode=off`) decides in ~0.1 ms with pure string matching and
   cannot be taken offline by a model that failed to load.
4. **Every decision is auditable.** Verdicts land in the session transcript with
   the risk, the reason, and what the classifier thought.

Ref-resolution note
-------------------
orvima addresses elements by `ref` (e12) as well as CSS selector, and its own
docstrings recommend refs. A ref carries no text, so this module snapshots the
page to resolve it - and because orvima renumbers refs on every snapshot by
document order, it also detects when an element has *moved* since the agent last
saw it. That case is always escalated: the decision was made about one button
and the click would land on another.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ApprovalRequest",
    "GateResult",
    "SentinelGate",
    "make_gate",
]


#: Risk tiers, least to most severe. Mirrors Sentinel's ordering so a decision
#: recorded as "outward" can be compared against one that now reads "destructive".
_RISK_ORDER = ("safe", "low", "outward", "destructive")


@dataclass
class ApprovalRequest:
    """A decision the agent would like to make, and needs a yes/no on."""

    id: str
    session_id: str
    tool: str
    args: dict
    risk: str
    reason: str
    #: everything a human needs to judge without reading the code
    detail: dict = field(default_factory=dict)
    created: float = field(default_factory=time.time)

    def public(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tool": self.tool,
            "args": self.args,
            "risk": self.risk,
            "reason": self.reason,
            "detail": self.detail,
            "created": self.created,
        }


@dataclass
class GateResult:
    """Outcome of consulting the gate."""

    allowed: bool
    #: True when a human must answer, and has not yet
    pending: bool = False
    risk: str = "unknown"
    reason: str = ""
    confidence: float = 0.0
    #: True when Sentinel was unavailable or errored; the action is NOT approved
    degraded: bool = False
    classifier_said: str | None = None

    def as_log(self) -> dict:
        return {
            "allowed": self.allowed,
            "pending": self.pending,
            "risk": self.risk,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "degraded": self.degraded,
            "classifier_said": self.classifier_said,
        }


class SentinelGate:
    """Decides which actions may run unattended, and queues the rest.

    Thread-safety: the agent loop runs on its own thread and the HTTP API
    approves from another, so `_pending` is guarded. The decision itself is pure
    and runs outside the lock - holding a lock across a model call would stall
    every approval for the duration.
    """

    def __init__(
        self,
        policy: Any | None = None,
        *,
        enabled: bool = True,
        page_url: Callable[[], str] | None = None,
        snapshot: Callable[[], dict | None] | None = None,
        classifier_mode: str = "off",
        approval_ttl: float = 300.0,
    ) -> None:
        """
        `page_url` and `snapshot` let the gate see the page. Without them it
        still works, but it cannot resolve refs or notice that the agent is
        standing on a checkout page - both of which are fail-closed gaps.

        `approval_ttl` bounds how long a queued decision may sit unanswered. A
        request left open over lunch is a request that will be approved on
        autopilot against a page that has since changed.
        """
        self.enabled = enabled
        self._page_url = page_url
        self._snapshot = snapshot
        self._classifier_mode = classifier_mode
        self._policy = policy
        self._policy_error: str | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, ApprovalRequest] = {}
        #: request ids dropped for expiring, so a waiter can tell that apart
        #: from one that was answered (which also leaves the queue)
        self._lapsed: set[str] = set()
        # (session_id, ref) -> fingerprint of the text it last resolved to.
        # Keyed by session because one gate is shared by every session, and ref
        # names are per-page: without the session, session A looking at e9 and
        # then session B looking at its own e9 reads as the element having moved.
        self._seen_refs: dict[tuple[str, str], str] = {}
        self.approval_ttl = approval_ttl
        self.stats: dict[str, int] = {
            "evaluated": 0,
            "auto_approved": 0,
            "prompted": 0,
            "approved": 0,
            "denied": 0,
            "degraded": 0,
            "expired": 0,
        }

    # ------------------------------------------------------------------ setup

    @property
    def policy(self) -> Any | None:
        return self._policy

    def attach_policy(self, policy: Any | None) -> None:
        with self._lock:
            self._policy = policy
            self._policy_error = None

    @property
    def available(self) -> bool:
        return self._policy is not None

    # --------------------------------------------------------------- classify

    def _resolver(
        self, session_id: str, *, record: bool = True
    ) -> Callable[[str], tuple[Mapping[str, object] | str, bool] | None]:
        """Build a ref -> (item, stale) resolver from the live page.

        Staleness is the interesting part. A ref is only a label for an element,
        not a permanent name: orvima's `RefRegistry` tracks element identity
        across re-renders, so a ref that survives a rebuild points at the same
        element, while one that does not may be reused for something else. We
        remember the text each ref last resolved to and escalate when it changes,
        which catches the reuse case without needing to know how orvima detects
        it.

        `record=False` reads without updating the cache, which is what
        re-validation needs: a second look at the same ref must not make the
        first look look stale by overwriting the fingerprint.
        """
        def resolve(ref: str) -> tuple[Mapping[str, object] | str, bool] | None:
            if self._snapshot is None:
                return None
            snap = self._snapshot()
            if not snap:
                return None
            for item in snap.get("items", []) or []:
                if str(item.get("ref")) != str(ref):
                    continue
                fingerprint = f"{item.get('label', '')}|{item.get('text', '')}"
                key = (session_id, str(ref))
                with self._lock:
                    previous = self._seen_refs.get(key)
                    if record:
                        self._seen_refs[key] = fingerprint
                return item, previous is not None and previous != fingerprint
            return None

        return resolve

    def revalidate(
        self,
        session_id: str,
        tool: str,
        args: Mapping[str, Any] | None = None,
        approved_risk: str = "",
        plan: str = "",
    ) -> GateResult:
        """Check whether an already-granted approval still applies.

        A queued approval can sit unanswered for minutes, and the page moves in
        that time. Without this, a human reviews "Checkout" and the click lands
        on whatever now occupies that ref.

        Note this does *not* ask "does this still need a human?" - it does, it is
        still risky, that is why it was queued. It asks the narrower question:
        **has anything changed that this approval was not a decision about?**

        Two things invalidate it:

        * the element a ref points at has changed, so the human reviewed a
          different control than the one that will be clicked;
        * the action is now *more* dangerous than when it was approved, e.g. a
          click on "Save" was approved and the page has since become a checkout.

        A lower or equal risk passes. Being approved for a purchase is not
        revoked because the element's text is unchanged.
        """
        current = self.check(
            tool, args, session_id=session_id, revalidate=True, plan=plan
        )
        if "moved since" in current.reason:
            return GateResult(
                allowed=False,
                risk=current.risk,
                reason=(
                    "approval no longer applies: the element changed while it was "
                    "waiting for a human"
                ),
                confidence=current.confidence,
                degraded=current.degraded,
            )
        if approved_risk:
            order = _RISK_ORDER
            try:
                was = order.index(approved_risk)
                now = order.index(current.risk)
            except ValueError:
                was, now = 0, len(order) - 1
            if now > was:
                return GateResult(
                    allowed=False,
                    risk=current.risk,
                    reason=(
                        f"approval was for {approved_risk} but the action is now "
                        f"{current.risk}"
                    ),
                    confidence=current.confidence,
                    degraded=current.degraded,
                )
        return GateResult(
            allowed=True,
            risk=current.risk,
            reason=f"approval still valid for {current.risk} ({current.reason})",
            confidence=current.confidence,
            degraded=current.degraded,
        )

    def _page(self) -> str:
        if self._page_url is None:
            return ""
        try:
            return self._page_url() or ""
        except Exception:
            return ""

    def check(
        self,
        tool: str,
        args: Mapping[str, Any] | None = None,
        *,
        session_id: str = "",
        revalidate: bool = False,
        plan: str = "",
    ) -> GateResult:
        """Decide whether `tool(**args)` may run unattended.

        Never raises. Every failure path returns a non-allow result, because the
        one unacceptable outcome is a decision that permits something because
        the thing meant to judge it was broken.

        `session_id` scopes ref-staleness memory, since one gate is shared by
        every session and ref names are per-page. `revalidate=True` reads refs
        without recording them, so re-checking an action cannot make the
        original check look stale.

        `plan` describes what the agent is trying to do, for callers that have a
        plan (Errands). It can only raise the risk, never lower it.
        """
        if not self.enabled:
            return GateResult(allowed=True, risk="unknown", reason="gate disabled")

        policy = self._policy
        if policy is None:
            self.stats["degraded"] += 1
            return GateResult(
                allowed=False,
                risk="unknown",
                reason="sentinel not loaded; refusing to auto-approve",
                degraded=True,
            )

        self.stats["evaluated"] += 1
        try:
            decision = policy.evaluate(
                tool,
                dict(args or {}),
                resolver=self._resolver(session_id, record=not revalidate),
                page_url=self._page(),
                item_resolver=_item_resolver(),
                plan=plan,
            )
        except Exception as exc:
            # A gate that throws must not become a gate that permits.
            self.stats["degraded"] += 1
            return GateResult(
                allowed=False,
                risk="unknown",
                reason=f"sentinel raised {type(exc).__name__}: {exc}; refusing to auto-approve",
                degraded=True,
            )

        result = GateResult(
            allowed=not decision.needs_human,
            risk=decision.risk.value,
            reason=decision.reason,
            confidence=decision.confidence,
            degraded=decision.degraded,
            classifier_said=decision.classifier_said.value if decision.classifier_said else None,
        )
        if result.degraded:
            self.stats["degraded"] += 1
        if result.allowed:
            self.stats["auto_approved"] += 1
        else:
            self.stats["prompted"] += 1
        return result

    # -------------------------------------------------------------- approvals

    def request_approval(
        self,
        session_id: str,
        tool: str,
        args: Mapping[str, Any] | None,
        result: GateResult,
        snapshot: dict | None = None,
    ) -> str:
        """Queue a decision for a human and return its request id."""
        import uuid

        request = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            session_id=session_id,
            tool=tool,
            args=dict(args or {}),
            risk=result.risk,
            reason=result.reason,
            detail=_human_detail(tool, args, snapshot),
        )
        with self._lock:
            self._pending[request.id] = request
        return request.id

    def pending(self, session_id: str | None = None) -> list[ApprovalRequest]:
        with self._lock:
            items = list(self._pending.values())
        if session_id is None:
            return items
        return [r for r in items if r.session_id == session_id]

    def resolve(self, request_id: str, approved: bool) -> ApprovalRequest | None:
        """Record a human's answer. Returns the request, or None if unknown.

        An expired request is dropped rather than answered, and reported as
        expired. Letting it through would mean honouring a decision made about a
        page as it was several minutes ago.
        """
        with self._lock:
            request = self._pending.get(request_id)
            if request is not None and self._expired(request):
                del self._pending[request_id]
                self.stats["expired"] += 1
                self._lapsed.add(request_id)
                return None
            request = self._pending.pop(request_id, None)
            if request is not None:
                self.stats["approved" if approved else "denied"] += 1
        return request

    def lapsed(self, request_id: str) -> bool:
        """True if this request was dropped for expiring rather than answered.

        The waiting loop needs to tell "expired" apart from "the answer is on its
        way": a normal `resolve()` pops the request too, so absence alone cannot
        distinguish the two.
        """
        with self._lock:
            return request_id in self._lapsed

    def _mark_lapsed(self, request_id: str) -> None:
        with self._lock:
            self._lapsed.add(request_id)

    def _expired(self, request: ApprovalRequest) -> bool:
        if self.approval_ttl <= 0:
            return False
        return (time.time() - request.created) > self.approval_ttl

    def expire_stale(self) -> list[ApprovalRequest]:
        """Drop every request that has gone unanswered for too long."""
        dropped: list[ApprovalRequest] = []
        with self._lock:
            for request_id, request in list(self._pending.items()):
                if self._expired(request):
                    del self._pending[request_id]
                    self._lapsed.add(request_id)
                    dropped.append(request)
            if dropped:
                self.stats["expired"] += len(dropped)
        return dropped

    def forget_refs(self, session_id: str | None = None) -> None:
        """Drop cached ref text for one session, or all of them.

        Call after any known navigation or re-render - a page change makes every
        ref on the old page meaningless, so carrying them forward only invites
        false staleness.
        """
        with self._lock:
            if session_id is None:
                self._seen_refs.clear()
            else:
                for key in [k for k in self._seen_refs if k[0] == session_id]:
                    del self._seen_refs[key]

    def snapshot_stats(self) -> dict:
        with self._lock:
            return {**self.stats, "pending": len(self._pending)}


# ----------------------------------------------------------------- helpers ----

def _item_resolver() -> Callable[[Mapping[str, object]], str]:
    """Turn a resolved snapshot item into words the policy can match.

    Prefers Sentinel's resolver, which knows that orvima emits no `type` field
    and an empty `role` for inputs, and can still spot a password box from the
    `***` its own redaction left behind.

    The fallback is written out rather than imported, because it must work in
    exactly the case where Sentinel is missing - which is the one case where a
    ref has no text and a click would otherwise be unclassifiable.
    """
    try:
        from sentinel import make_item_resolver

        return make_item_resolver()
    except Exception:

        def describe(item: Mapping[str, object]) -> str:
            parts = [
                str(item[key])
                for key in ("role", "label", "text", "value")
                if item.get(key)
            ]
            tag = str(item.get("tag") or "").lower()
            if tag in ("input", "textarea", "select") and str(item.get("value") or "") == "***":
                # orvima redacts password values to "***", which marks the field
                # as a credential sink even though no `type` is exposed.
                parts.insert(0, "password field")
            elif not parts and tag:
                parts.append(tag)
            return " ".join(parts)

        return describe


def _human_detail(
    tool: str,
    args: Mapping[str, Any] | None,
    snapshot: dict | None,
) -> dict:
    """What a human needs to answer, so approving is not guesswork.

    Includes the page title and the element's own text, because the common
    failure of an approval dialog is asking someone to approve a click without
    telling them what they are clicking.
    """
    detail: dict[str, Any] = {"tool": tool}
    if snapshot:
        detail["page_title"] = snapshot.get("title")
        detail["page_url"] = snapshot.get("url")
    ref = (args or {}).get("ref")
    if ref and snapshot:
        for item in snapshot.get("items", []) or []:
            if str(item.get("ref")) == str(ref):
                detail["element"] = {
                    "ref": item.get("ref"),
                    "tag": item.get("tag"),
                    "role": item.get("role"),
                    "label": item.get("label"),
                    "text": item.get("text"),
                }
                break
    return detail


def make_gate(**kwargs: Any) -> SentinelGate:
    """Build a gate with a policy if Sentinel is importable, else without.

    Never raises. A missing or broken Sentinel produces a gate that declines to
    auto-approve, which is the correct behaviour for a safety component that
    cannot do its job.
    """
    mode = kwargs.pop("classifier_mode", "off")
    gate = SentinelGate(enabled=kwargs.pop("enabled", True), classifier_mode=mode, **kwargs)
    try:
        from sentinel import Classifier, ClassifierMode, HashingEmbedder, Policy

        policy = Policy(
            Classifier(HashingEmbedder()),
            classifier_mode=ClassifierMode(mode),
        )
        gate.attach_policy(policy)
    except Exception:
        # Left with no policy: every check returns degraded/refuse.
        pass
    return gate
