"""What the CLI says must match what it does.

Three separate ways `orvima` could mislead someone about whether it is driving
a real browser:

1. `ORVIMA_MODE` used to default to `demo`, so `orvima mcp` with no flags was a
   simulator. Silence here is what let an MCP config asking for Brave run
   against acme.dev for an entire debugging session. The default is now `real`,
   and these tests pin that in both directions: the default must be real, and
   `--mode demo` must still reach the simulator without pretending to be ready.
2. `--browser brave` is parsed, stored, and then never used in demo mode. A
   flag that is accepted and does nothing is worse than a missing one, because
   it reads as "that part is configured".
3. `doctor` printed "All checks passed — Orvima is ready" while running in demo
   mode, and named a browser it was not driving. Flipping the default is only
   half the fix: doctor must still refuse to be ready when no browser is behind
   it, and must not claim `orvima run` works without an LLM configured.

The rule these encode: a health check that passes while the product is in a
non-functional configuration is worse than no health check, because it is
trusted. A default that quietly disagrees with the documentation is the same
defect through a different door, which is why the default is asserted as a
value and not as a substring.

Run: pytest tests/test_cli_honesty.py -q
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from orvima import cli

SRC = str(Path(__file__).resolve().parents[1] / "src")


def orvima(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the CLI in a child process, with ORVIMA_* scrubbed.

    A subprocess because the mode is read from the environment and stashed into
    os.environ at import time; setting it in-process would leak into other
    tests through the module-level defaults.
    """
    child = {k: v for k, v in os.environ.items() if not k.startswith("ORVIMA_")}
    child["PYTHONPATH"] = SRC
    if env:
        child.update(env)
    return subprocess.run(
        [sys.executable, "-m", "orvima.cli", *args],
        capture_output=True, text=True, env=child, timeout=120,
    )


class TestTheModeIsNeverSilent:
    """A caller must be able to tell a simulator from a browser."""

    def test_doctor_names_the_mode_it_would_use(self):
        """It must say the mode it actually checked -- not a fixed word.

        This used to assert the literal "demo", which was a way of pinning the
        old default rather than the property being tested. Asserted against
        `resolve_mode` instead: doctor says whatever the resolver says.
        """
        active = cli.resolve_mode(None)
        out = orvima("doctor").stdout
        assert active in out.lower(), (
            f"doctor never says which mode it checked (expected {active!r}): {out}"
        )

    def test_doctor_never_calls_the_simulator_ready(self):
        """The exact sentence that was wrong.

        Asserted as a whole line, not as a substring match on "ready" alone: the
        mode belongs *in* the readiness sentence, so the sentence has to name it.
        In demo mode there is no browser behind orvima, so it must not be ready
        at all -- and in real mode the readiness sentence must say "real".
        """
        demo = orvima("doctor", env={"ORVIMA_MODE": "demo"})
        for line in demo.stdout.splitlines():
            if "Orvima is ready" in line:
                pytest.fail(f"doctor must not be ready with no browser behind it: {line!r}")

        real = orvima("doctor", env={"ORVIMA_MODE": "real"})
        ready = [ln for ln in real.stdout.splitlines() if "Orvima is ready" in ln]
        assert ready, real.stdout
        assert "real" in ready[0], ready[0]

    def test_a_failed_doctor_says_why_in_demo_mode(self):
        """A non-zero exit with no explanation is not usable.

        Skipping the demo-specific sentence and printing the generic
        "see above" leaves a first-time user with a red cross and no reason,
        which is how the original version of this file could pass while
        `doctor` stopped explaining itself.
        """
        out = orvima("doctor", env={"ORVIMA_MODE": "demo"}).stdout
        assert "demo" in out, f"doctor never mentions the mode it ran in: {out}"
        assert "no real browser is behind it" in out, (
            f"doctor failed in demo mode without saying no browser was involved: {out}"
        )

    def test_doctor_does_not_advertise_demo_mode(self):
        """Once demo is opt-in, doctor must not tell anyone to opt in.

        The MCP hint used to say "run 'orvima mcp --mode demo'", which walked
        every new user straight into the simulator this change removes.
        """
        for mode in ("real", "demo"):
            out = orvima("doctor", env={"ORVIMA_MODE": mode}).stdout
            assert "--mode demo" not in out, (
                f"doctor recommends --mode demo to a {mode}-mode user: {out}"
            )

    def test_doctor_does_not_promise_autonomous_runs_without_an_llm(self):
        """`orvima mcp` works with no LLM. `orvima run` does not.

        Asserted against the readiness block only. Checking the whole output
        would pass on the "LLM endpoint: not configured" line in the checks table
        even with the caveat removed from the sentence people actually read, and
        the mutation harness caught exactly that.
        """
        llm_set = bool(os.environ.get("ORVIMA_LLM_BASE") and os.environ.get("ORVIMA_LLM_KEY"))
        if llm_set:
            return
        out = orvima("doctor", env={"ORVIMA_MODE": "real"}).stdout
        assert "All checks passed" in out, out
        verdict = out[out.index("All checks passed") :]
        assert "orvima run" in verdict, (
            f"the readiness verdict never says which surfaces work: {verdict!r}"
        )
        assert "ORVIMA_LLM_BASE" in verdict, (
            f"the verdict promises readiness without naming what orvima run needs: {verdict!r}"
        )

    def test_real_mode_readiness_names_the_mode(self):
        """The fix is not just removing the claim — it is qualifying it."""
        result = orvima("--browser", "msedge", "doctor", env={"ORVIMA_MODE": "real"})
        ready = [ln for ln in result.stdout.splitlines() if "Orvima is ready" in ln]
        assert ready, result.stdout
        assert "real" in ready[0], ready[0]

    def test_doctor_exit_code_signals_that_no_browser_would_be_driven(self):
        """Fail closed. A non-zero exit is the only thing a script reads.

        Zero is only allowed when a real browser would actually be driven.
        """
        demo = orvima("doctor", env={"ORVIMA_MODE": "demo"})
        assert demo.returncode != 0, (
            "doctor exits 0 while orvima would drive a simulated site; a "
            "caller checking the exit code is told everything is fine"
        )

        real = orvima("doctor", env={"ORVIMA_MODE": "real"})
        if real.returncode == 0:
            # Zero must be earned: a browser was detected and a profile is usable.
            assert "would use" in real.stdout or "Browser" in real.stdout, real.stdout
            assert "✗ Browser" not in real.stdout, (
                f"doctor exited 0 with no usable browser: {real.stdout}"
            )
        assert "demo" not in real.stdout, real.stdout

    def test_the_browser_line_is_a_detection_not_a_claim(self):
        """In demo mode, naming a channel must not read as using it.

        This is the specific lie: `Browser: msedge` next to
        `Orvima is ready`, when nothing was driving msedge and the mode was demo.
        """
        result = orvima("doctor")
        # Match on "Browser:" anywhere in the line. The tick/cross glyphs are not
        # matched: the CLI reconfigures its streams to utf-8, but a captured
        # pipe on Windows can still hand them over as cp1252, and a test that
        # depends on a status glyph surviving the pipe is a test that will fail
        # for reasons that have nothing to do with the CLI.
        line = next(
            (ln.strip() for ln in result.stdout.splitlines() if "Browser:" in ln),
            None,
        )
        assert line is not None, result.stdout
        detail = line.split("Browser:", 1)[1]
        assert "mode" in result.stdout.lower(), (
            "the output never names the mode, so a browser line cannot be read "
            f"as a claim about what is being driven: {result.stdout}"
        )
        # A detection result is hedged. "msedge" on its own is a claim.
        hedged = any(w in detail.lower() for w in ("would use", "detected", "found", "not driving"))
        assert hedged, (
            f"the Browser line names a channel as if it were in use: {line!r}"
        )
        # And it must not be a tick while demo mode is active: a ✓ beside a
        # browser name is the shape of a readiness claim.
        if "NOT driving" in result.stdout:
            assert "✓" not in line and "✔" not in line, (
                f"demo mode reports the browser check as passing: {line!r}"
            )


class TestAnInertFlagSaysSo:
    """`--browser brave` in demo mode is accepted and ignored. It must not be
    silent about that."""

    def test_a_browser_flag_in_demo_mode_is_reported_as_unused(self):
        # `run` reaches the mode resolution without needing a browser, unlike
        # mcp (stdio) and serve (binds a port).
        result = orvima("--browser", "brave", "run", "noop", "--mode", "demo")
        combined = result.stdout + result.stderr
        assert "brave" in combined, (
            "a --browser flag was given and then silently dropped: "
            f"{combined}"
        )

    def test_the_warning_says_the_flag_had_no_effect(self):
        result = orvima("--browser", "brave", "run", "noop", "--mode", "demo")
        combined = (result.stdout + result.stderr).lower()
        assert any(
            phrase in combined
            for phrase in ("ignored", "not used", "no effect", "unused", "demo mode")
        ), (
            "the CLI mentions the browser but never says the flag did nothing: "
            f"{combined}"
        )


class TestRealModeIsWhatRealModeMeans:
    """Stated so the default can change without anyone noticing it did."""

    def test_real_mode_is_reachable_and_does_not_claim_offline(self):
        result = orvima("run", "noop", "--mode", "real")
        combined = result.stdout + result.stderr
        # Real mode needs an LLM or it fails; what matters is that it does not
        # succeed by pretending to be offline.
        assert "acme.dev" not in combined, (
            "real mode served the demo site, so --mode real is not honoured"
        )

    def test_the_mode_default_is_a_deliberate_documented_choice(self):
        """Stated as a fact about the code, so a silent flip fails here.

        The fallback lives in `resolve_mode`, in one place, so that `doctor` and
        the commands it checks cannot resolve it differently. Asserting on the
        module rather than on `main` is what keeps it there: as long as the
        literal is visible in one named function, a reader can see the default.
        """
        import inspect

        from orvima import cli

        source = inspect.getsource(cli.resolve_mode)
        assert "ORVIMA_MODE" in source, (
            "resolve_mode no longer reads ORVIMA_MODE, so the documented way to "
            f"switch modes has changed: {source}"
        )
        # The default is `real`, and it must be an explicit literal a reader can
        # see. Asserting the value rather than the spelling means a rename to
        # demo -- the silent flip this test exists to catch -- fails here.
        assert cli.resolve_mode(None) == "real", (
            f"the default mode is no longer real: {source}"
        )
        assert '"real"' in source or "'real'" in source, (
            f"the fallback is no longer an explicit literal a reader can see: {source}"
        )

    def test_doctor_agrees_with_the_commands_it_checks(self):
        """One resolver, so a health check cannot describe a different world."""
        import inspect

        from orvima import cli

        for name in ("cmd_doctor", "main"):
            source = inspect.getsource(getattr(cli, name))
            assert "ORVIMA_MODE" not in source, (
                f"{name} resolves ORVIMA_MODE itself instead of calling "
                "resolve_mode, so the two can disagree"
            )
            assert 'os.environ.get("ORVIMA_MODE"' not in source
