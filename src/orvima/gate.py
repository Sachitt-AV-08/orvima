"""gate_* tools: sentinel risk classifier for browser actions.

Wraps sentinel's Policy + Classifier into Orvima's dict-in/dict-out contract.
Uses the HashingEmbedder (dependency-free, local) by default.
"""

from __future__ import annotations

from .sentinel.classify import Classifier
from .sentinel.embed import HashingEmbedder
from .sentinel.policy import ClassifierMode, Policy


def _make_policy(mode: str = "advisory") -> Policy:
    classifier = Classifier(embedder=HashingEmbedder())
    mode_map = {
        "off": ClassifierMode.OFF,
        "advisory": ClassifierMode.ADVISORY,
        "blocking": ClassifierMode.BLOCKING,
    }
    return Policy(classifier=classifier, classifier_mode=mode_map.get(mode, ClassifierMode.ADVISORY))


_DEFAULT_POLICY = _make_policy()


def gate_classify(tool: str, args: dict | None = None, page_url: str = "", mode: str = "advisory") -> dict:
    """Classify the risk of a browser action.

    Returns the risk tier (safe/low/outward/destructive), whether a human is
    needed, confidence, and reason. Uses sentinel's concept matching + classifier.
    """
    global _DEFAULT_POLICY
    if mode != "advisory":
        _DEFAULT_POLICY = _make_policy(mode)

    decision = _DEFAULT_POLICY.evaluate(tool, args or {}, page_url=page_url)
    return {
        "ok": True,
        "tool": tool,
        "risk": decision.risk.value,
        "needs_human": decision.needs_human,
        "confidence": round(decision.confidence, 4),
        "reason": decision.reason,
        "floor": decision.floor.value,
        "degraded": decision.degraded,
    }


def gate_describe_action(tool: str, args: dict | None = None) -> dict:
    """Describe what a tool call does as text (for risk matching)."""
    text = Policy.describe_action(tool, args or {})
    return {"ok": True, "tool": tool, "description": text}


def gate_risk_concepts(text: str) -> dict:
    """Check if text matches any risk concept from sentinel's concept list."""
    from .sentinel.policy import matches_concept, matches_weak
    concept = matches_concept(text)
    weak = matches_weak(text)
    return {
        "ok": True,
        "text": text,
        "matched_concept": concept,
        "matched_weak": weak,
        "is_risky": concept is not None or weak is not None,
    }


GATE_TOOLS = (
    gate_classify,
    gate_describe_action,
    gate_risk_concepts,
)
