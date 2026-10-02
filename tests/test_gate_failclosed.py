"""The gate's own fail-closed promise, checked where it is actually kept.

``sentinel_gate.py`` makes a strong commitment: if the thing meant to judge an
action is unavailable, the action is *not* auto-approved, and the failure is
loud. ``make_gate`` honours it - no Sentinel package means a gate with no
policy, and a gate with no policy refuses everything.

That commitment is defeated one layer up, and no existing test looks there.

Two paths reach ``AgentLoop`` with ``gate=None``, and ``_authorise`` treats that
as "allow everything":

1. ``get_gate()`` returns ``None`` when ``from .sentinel_gate import
   make_gate`` raises. A syntax error, a partial install, a bad dependency -
   and the agent becomes fully autonomous, silently. This is a malfunction, not
   a decision, and it must not have the same effect as one.

2. ``ORVIMA_SENTINEL=off`` returns ``None`` deliberately. That one is a real
   operator choice and is left alone - but it is currently invisible, so an
   operator watching a live run has no way to know no gate is in force.

What made this findable: two comments in the tree assert that the ``_paused``
event at the top of the run loop is "the only gate" and that disabling Sentinel
"restores the original behaviour of pausing at every step". Neither is true.
``Session.__post_init__`` calls ``self._paused.set()``, so ``_paused.wait()``
returns immediately on every step. It is an operator pause control for a live
run, not an approval gate. Those comments describe a safety net that does not
exist, which is the most dangerous kind of wrong in a safety component: it
survives audit by reading true.

Run: pytest tests/test_gate_failclosed.py -q
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orvima import api  # noqa: E402
from orvima.agent import AgentLoop  # noqa: E402
from orvima.sentinel_gate import SentinelGate  # noqa: E402


@pytest.fixture
def clean_gate_cache():
    """Reset the module-level gate cache around each test."""
    original = api._gate
    api._gate = None
    try:
        yield
    finally:
        api._gate = original


class TestTheGateIsNeverSilentlyAbsentWhenGatingIsOn:
    """The fail-closed promise, kept at the layer that can break it."""

    def test_a_broken_gate_module_does_not_disable_gating(
        self, monkeypatch, clean_gate_cache
    ):
        """The dangerous path.

        A gate that cannot be imported is a malfunction. Treating it as
        "no gate" hands the agent a blank cheque and says nothing, which is
        exactly the failure mode `sentinel_gate.py` was written to prevent -
        arriving through the front door it was built to close.
        """
        broken = types.ModuleType("orvima.sentinel_gate")  # no make_gate at all
        monkeypatch.setitem(sys.modules, "orvima.sentinel_gate", broken)

        gate = api.get_gate()

        assert gate is not None, (
            "get_gate() returned None when the gate module failed to import, so "
            "AgentLoop would run every action unattended with no gate and no "
            "warning"
        )
        # Not isinstance(gate, SentinelGate): the whole point is that the stub
        # works when that module is the broken thing, so it cannot be an instance
        # of it. The contract is the interface, not the class.
        for method in ("check", "request_approval", "pending", "resolve",
                       "snapshot_stats", "revalidate"):
            assert callable(getattr(gate, method, None)), (
                f"the refusing gate is missing {method}(), so AgentLoop or the API "
                "would fail on a gate that is supposed to be the safe fallback"
            )

    def test_a_broken_gate_module_refuses_rather_than_permits(
        self, monkeypatch, clean_gate_cache
    ):
        """Not just present - it must actually block."""
        broken = types.ModuleType("orvima.sentinel_gate")
        monkeypatch.setitem(sys.modules, "orvima.sentinel_gate", broken)

        gate = api.get_gate()
        result = gate.check("browse_click", {"selector": "#pay"})

        assert result.allowed is False, (
            "a gate that could not load permitted an irreversible action"
        )
        assert result.degraded is True, (
            "the refusal was not marked degraded, so it cannot be told apart "
            "from a real judgement"
        )
        assert result.reason, "a refusal with no reason is not diagnosable"

    def test_the_real_module_is_restored_afterwards(
        self, monkeypatch, clean_gate_cache
    ):
        """The failure is not sticky.

        A gate that failed once should not permanently pin the session into
        refusing everything - that is the opposite bug, and the api.py comment
        about lazy construction exists precisely because somebody already hit it.
        """
        broken = types.ModuleType("orvima.sentinel_gate")
        monkeypatch.setitem(sys.modules, "orvima.sentinel_gate", broken)
        assert api.get_gate() is not None

        monkeypatch.undo()
        api._gate = None
        gate = api.get_gate()
        assert isinstance(gate, SentinelGate)


class TestAGateWithNoPolicyStillBlocks:
    """The path that already works, pinned so it cannot regress.

    This is the fail-closed behaviour *inside* the gate, and it is correct. It is
    worth a test because the integration tests all attach a working policy, so
    nothing was holding this specific line.
    """

    def test_no_policy_refuses(self):
        result = SentinelGate(policy=None).check("browse_click", {"selector": "#pay"})
        assert result.allowed is False
        assert result.degraded is True

    def test_a_policy_that_raises_refuses(self):
        class Exploding:
            def evaluate(self, *a, **k):
                raise RuntimeError("classifier down")

        result = SentinelGate(Exploding()).check("browse_click", {"selector": "#pay"})
        assert result.allowed is False, "a throwing classifier became permission"
        assert result.degraded is True

    def test_a_human_approval_cannot_be_laundered_by_a_recheck(self, monkeypatch, clean_gate_cache):
        """The re-check must not be a way for a refusal to become permission.

        After a human approves, the loop classifies once more against the page as
        it is *now*. With no policy there is nothing that can legitimately change
        its mind, so the re-check has to refuse too - otherwise "degraded" would
        mean "refuse once, then permit".
        """
        broken = types.ModuleType("orvima.sentinel_gate")
        monkeypatch.setitem(sys.modules, "orvima.sentinel_gate", broken)
        gate = api.get_gate()
        assert gate.revalidate("s1", "browse_click", {"selector": "#pay"}).allowed is False

    def test_a_disabled_gate_allows(self):
        """The one documented escape hatch, so the refusal above is not vacuous."""
        result = SentinelGate(policy=None, enabled=False).check(
            "browse_click", {"selector": "#pay"}
        )
        assert result.allowed is True
        assert "disabled" in result.reason


class TestDisablingTheGateIsVisible:
    """``ORVIMA_SENTINEL=off`` is a legitimate choice with real consequences.

    It is left functional. What it must not do is disappear: an operator who
    believes a gate is evaluating every action, while none is, has been given a
    false picture of what is protecting them.
    """

    def test_off_returns_no_gate(self, monkeypatch, clean_gate_cache):
        monkeypatch.setenv("ORVIMA_SENTINEL", "off")
        assert api.get_gate() is None

    def test_the_disabled_state_is_reported_not_silent(
        self, monkeypatch, clean_gate_cache
    ):
        """Something has to say so. Currently nothing does."""
        monkeypatch.setenv("ORVIMA_SENTINEL", "off")
        assert api.gate_status() == "off", (
            "nothing reports that gating is disabled, so a session running with "
            "no gate is indistinguishable from one that is being judged"
        )

    def test_on_with_a_working_gate_reports_on(self, monkeypatch, clean_gate_cache):
        monkeypatch.setenv("ORVIMA_SENTINEL", "on")
        api.get_gate()
        assert api.gate_status() in ("on", "degraded")

    def test_a_broken_module_reports_degraded_rather_than_off(
        self, monkeypatch, clean_gate_cache
    ):
        """Distinct from "off" on purpose.

        "A human turned this off" and "this broke" demand different responses,
        and collapsing them is how a malfunction becomes a policy.
        """
        monkeypatch.setenv("ORVIMA_SENTINEL", "on")
        broken = types.ModuleType("orvima.sentinel_gate")
        monkeypatch.setitem(sys.modules, "orvima.sentinel_gate", broken)
        api.get_gate()
        assert api.gate_status() == "degraded", (
            "a malfunction is being reported as though the gate were switched off"
        )


class TestAuthoriseFailOpenIsNotMistakenForSafety:
    """Pin what ``gate=None`` means, so nobody re-reads it as "the safe default".

    ``_authorise`` returns True when there is no gate. That is the right
    behaviour for ``bench.py`` and ``cli.py``, which construct a loop with no
    gate and expect an unattended run - changing it would break both. The defect
    was never the branch; it was the comment above it claiming the branch was
    protected by a per-step human pause that does not exist.
    """

    def test_no_gate_means_unattended_and_is_named_as_such(self):
        loop = AgentLoop.__new__(AgentLoop)
        loop.gate = None
        assert loop._authorise(1, "browse_click", {"selector": "#pay"}) is True

    def test_the_loop_pause_event_is_not_an_approval_gate(self):
        """``_paused`` starts signalled, so ``wait()`` returns immediately.

        This is the specific false claim the module and api docstrings repeat.
        If this test ever fails because someone made the pause real, the
        fail-open branch above becomes genuinely safe and the docstrings should
        be corrected to say so.
        """
        from orvima.agent import SessionStore

        sess = SessionStore().create(mode="demo")
        assert sess._paused.is_set(), (
            "the pause event now starts cleared, so the top-of-loop wait blocks "
            "- re-check the fail-closed reasoning in _authorise and api.get_gate"
        )
        # It returns at once, which is the whole point.
        sess._paused.wait(timeout=0.05)
