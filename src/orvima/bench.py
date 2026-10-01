"""orvima bench - a falsifiable pass-rate measurement for the agent loop.

Why this exists
---------------
Every claim that orvima is "more powerful" after a change needs a number to move.
Without one, improvements are asserted rather than shown, and regressions hide.
This module measures **task pass rate** on a hostile site fixture (see site.py).

What it measures, and what it deliberately does not
---------------------------------------------------
It measures the *loop*: does a failure get recovered from, or does it end the run?
The planner is a scripted list of actions, not an LLM, so the score reflects
recovery logic and not model variance - which is what makes the number stable
across runs and comparable between revisions.

It does **not** measure real-world capability. The site is a simulator, the
planner is scripted, and no real browser is launched. A high score here means
"the loop's control flow is sound", not "orvima can drive LinkedIn". Reporting it
as anything larger would be a lie. See ``orvima bench --help`` for the caveat
this prints.

Task shapes
-----------
Each task targets one behaviour, so a pass-rate drop names its own cause:

    stale-ref        click a ref that the site has already replaced
    transient        an action that fails once, then works
    late-element     act on something that only exists after other interaction
    irreversible     press a submit exactly once, even under failure pressure
    plain            a straightforward multi-step flow with no obstacles
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from orvima.agent import AgentLoop, Session

from .bench_site import BenchSite, Counter

# Tags a task as safety-critical: these must pass, and a double-submit fails hard.
IRREVERSIBLE = "irreversible"


@dataclass
class Task:
    """One benchmark task: a goal, a scripted plan, and a pass condition."""

    name: str
    shape: str
    goal: str
    start: str
    #: Actions the scripted planner will attempt, in order. Each is (tool, args).
    plan: list[tuple[str, dict]]
    #: Checks the run's side effects. Receives the Counter and the site.
    expect: Callable[[Counter, BenchSite], bool]
    tags: list[str] = field(default_factory=list)

    @property
    def irreversible(self) -> bool:
        return IRREVERSIBLE in self.tags or "submit" in self.tags

    @property
    def safety_only(self) -> bool:
        """True when only the no-double-action property is being asserted.

        A refused retry ends the run in error, and the refused action really did
        land. Scoring such a task as simply "failed" would conflate "the loop
        kept the user safe" with "the loop did not finish", and would make a
        correct refusal look like a defect. These tasks are graded on the ledger
        alone - what the site actually saw.
        """
        return "safety_only" in self.tags


# --------------------------------------------------------------- conditions --


def _submitted_once(c: Counter) -> bool:
    return c.submits == 1


# ------------------------------------------------------------------- tasks --

# Plain flows: no obstacles. These should pass before and after any change, and
# are the control group - if they start failing, the change broke the basics.
TASKS: list[Task] = [
    Task(
        name="plain-login",
        shape="plain",
        goal="log in to the bench site",
        start="login",
        plan=[
            ("browse_type", {"selector": "#username", "text": "orvima"}),
            ("browse_type", {"selector": "#password", "text": "hunter2"}),
            ("browse_click", {"selector": "#submit"}),
        ],
        expect=lambda c, s: _submitted_once(c) and s.values.get("#username") == "orvima",
        tags=["submit"],
    ),
    Task(
        name="plain-navigate-extract",
        shape="plain",
        goal="open the list and read it",
        start="login",
        plan=[
            ("browse_navigate", {"url": "https://bench.test/list"}),
            ("browse_snapshot", {}),
            ("browse_extract", {"selector": "#title"}),
        ],
        expect=lambda c, s: c.navs == ["https://bench.test/list"] and s.page == "list",
    ),
    Task(
        name="plain-multi-step-form",
        shape="plain",
        goal="fill three fields and submit",
        start="login",
        plan=[
            ("browse_type", {"selector": "#username", "text": "a"}),
            ("browse_type", {"selector": "#password", "text": "b"}),
            ("browse_snapshot", {}),
            ("browse_click", {"selector": "#submit"}),
        ],
        expect=lambda c, s: _submitted_once(c) and len(c.types.get("#username", [])) == 1,
        tags=["submit"],
    ),
    # The stale-ref shape. #row-1 stops existing the moment it is clicked, so a
    # planner that trusted its snapshot must re-snapshot and re-target.
    Task(
        name="stale-ref-row",
        shape="stale-ref",
        goal="open the first row",
        start="list",
        plan=[
            ("browse_click", {"selector": "#row-1"}),
            ("browse_snapshot", {}),
        ],
        expect=lambda c, s: s.rerendered and "#row-1-v2" in s.visible,
    ),
    # Transient: the first click fails, the second works. Needs a retry that is
    # bounded and does not confuse "failed" with "done".
    Task(
        name="transient-flaky-click",
        shape="transient",
        goal="press the flaky button until it works",
        start="login",
        plan=[
            ("browse_click", {"selector": "#flaky"}),
            ("browse_click", {"selector": "#flaky"}),
        ],
        expect=lambda c, s: c.clicks.get("#flaky") == 2 and s.page == "ready",
    ),
    # Late element: the panel only appears after two interactions.
    Task(
        name="late-element-panel",
        shape="late-element",
        goal="open the panel that appears late",
        start="login",
        plan=[
            ("browse_click", {"selector": "#open-panel"}),
            ("browse_click", {"selector": "#open-panel"}),
            ("browse_wait_for", {"selector": "#panel"}),
        ],
        expect=lambda c, s: "#panel" in s.visible,
    ),
    # Irreversible under recovery pressure. A failing action sits *before* the
    # submit, so any recovery that replays from the wrong place, or blindly
    # re-runs the last action, produces a second submit. The condition is
    # submits == 1 - not merely "the run finished" - so a loop that stumbles into
    # double-submitting scores as a failure, not a success with a warning.
    Task(
        name="irreversible-submit-once",
        shape="irreversible",
        goal="submit the form exactly once, after an unrelated failure",
        start="login",
        plan=[
            ("browse_type", {"selector": "#username", "text": "once"}),
            ("browse_click", {"selector": "#flaky"}),
            ("browse_click", {"selector": "#flaky"}),
            ("browse_click", {"selector": "#submit"}),
        ],
        expect=lambda c, s: _submitted_once(c) and s.page == "dashboard",
        tags=["submit", IRREVERSIBLE],
    ),
    # Irreversible where the *first* attempt fails outright.
    Task(
        name="irreversible-submit-after-failure",
        shape="irreversible",
        goal="submit once despite an earlier unrelated failure",
        start="login",
        plan=[
            ("browse_click", {"selector": "#flaky"}),
            ("browse_click", {"selector": "#flaky"}),
            ("browse_type", {"selector": "#username", "text": "bob"}),
            ("browse_click", {"selector": "#submit"}),
        ],
        expect=lambda c, s: _submitted_once(c) and s.values.get("#username") == "bob",
        tags=["submit", IRREVERSIBLE],
    ),
    # The one that must never regress, and the reason this whole phase exists.
    #
    # #submit-timeout takes effect and *then* raises "Timeout 10000ms exceeded" -
    # an error the classifier would call retryable on its own. The run is
    # therefore under real pressure to click again, and doing so charges twice.
    # The loop has to refuse on the strength of the *action* alone.
    #
    # This also stays failed-on-purpose once recovery works: the submit really
    # did land, the run really does report failure, and the task is scored on
    # submits == 1 rather than on the run finishing. A double submit is what is
    # being tested for, not task completion.
    Task(
        name="irreversible-submit-that-looks-timeout",
        shape="irreversible",
        goal="pay once even though the confirmation timed out",
        start="login",
        plan=[
            ("browse_type", {"selector": "#username", "text": "victim"}),
            ("browse_click", {"selector": "#submit-timeout"}),
            ("browse_click", {"selector": "#submit-timeout"}),
            ("browse_click", {"selector": "#submit-timeout"}),
        ],
        expect=lambda c, s: c.submits == 1,
        tags=["submit", IRREVERSIBLE, "safety_only"],
    ),
    Task(
        name="element-not-found-recovers",
        shape="stale-ref",
        goal="snapshot after a bad ref and carry on",
        start="login",
        plan=[
            ("browse_click", {"selector": "#does-not-exist"}),
            ("browse_snapshot", {}),
        ],
        expect=lambda c, s: s.page == "login",
    ),
    Task(
        name="tab-round-trip",
        shape="plain",
        goal="open a tab, list tabs, come back",
        start="login",
        plan=[
            ("browse_open_tab", {"url": "https://bench.test/list"}),
            ("browse_list_tabs", {}),
            ("browse_switch_tab", {"index": 0}),
        ],
        expect=lambda c, s: s.page == "login",
    ),
]


# ------------------------------------------------------------------ planner --


class ScriptedPlanner:
    """Replays a task's plan, and reacts to failures the way a planner would.

    This stands in for the LLM. It does not know the site's rules and cannot see
    that an element is missing before trying it, so it never skips ahead
    speculatively - a planner that cheated would hide loop defects.

    What it does do is *react*: when the loop reports a failure and hands back a
    fresh snapshot, it moves to the next action in its plan. That is the whole
    recovery contract from the planner's side, and without it the benchmark can
    only ever measure the loop's ability to fail, never to recover. An earlier
    version aborted on any failure, which silently pinned the score at the
    no-recovery baseline no matter how good the loop became.
    """

    def __init__(self, task: Task) -> None:
        self.task = task
        self.cursor = 0

    def toolset(self) -> str:
        return ", ".join(sorted({t for t, _ in self.task.plan}))

    def decide(self, goal: str, history: list[dict]) -> dict:
        if self.cursor >= len(self.task.plan):
            return {"done": True, "summary": f"completed {self.task.name}"}

        tool, args = self.task.plan[self.cursor]
        self.cursor += 1
        return {"tool": tool, "args": args}


# ------------------------------------------------------------------ runner --


def run_task(task: Task, max_steps: int = 20) -> dict:
    """Run one task in a fresh site + session. Never raises."""
    site = BenchSite(start=task.start)
    session = Session(id=f"bench-{task.name}", mode="bench", browser=site)
    loop = AgentLoop(session=session, planner=ScriptedPlanner(task), max_steps=max_steps)

    error = ""
    finished = False
    try:
        result = loop.run(task.goal)
        finished = bool(result.get("ok"))
        if not finished:
            error = str(result.get("error", "unknown"))
    except Exception as exc:  # a crash is a failure, not a broken benchmark
        error = f"{type(exc).__name__}: {exc}"

    oracle = False
    try:
        oracle = bool(task.expect(site.counter, site))
    except Exception as exc:
        error = f"oracle error: {exc}"

    if task.safety_only:
        # Graded on what the site saw, not on whether the run finished. A
        # refused retry is supposed to end the run in error, so requiring
        # `finished` here would mark correct behaviour as a failure.
        passed = oracle
    else:
        # A run that errored is never a pass, even if the oracle is satisfied by
        # a side effect that happened before the failure. That combination once
        # turned a task that died at step 1 into a green row and inflated the
        # baseline from 30% to 50%.
        passed = finished and not error and oracle

    return {
        "name": task.name,
        "shape": task.shape,
        "irreversible": task.irreversible,
        "safety_only": task.safety_only,
        "passed": passed,
        "error": error,
        "submits": site.counter.submits,
        "steps": sum(1 for h in loop.history if h.get("kind") == "tool"),
    }


def run_all(tasks: list[Task] | None = None) -> dict:
    tasks = tasks if tasks is not None else TASKS
    results = [run_task(t) for t in tasks]
    passed = sum(1 for r in results if r["passed"])

    # Safety is reported separately and never averaged into the headline: a
    # double-submit is a different kind of wrong than a missed task.
    safety = [r for r in results if r["irreversible"]]
    safety_ok = sum(1 for r in safety if r["passed"])

    by_shape: dict[str, dict[str, int]] = {}
    for r in results:
        s = by_shape.setdefault(r["shape"], {"passed": 0, "total": 0})
        s["total"] += 1
        if r["passed"]:
            s["passed"] += 1

    return {
        "passed": passed,
        "total": len(results),
        "rate": round(passed / len(results), 4) if results else 0.0,
        "safety_passed": safety_ok,
        "safety_total": len(safety),
        "by_shape": by_shape,
        "results": results,
    }


# --------------------------------------------------------------------- cli --

CAVEAT = (
    "Measures the agent loop's control flow against a simulated site with a "
    "scripted planner. It does NOT measure real-world browsing ability, and a "
    "high score here is not evidence orvima can drive a real site."
)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="orvima bench", description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output only")
    ap.add_argument("--shape", help="only run tasks of this shape")
    ap.add_argument("--out", type=Path, help="write the full report to this JSON file")
    args = ap.parse_args(argv)

    tasks = TASKS
    if args.shape:
        tasks = [t for t in TASKS if t.shape == args.shape]
        if not tasks:
            print(f"no tasks with shape {args.shape!r}", file=sys.stderr)
            return 2

    report = run_all(tasks)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    else:
        width = max(len(t.name) for t in tasks)
        for r in report["results"]:
            mark = "ok  " if r["passed"] else "FAIL"
            flag = " [irreversible]" if r["irreversible"] else ""
            extra = f"  submits={r['submits']}" if r["irreversible"] and not r["passed"] else ""
            print(f"{mark} {r['name']:<{width}}  {r['shape']:<14}{flag}{extra}")
            if r["error"]:
                print(f"     -> {r['error']}")
        print()
        for shape, s in sorted(report["by_shape"].items()):
            print(f"  {shape:<14} {s['passed']}/{s['total']}")
        print()
        print(f"pass rate     {report['passed']}/{report['total']}  ({report['rate']:.0%})")
        print(
            f"safety        {report['safety_passed']}/{report['safety_total']} "
            "(irreversible actions done exactly once)"
        )
        print()
        print(f"note: {CAVEAT}")

    # Non-zero if any safety task failed, so a regression is loud in CI.
    return 0 if report["safety_passed"] == report["safety_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
