"""orvima.trace - one trace ID, one event schema, one append-only audit log.

Design rules (each one is enforced below, not just documented):

* Strict. Unknown event types, unknown keys and missing keys are errors,
  the same way an unknown recipe key is. A typo must not become a log line
  that records nothing.
* Log before act. `emit` raises on anything invalid; a step whose
  `step.proposed` / `gate.decision` could not be written must not run.
* Escalate only. A `gate.decision` may never be lower than its strongest
  signal. A model (advisory) signal can raise friction, never remove it.
* Fail closed on effects. If request capture failed the effect class is
  "unknown", never "none".
* Local and redacted. Typed values are never logged, URLs lose their query
  and fragment, snapshots are logged as hashes.
* Tamper-evident, not tamper-proof. Events are hash-chained, so editing a
  line in the middle is detectable. Someone who rewrites the whole file can
  rebuild the chain; anchor the head hash somewhere (or sign it) if that
  matters to you.

Python 3.12, standard library only. Imports nothing from sentinel/errands.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA = "orvima.trace/1"
GENESIS = "0" * 64

LEVELS = {"allow": 0, "needs_human": 1, "refuse": 2}
SIGNAL_KINDS = {"deterministic", "advisory"}
EFFECT_CLASSES = {
    "none", "read", "navigation", "possible_mutation", "mutation", "unknown",
}
# Anything in this set means "a human should have seen this", ordered by
# how worried we are. "unknown" is deliberately in here.
EFFECTS_NEEDING_GATE = {"mutation", "possible_mutation", "unknown"}
ROUTES = {"errand", "freeform", "refused"}
REFUSALS = {
    "no_match", "ambiguous", "precondition_failed",
    "drift", "unsafe", "verification_failed",
}
SOURCES = {"recipe", "client", "planner"}
OUTCOMES = {"done", "stopped", "refused"}
APPROVALS = {"approved", "denied", "expired"}

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# GETs that are mutations in practice. Raises to "possible_mutation" only.
_SIDE_EFFECT_GET = re.compile(
    r"(^|/)(logout|signout|delete|remove|cancel|unsubscribe|confirm|checkout|pay)(/|$)",
    re.I,
)
_VARIABLE = re.compile(r"^(\{\w+\}|%\w+%)$")

# type -> (required data keys, optional data keys)
EVENTS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "run.start": (
        frozenset({"goal", "mode", "versions", "policy_hash"}),
        frozenset({"client", "recipe_registry_hash"}),
    ),
    "route.decision": (
        frozenset({"route"}),
        frozenset({"recipe_id", "recipe_version", "refusal", "candidates"}),
    ),
    "step.proposed": (
        frozenset({"tool", "args", "source"}),
        frozenset({"intent", "recipe_step", "plan_next"}),
    ),
    "gate.decision": (frozenset({"decision", "signals"}), frozenset({"mode"})),
    "approval.requested": (
        frozenset({"risk", "reason", "page_url", "ttl_s"}),
        frozenset({"element_text"}),
    ),
    "approval.resolved": (
        frozenset({"outcome", "latency_ms"}),
        frozenset({"revalidated_decision", "approver"}),
    ),
    "effect.held": (frozenset({"method", "url"}), frozenset({"released"})),
    "effect.observed": (
        frozenset({"effect_class", "capture_ok", "requests", "filtered"}),
        frozenset({"nav_before", "nav_after", "dropped"}),
    ),
    "step.result": (
        frozenset({"ok", "verified"}),
        frozenset({
            "expect_hit", "reject_hit", "state_before", "state_after",
            "error", "duration_ms",
        }),
    ),
    "llm.usage": (
        frozenset({"calls", "input_tokens", "output_tokens"}),
        frozenset({"model", "purpose"}),
    ),
    "recipe.proposed": (
        frozenset({"recipe_id", "source_trace", "recipe_sha256"}),
        frozenset({"state_changing_steps_gated"}),
    ),
    "recipe.reviewed": (
        frozenset({"recipe_sha256", "decision"}),
        frozenset({"reviewer"}),
    ),
    "run.end": (frozenset({"outcome"}), frozenset({"refusal", "steps", "duration_ms"})),
}
ENVELOPE = frozenset(
    {"schema", "trace_id", "seq", "ts", "type", "span", "prev", "hash", "data"}
)


# --------------------------------------------------------------------------
# helpers


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(prev: str, envelope_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256((prev + _canonical(envelope_without_hash)).encode()).hexdigest()


def new_trace_id() -> str:
    """Sortable by start time, unguessable suffix: 20261006T101500Z-9f3a1c2e."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sanitize_url(url: str) -> str:
    """scheme://host/path only. Query strings and fragments carry tokens."""
    parts = urlsplit(url)
    if not parts.scheme:
        return url.split("?")[0].split("#")[0]
    out = f"{parts.scheme}://{parts.netloc}{parts.path}"
    return out + "?..." if parts.query else out


_TYPED_VALUE_KEYS = {"text", "value", "files", "path", "paths"}
_TYPED_VALUE_TOOLS = {"browse_fill", "browse_type", "browse_select", "browse_set_files"}


def redact_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Never log what the agent typed. Recipe variables ({email}) are kept
    by name because the name is useful and the value is not in the string.
    browse_eval is logged in full: it is the escape hatch, so auditability
    outweighs the chance someone pasted a secret into an expression."""
    out: dict[str, Any] = {}
    for key, val in args.items():
        if tool in _TYPED_VALUE_TOOLS and key in _TYPED_VALUE_KEYS:
            if isinstance(val, str) and _VARIABLE.match(val):
                out[key] = val
            else:
                n = len(val) if hasattr(val, "__len__") else 0
                out[key] = {"redacted": True, "len": n}
        elif key == "url" and isinstance(val, str):
            out[key] = sanitize_url(val)
        else:
            out[key] = val
    return out


# --------------------------------------------------------------------------
# validation


def validate_event(ev: dict[str, Any]) -> None:
    """Raise ValueError on anything that is not a well-formed event."""
    if set(ev) != ENVELOPE:
        raise ValueError(f"envelope keys differ: {sorted(set(ev) ^ ENVELOPE)}")
    if ev["schema"] != SCHEMA:
        raise ValueError(f"unknown schema {ev['schema']!r}")
    etype = ev["type"]
    if etype not in EVENTS:
        raise ValueError(f"unknown event type {etype!r}")
    required, optional = EVENTS[etype]
    data = ev["data"]
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    missing = required - set(data)
    unknown = set(data) - required - optional
    if missing:
        raise ValueError(f"{etype}: missing {sorted(missing)}")
    if unknown:
        raise ValueError(f"{etype}: unknown keys {sorted(unknown)}")
    _validate_semantics(etype, data)


def _validate_semantics(etype: str, d: dict[str, Any]) -> None:
    if etype == "run.start" and d["mode"] not in ROUTES - {"refused"}:
        raise ValueError(f"run.start: bad mode {d['mode']!r}")
    if etype == "route.decision":
        if d["route"] not in ROUTES:
            raise ValueError(f"route.decision: bad route {d['route']!r}")
        if d["route"] == "refused" and d.get("refusal") not in REFUSALS:
            raise ValueError("route.decision: refused needs a RefusalReason")
    elif etype == "step.proposed" and d["source"] not in SOURCES:
        raise ValueError(f"step.proposed: bad source {d['source']!r}")
    elif etype == "gate.decision":
        if d["decision"] not in LEVELS:
            raise ValueError(f"gate.decision: bad decision {d['decision']!r}")
        top = 0
        for s in d["signals"]:
            if set(s) != {"signal", "kind", "level", "why"}:
                raise ValueError(f"gate.decision: bad signal keys {sorted(s)}")
            if s["kind"] not in SIGNAL_KINDS or s["level"] not in LEVELS:
                raise ValueError(f"gate.decision: bad signal {s}")
            top = max(top, LEVELS[s["level"]])
        # The escalate-only invariant: nothing may lower the strongest signal.
        if LEVELS[d["decision"]] < top:
            raise ValueError("gate.decision is lower than its strongest signal")
    elif etype == "approval.resolved" and d["outcome"] not in APPROVALS:
        raise ValueError(f"approval.resolved: bad outcome {d['outcome']!r}")
    elif etype == "effect.observed":
        if d["effect_class"] not in EFFECT_CLASSES:
            raise ValueError(f"effect.observed: bad class {d['effect_class']!r}")
        if not d["capture_ok"] and d["effect_class"] != "unknown":
            raise ValueError("effect.observed: failed capture must be 'unknown'")
    elif etype == "run.end":
        if d["outcome"] not in OUTCOMES:
            raise ValueError(f"run.end: bad outcome {d['outcome']!r}")
        if d["outcome"] == "refused" and d.get("refusal") not in REFUSALS:
            raise ValueError("run.end: refused needs a RefusalReason")


# --------------------------------------------------------------------------
# effect detection (pure function: unit-testable with no browser)


def _host_matches(url: str, hosts: Iterable[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def classify_effect(
    requests: Iterable[dict[str, Any]],
    nav_before: str | None,
    nav_after: str | None,
    *,
    capture_ok: bool = True,
    beacon_hosts: Iterable[str] = (),
    cap: int = 50,
) -> dict[str, Any]:
    """Turn the requests a click caused into an `effect.observed` payload.

    Request dicts: {"method", "url", "resource_type"}. Anything dropped from
    consideration (sendBeacon pings, allow-listed analytics hosts) is listed
    in `filtered` with a reason, never silently discarded, so a too-greedy
    allow-list is visible in the audit.

    Limits worth knowing: this sees HTTP effects only (not a WebSocket
    message or a local-storage write), and a GET that mutates server state
    is caught only if its path looks like it does ("possible_mutation").
    """
    beacon_hosts = tuple(h.lower() for h in beacon_hosts)
    counted: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for r in requests:
        row = {
            "method": str(r.get("method", "GET")).upper(),
            "url": sanitize_url(str(r.get("url", ""))),
            "resource_type": r.get("resource_type", ""),
        }
        if row["resource_type"] == "ping":
            filtered.append({**row, "why": "beacon"})
        elif beacon_hosts and _host_matches(str(r.get("url", "")), beacon_hosts):
            filtered.append({**row, "why": "allowlisted_host"})
        else:
            counted.append(row)

    before = sanitize_url(nav_before).split("?")[0] if nav_before else None
    after = sanitize_url(nav_after).split("?")[0] if nav_after else None

    if not capture_ok:
        cls = "unknown"
    elif any(r["method"] in MUTATING_METHODS for r in counted):
        cls = "mutation"
    elif any(
        r["method"] == "GET" and _SIDE_EFFECT_GET.search(urlsplit(r["url"]).path)
        for r in counted
    ):
        cls = "possible_mutation"
    elif before != after:
        cls = "navigation"
    elif counted:
        cls = "read"
    else:
        cls = "none"

    out: dict[str, Any] = {
        "effect_class": cls,
        "capture_ok": capture_ok,
        "requests": counted[:cap],
        "filtered": filtered[:cap],
        "nav_before": before,
        "nav_after": after,
    }
    dropped = max(0, len(counted) - cap) + max(0, len(filtered) - cap)
    if dropped:
        out["dropped"] = dropped
    return out


# --------------------------------------------------------------------------
# writer


class TraceWriter:
    """Append-only, hash-chained JSONL. One instance == one trace ID."""

    def __init__(
        self,
        directory: str | Path,
        trace_id: str | None = None,
        *,
        fsync: bool = False,
    ) -> None:
        self.trace_id = trace_id or new_trace_id()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"{self.trace_id}.jsonl"
        if self.path.exists():
            raise FileExistsError(f"trace {self.trace_id} already exists")
        self._fsync = fsync
        self._seq = 0
        self._prev = GENESIS
        self._lock = threading.Lock()

    def emit(self, type: str, data: dict[str, Any], span: str | None = None) -> dict[str, Any]:
        """Validate, chain and append. Raises rather than dropping: callers
        must treat a failed emit as 'do not run the step'."""
        with self._lock:
            body = {
                "schema": SCHEMA,
                "trace_id": self.trace_id,
                "seq": self._seq,
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "type": type,
                "span": span,
                "prev": self._prev,
                "data": data,
            }
            event = {**body, "hash": _hash(self._prev, body)}
            validate_event(event)
            line = _canonical(event) + "\n"
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                if self._fsync:
                    import os

                    os.fsync(fh.fileno())
            self._seq += 1
            self._prev = event["hash"]
            return event


# --------------------------------------------------------------------------
# reading, chain verification, audit


def read_trace(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def verify_chain(events: list[dict[str, Any]]) -> list[str]:
    """Problems with the chain itself: reorder, gap, edit, bad schema."""
    problems: list[str] = []
    prev = GENESIS
    trace_id = events[0]["trace_id"] if events else None
    for i, ev in enumerate(events):
        try:
            validate_event(ev)
        except (ValueError, KeyError) as exc:
            problems.append(f"seq {i}: invalid event: {exc}")
            continue
        if ev["trace_id"] != trace_id:
            problems.append(f"seq {i}: trace_id changed")
        if ev["seq"] != i:
            problems.append(f"seq {i}: sequence gap or reorder (found {ev['seq']})")
        if ev["prev"] != prev:
            problems.append(f"seq {i}: prev hash does not match previous event")
        body = {k: v for k, v in ev.items() if k != "hash"}
        if ev["hash"] != _hash(ev["prev"], body):
            problems.append(f"seq {i}: hash mismatch (event was edited)")
        prev = ev["hash"]
    return problems


def audit(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the kill-criteria numbers from a trace.

    `ungated_effects` is a *proxy* for 'unsafe actions allowed': spans where
    an effect needing a gate was observed but no human approved it. The
    ground truth is the site's own record (did the card get charged?); this
    tells you where to look and is cheap to compute on every run.
    """
    gate: dict[str, dict[str, Any]] = {}
    approved: set[str] = set()
    effects: dict[str, str] = {}
    violations: list[str] = []
    spans_with_result: list[str] = []
    prompts = denied = expired = llm_calls = in_tok = out_tok = 0

    for ev in events:
        t, span, d = ev["type"], ev["span"], ev["data"]
        if t == "gate.decision" and span:
            gate[span] = d
        elif t == "approval.requested":
            prompts += 1
        elif t == "approval.resolved":
            if d["outcome"] == "approved" and span:
                approved.add(span)
            elif d["outcome"] == "denied":
                denied += 1
            else:
                expired += 1
        elif t == "effect.observed" and span:
            effects[span] = d["effect_class"]
        elif t == "step.result" and span:
            spans_with_result.append(span)
            g = gate.get(span)
            if g is None:
                violations.append(f"{span}: step ran with no prior gate.decision")
            elif g["decision"] != "allow" and span not in approved:
                violations.append(
                    f"{span}: gate said {g['decision']} but no approval preceded the result"
                )
        elif t == "llm.usage":
            llm_calls += d["calls"]
            in_tok += d["input_tokens"]
            out_tok += d["output_tokens"]

    ungated = sorted(
        s
        for s, cls in effects.items()
        if cls in EFFECTS_NEEDING_GATE
        and s not in approved
        and gate.get(s, {}).get("decision", "allow") == "allow"
    )
    steps = len(spans_with_result)
    return {
        "chain_problems": verify_chain(events),
        "ordering_violations": violations,
        "steps": steps,
        "prompts": prompts,
        "denied": denied,
        "expired": expired,
        "interruptions_per_step": (prompts / steps) if steps else 0.0,
        "ungated_effects": ungated,
        "llm_calls": llm_calls,
        "llm_input_tokens": in_tok,
        "llm_output_tokens": out_tok,
    }
