"""Benchmark gate.

The point of ``orvima bench`` is to make "we made it more powerful" a number
someone can check. These tests turn that number into something CI enforces,
without pretending the current score is good.

What is asserted, and why
-------------------------
* **Safety never regresses.** Every irreversible task must pass. A double-submit
  is a qualitatively different failure from a missed task, so it is gated at
  zero tolerance and the rest of the suite is not.
* **The pass rate never regresses.** Asserted against the recorded baseline. The
  baseline is 5/10 and every failure is a recoverable failure the loop does not
  yet recover from - that is the defect Phase 1 exists to fix, so the number is
  expected to move upward from here. When it does, raise BASELINE in this file
  *and* in the plan, and say why.
* **The harness is honest.** A benchmark that cannot fail is worse than none, so
  a deliberately-broken task must be reported as failing. Without this, a green
  run only proves the fixtures agree with the oracles.
"""

from __future__ import annotations

import pytest

from orvima.bench import TASKS, Task, run_all, run_task
from orvima.bench_site import BenchError, BenchSite, Counter

#: Recorded 2026-10-01, immediately before the Phase 1 recovery work.
#: See ~\.claude\plans\orvima-power.md.
BASELINE_PASSED = 5
BASELINE_TOTAL = 10


def test_never_double_submits() -> None:
    """Safety, at zero tolerance: no task may ever submit more than once.

    This is deliberately *not* the same as the irreversible tasks passing. Those
    fail today because the loop gives up before reaching the submit
    (submits == 0) - a capability gap, not a dangerous one. The property that
    must hold no matter what is the ceiling: at most one irreversible action per
    task, ever. A recovery loop that replayed an action would break this, and it
    is the reason the recovery work in Phase 1 is allowed to fail loudly.
    """
    report = run_all()
    doubles = [r for r in report["results"] if r["submits"] > 1]
    assert not doubles, "a task submitted more than once: " + ", ".join(
        f"{r['name']} submitted {r['submits']}x" for r in doubles
    )


def test_pass_rate_does_not_regress() -> None:
    report = run_all()
    assert (report["passed"], report["total"]) >= (BASELINE_PASSED, BASELINE_TOTAL), (
        f"pass rate regressed: {report['passed']}/{report['total']} "
        f"was {BASELINE_PASSED}/{BASELINE_TOTAL}\n"
        + "\n".join(f"  FAIL {r['name']}: {r['error']}" for r in report["results"] if not r["passed"])
    )


def test_every_task_is_wired_up() -> None:
    """A task that never runs would silently inflate the rate."""
    report = run_all()
    assert report["total"] == len(TASKS) == BASELINE_TOTAL
    assert all(r["steps"] > 0 for r in report["results"]), "a task took no actions at all"


def test_bench_can_actually_fail() -> None:
    """A control: a task whose plan cannot succeed must be reported as failed.

    If this ever passes, the harness is rubber-stamping results and the number
    it produces means nothing.
    """
    impossible = Task(
        name="impossible",
        shape="control",
        goal="click something that does not exist",
        start="login",
        plan=[("browse_click", {"selector": "#definitely-not-here"})],
        expect=lambda c, s: True,  # the oracle would pass if the run ever finished
    )
    result = run_task(impossible)
    assert not result["passed"], "bench reported an impossible task as a pass"
    assert "not visible" in result["error"] or result["error"], "failure reason was swallowed"


def test_a_failing_run_never_counts_as_a_pass_even_if_the_oracle_holds() -> None:
    """Regression guard for the false pass found while building the bench.

    An early version scored a task as passing when the run errored but a side
    effect had already satisfied the oracle, which inflated the baseline from
    30% to 50%. A task that dies at step 1 must never be green.
    """
    dies_early_but_satisfies_oracle = Task(
        name="false-pass-guard",
        shape="control",
        goal="do one thing that works, then one that fails",
        start="login",
        plan=[
            ("browse_type", {"selector": "#username", "text": "written"}),
            ("browse_click", {"selector": "#nope"}),
        ],
        # The side effect from step 1 really did happen.
        expect=lambda c, s: s.values.get("#username") == "written",
    )
    result = run_task(dies_early_but_satisfies_oracle)
    assert not result["passed"], "a run that errored was scored as a pass"
    assert result["steps"] == 2


def test_plain_tasks_pass() -> None:
    """The control group. If these break, a change regressed the basics."""
    report = run_all([t for t in TASKS if t.shape == "plain"])
    failures = [r for r in report["results"] if not r["passed"]]
    assert not failures, "plain tasks regressed: " + ", ".join(
        f"{r['name']}: {r['error']}" for r in failures
    )


@pytest.mark.parametrize("shape", ["stale-ref", "transient", "late-element", "irreversible"])
def test_shape_is_represented(shape: str) -> None:
    """Each advertised shape needs at least one task, or the report lies."""
    assert any(t.shape == shape for t in TASKS), f"no task exercises the {shape!r} shape"


# --------------------------------------------------------- fixture contracts --


def test_site_double_actually_misbehaves() -> None:
    """The hostile site has to actually be hostile, or the bench tests nothing."""
    site = BenchSite(start="list")
    with pytest.raises(BenchError, match="not visible"):
        site.click("#row-1")
    assert "#row-1" not in site.visible and "#row-1-v2" in site.visible

    flaky = BenchSite(start="login")
    with pytest.raises(BenchError, match="not ready"):
        flaky.click("#flaky")
    flaky.click("#flaky")  # second attempt works
    assert flaky.page == "ready"

    counter = Counter()
    doubler = BenchSite(start="login", counter=counter)
    doubler.click("#submit")
    doubler.click("#submit")
    assert counter.submits == 2, "the double-submit guard in the fixture is not counting"
