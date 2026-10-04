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


def _plain(markdown: str) -> str:
    """Read the prose without markdown emphasis, so claims match literally.

    Only `*` is removed, and underscores are deliberately left alone: they are
    part of the tokens these assertions check for. Stripping `_` turns
    `ORVIMA_SENTINEL=off` into `ORVIMASENTINEL=off`, and the test then fails
    against a README that says exactly the right thing - which is worse than no
    test, because the obvious response is to loosen the assertion until it goes
    green rather than to find the real cause.
    """
    return markdown.replace("*", "")


def _approvals_section() -> str:
    """Just the README's Approvals section.

    Assertions on the whole document pass on a stray second mention of
    `/api/gate/stats` even when the section that is supposed to carry it has
    been renamed away. Scoping to the section makes those mutations detectable.
    """
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(
        encoding="utf-8"
    )
    start = readme.find("## Approvals")
    assert start != -1, (
        "the README has no '## Approvals' section; the three run modes - CLI "
        "unattended, serve degraded, ORVIMA_SENTINEL=off - are documented nowhere "
        "else, and a user with a stuck session has no way to work out why"
    )
    end = readme.find("\n## ", start + 1)
    return _plain(readme[start:end] if end != -1 else readme[start:])


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


class TestWhatAFreshInstallActuallyDoes:
    """The default, pinned because the README now states it.

    Verified rather than assumed, and it is not what the docs used to imply.
    With `sentinel` not installed - and it is not a declared dependency, not even
    an extra - `make_gate` produces a gate with no policy, which refuses
    *everything*. Not just purchases: `browse_snapshot` too.

    That is fail-closed behaving correctly. It is also a fresh install that
    appears broken, with the reason written nowhere a user would look. Hence
    this test: the documented behaviour is a fact the suite holds, not prose
    that decays.
    """

    def _gate_without_sentinel(self, monkeypatch):
        """Simulate a fresh install: no sentinel package on the path."""
        import builtins

        real_import = builtins.__import__

        def blocked(name, *a, **k):
            if name == "sentinel" or name.startswith("sentinel."):
                raise ModuleNotFoundError("No module named 'sentinel'")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", blocked)
        monkeypatch.setitem(sys.modules, "sentinel", None)
        for mod in [m for m in sys.modules if m.startswith("sentinel.")]:
            monkeypatch.delitem(sys.modules, mod, raising=False)
        api._gate = None
        return api.get_gate()

    def test_a_fresh_install_refuses_rather_than_running_unattended(
        self, monkeypatch
    ):
        gate = self._gate_without_sentinel(monkeypatch)
        result = gate.check("browse_click", {"selector": "#pay"})
        assert result.allowed is False
        assert result.degraded is True

    def test_a_fresh_install_refuses_reads_too(self, monkeypatch):
        """The part that makes it look broken rather than cautious.

        A gate that only blocked purchases would be a safety feature. One that
        blocks `browse_snapshot` is an agent that cannot see, and the user is
        left with a session that refuses to do anything for no stated reason.
        """
        gate = self._gate_without_sentinel(monkeypatch)
        assert gate.check("browse_snapshot", {}).allowed is False, (
            "a fresh install now runs reads unattended - if this test fails, the "
            "README's account of the default is wrong again"
        )

    def test_the_reason_says_what_is_missing_and_how_to_change_it(self, monkeypatch):
        """A refusal the operator cannot act on is only half a safeguard."""
        gate = self._gate_without_sentinel(monkeypatch)
        reason = gate.check("browse_click", {"selector": "#pay"}).reason
        assert "sentinel" in reason.lower(), reason
        assert "ORVIMA_SENTINEL" in reason or "install" in reason.lower(), (
            f"the refusal does not say how to proceed: {reason!r}"
        )

    def test_switching_the_gate_off_is_documented_and_works(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_SENTINEL", "off")
        api._gate = None
        assert api.get_gate() is None, (
            "ORVIMA_SENTINEL=off is the documented escape hatch and must work"
        )


class TestWhatTheDocsClaim:
    """The README and SECURITY.md make specific claims about approvals.

    Both used to claim more than was true - "approve any action before it
    commits", "control of every action", "read-only mode by default" (no such
    mode exists), "file dialogs not supported" (`browse_set_files` shipped).
    Prose that overstates a safety property is worse than no prose, because it
    is what a reader checks instead of checking the code.

    So the claims are pinned here. Each test names the doc line it protects, and
    fails if the behaviour drifts away from what the docs say - in either
    direction, because a doc that has become too cautious is also wrong.
    """

    def test_readme_still_states_the_three_run_modes(self):
        """README '## Approvals' table: CLI unattended, serve degraded, off."""
        section = _approvals_section()
        assert "ORVIMA_SENTINEL=off" in section, (
            "the Approvals table no longer offers the deliberate off switch"
        )
        assert "/api/gate/stats" in section, (
            "the Approvals section no longer says how to check which mode you "
            "are in, so a stuck session is undebuggable from the docs"
        )
        assert "orvima run" in section and "orvima serve" in section, (
            "the Approvals table must distinguish the CLI (no gate at all) from "
            "the API (a gate, possibly degraded)"
        )

    def test_the_sentinel_dependency_claim_is_true_of_pyproject(self):
        """Check the packaging, not the prose that describes it.

        The README says `sentinel` is not a declared dependency. Asserting that
        against the README is circular - it only proves someone typed a
        sentence. If someone later adds a `sentinel` extra, the sentence becomes
        false and nothing here would notice, because the mutation does not touch
        the prose at all.
        """
        pyproject = (
            Path(__file__).resolve().parent.parent / "pyproject.toml"
        ).read_text(encoding="utf-8")
        assert "sentinel" not in pyproject, (
            "`sentinel` is now declared in pyproject, so the README's 'not a "
            "declared dependency' warning is out of date. Either drop the extra "
            "or fix the sentence - a stale install instruction is the same "
            "failure as a missing one."
        )

    def test_readme_does_not_claim_unconditional_approval(self):
        """The old claim: 'approve any action before it commits'."""
        readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(
            encoding="utf-8"
        )
        for overclaim in ("approve any action", "control of every action"):
            assert overclaim not in readme.lower(), (
                f"README still claims '{overclaim}'. Whether a gate is in force "
                "depends on how orvima was started and whether `sentinel` is "
                "installed; the CLI has no gate at all."
            )

    def test_security_md_does_not_claim_a_read_only_mode(self):
        """No read-only mode exists. `browse_eval` measures mutation, nothing more.

        This was the most dangerous of the false claims, because it sat in the
        threat-model table as a mitigation for prompt injection.
        """
        security = (Path(__file__).resolve().parent.parent / "SECURITY.md").read_text(
            encoding="utf-8"
        )
        assert "read-only mode by default" not in security.lower()

        # Guard the claim in code, not just in prose.
        #
        # The claim is that there is no read-only *mode*: no way to run orvima so
        # that it cannot act. An MCP `readOnlyHint` is not that. It is metadata
        # describing what a tool does, which lets a host warn a user before
        # invoking it; orvima does not enforce it and gains no restriction from
        # it. m8ven's review asked for all four hints on every tool, and OpenAI's
        # MCP directory rejects a tool missing any of them, so the distinction
        # matters in both directions: the hint must exist, and SECURITY.md must
        # not start implying it protects anything.
        #
        # What must NOT appear is an enforced restriction - a flag, a mode, or a
        # gate that actually blocks a write.
        package = Path(__file__).resolve().parent.parent / "src" / "orvima"
        enforced = []
        for f in package.glob("*.py"):
            text = f.read_text(encoding="utf-8")
            if "read_only" not in text:
                continue
            for line in text.splitlines():
                low = line.lower()
                if "read_only_hint" in low or "readonlyhint" in low:
                    continue  # the MCP annotation, which is descriptive only
                if any(
                    token in low
                    for token in ("read_only_mode", "--read-only", "--readonly", "read_only=True")
                ):
                    enforced.append(f"{f.name}: {line.strip()}")
        assert not enforced, (
            "an enforced read-only restriction now exists; SECURITY.md says "
            f"there is none, so one of the two is wrong: {enforced}"
        )

    def test_the_read_only_hint_is_metadata_and_not_a_restriction(self):
        """The other half of the claim above, asserted directly.

        `readOnlyHint` exists so a host can warn before a tool runs. If it ever
        started gating the call itself, orvima would have a read-only mode and
        SECURITY.md would be wrong - so this pins that the annotation is only
        ever handed to the MCP server, never consulted to allow or deny.
        """
        package = Path(__file__).resolve().parent.parent / "src" / "orvima"
        server = (package / "mcp_server.py").read_text(encoding="utf-8")
        assert "read_only_hint=b.read_only" in server, (
            "the hint should be passed through to the SDK as metadata"
        )
        # No call site anywhere decides on it.
        for f in package.glob("*.py"):
            for line in f.read_text(encoding="utf-8").splitlines():
                low = line.lower()
                if "read_only" not in low or "read_only_hint" in low or "readonlyhint" in low:
                    continue
                assert "if " not in low or "read_only" not in low.split("if ")[1][:12], (
                    f"{f.name} appears to branch on read_only: {line.strip()}"
                )

    def test_security_md_does_not_claim_file_dialogs_are_unsupported(self):
        """`browse_set_files` shipped; the native OS picker still is not driven."""
        security = (Path(__file__).resolve().parent.parent / "SECURITY.md").read_text(
            encoding="utf-8"
        )
        assert "File dialogs** - Not supported" not in security
        tools = (
            Path(__file__).resolve().parent.parent / "src" / "orvima" / "tools.py"
        ).read_text(encoding="utf-8")
        assert "browse_set_files" in tools, (
            "SECURITY.md no longer lists file dialogs as a limit, but the tool "
            "is gone - if support was dropped, put the limit back"
        )

    def test_the_documented_gate_statuses_are_the_ones_the_code_returns(self):
        """README promises on / degraded / off from /api/gate/stats."""
        from fastapi.testclient import TestClient

        from orvima.api import create_app

        client = TestClient(create_app())
        body = client.get("/api/gate/stats").json()
        assert body["gate"] in ("on", "degraded", "off"), body
        assert "gate" in body, "the status the README tells people to read is absent"


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
