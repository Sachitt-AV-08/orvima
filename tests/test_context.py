"""Bounded context on a long run.

The gate the plan asks for: a 50-step task completes within a bounded prompt
size, measured. The before-number was measured on this same fixture before any
of this existed - 50 steps cost 285,449 characters. Every bound below is checked
against that, not against a wish.

The honesty tests matter as much as the size tests. A truncated history that
looks complete teaches the planner it never took those steps, and it will take
them again - which for an irreversible action means paying twice.

Run: pytest tests/test_context.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from orvima.context import ContextBudget, compact_row, render_transcript  # noqa: E402
from orvima.planner import LLMPlanner  # noqa: E402

#: Measured on this fixture before context.py existed.
BEFORE_50_STEPS = 285_449

#: Generous, but well under the before-number, so the test cannot pass by luck.
BOUND_50_STEPS = 40_000


def result(i: int, ok: bool = True) -> dict:
    """A result roughly the size a real page produces."""
    return {
        "ok": ok,
        "url": f"https://example.test/checkout/step-{i}",
        "title": f"Checkout step {i}",
        "items": [{"ref": f"e{n}", "label": f"Item {n}"} for n in range(40)],
        "body": ("Lorem ipsum dolor sit amet " * 90)[:3000],
        "candidates": [{"ref": f"e{n}", "label": "c"} for n in range(10)],
    }


def history(steps: int, fail_every: int = 0) -> list[dict]:
    """``fail_every=3`` fails every third step; 0 means every step succeeds."""
    return [
        {
            "kind": "tool",
            "step": i,
            "tool": "browse_click",
            "args": {"ref": f"e{i}"},
            "result": result(i, ok=not (fail_every and i % fail_every == 0)),
        }
        for i in range(1, steps + 1)
    ]


class TestTheBoundIsReal:
    def test_fifty_steps_fit_in_a_bounded_prompt(self):
        transcript = render_transcript(history(50))
        assert len(transcript) < BOUND_50_STEPS, (
            f"50 steps cost {len(transcript)} chars; the pre-change figure was "
            f"{BEFORE_50_STEPS}"
        )

    def test_the_improvement_is_large_not_marginal(self):
        """A bound that barely moved would not be worth the code."""
        after = len(render_transcript(history(50)))
        assert after < BEFORE_50_STEPS / 5, (
            f"only {BEFORE_50_STEPS / after:.1f}x smaller than before"
        )

    def test_growth_is_slow_rather_than_linear(self):
        """The point of a budget: doubling the steps must not double the prompt.

        Not flat - each old step keeps a one-line record - but the slope has to
        be a small constant rather than one whole result per step.
        """
        at_50 = len(render_transcript(history(50)))
        at_100 = len(render_transcript(history(100)))
        growth = (at_100 - at_50) / at_50
        assert growth < 0.5, (
            f"100 steps cost {at_100} vs {at_50} at 50 - {growth:.0%} growth for "
            "2x the steps is still roughly linear"
        )

    def test_a_single_enormous_result_cannot_crowd_out_the_rest(self):
        rows = history(10)
        rows[5]["result"]["body"] = "x" * 500_000
        transcript = render_transcript(rows)
        assert len(transcript) < BOUND_50_STEPS, (
            f"one 500KB result pushed the prompt to {len(transcript)}"
        )


class TestWhatIsKeptAndWhatIsNot:
    def test_the_most_recent_steps_keep_their_full_result(self):
        budget = ContextBudget(detail_steps=6)
        transcript = render_transcript(history(50), budget)
        # A full row shows the result body; a compact row shows only the marker.
        assert "ok=True {'ok': True" in transcript, "the detail window lost its results"

    def test_older_steps_keep_whether_they_worked(self):
        """Whether a step worked changes behaviour; its body does not."""
        transcript = render_transcript(history(50, fail_every=3))
        assert "FAILED" in transcript, "an old failure became invisible"
        assert "step 1: browse_click" in transcript, "an old step vanished entirely"

    def test_an_old_error_keeps_its_reason(self):
        """"This failed and here is why" is the most useful thing to remember
        about an old step."""
        rows = history(50)
        rows[3] = {"kind": "error", "step": 3, "error": "net::ERR_CONNECTION_REFUSED"}
        transcript = render_transcript(rows)
        assert "ERR_CONNECTION_REFUSED" in transcript

    def test_the_element_outline_is_not_inlined_into_every_step(self):
        """items are the snapshot's job. Inlining them per step is what made
        each one cost thousands of characters."""
        transcript = render_transcript(history(20))
        assert "'items':" not in transcript, (
            "the element outline is being repeated in every step"
        )

    def test_a_screenshot_payload_never_reaches_the_transcript(self):
        """The payload is excluded by key, not by running out of clip budget.

        An earlier version of this test put png_b64 on a row that already had a
        3,000-character body, so the body consumed the whole per-result clip and
        the image was excluded for the wrong reason - removing the exclusion
        entirely still passed it. Kept here with a small result so the key
        exclusion is what is doing the work.
        """
        rows = history(5)
        rows[2]["result"] = {"ok": True, "url": "https://x.test", "png_b64": "A" * 100_000}
        transcript = render_transcript(rows)
        assert "AAAA" not in transcript, "base64 image data leaked into the prompt"
        assert "png_b64" not in transcript, (
            "the payload key itself is rendered, even if truncated"
        )

    def test_a_screenshot_payload_is_excluded_from_an_old_step_too(self):
        rows = history(50)
        rows[2]["result"] = {"ok": True, "url": "https://x.test", "png_b64": "A" * 100_000}
        transcript = render_transcript(rows)
        assert "png_b64" not in transcript

    def test_an_empty_history_renders_to_nothing(self):
        assert render_transcript([]) == ""
        assert render_transcript(None) == ""


class TestTruncationIsAnnounced:
    """The honesty requirement.

    Silently dropping history teaches a planner it never acted, and it will act
    again. Every removed span must leave a visible marker.
    """

    def test_the_detail_boundary_is_announced(self):
        transcript = render_transcript(history(50), ContextBudget(detail_steps=6))
        assert "earlier step(s) summarised" in transcript, (
            "the transcript drops old detail without saying so"
        )

    def test_dropping_whole_steps_under_the_ceiling_is_announced(self):
        transcript = render_transcript(
            history(400), ContextBudget(max_chars=4000)
        )
        assert "dropped entirely" in transcript, (
            "steps were removed by the ceiling with no notice"
        )

    def test_a_truncated_transcript_stays_under_its_ceiling(self):
        budget = ContextBudget(max_chars=4000)
        transcript = render_transcript(history(400), budget)
        # The notice itself is added after trimming, so allow a small margin
        # rather than pretending the ceiling is exact.
        assert len(transcript) < budget.max_chars * 1.2, (
            f"ceiling was {budget.max_chars}, produced {len(transcript)}"
        )

    def test_a_zero_detail_budget_still_shows_what_happened(self):
        """Worst case: nothing keeps its body. The one-liners must remain."""
        transcript = render_transcript(history(20), ContextBudget(detail_steps=0))
        assert "step 20:" in transcript
        assert "FAILED" in transcript or "-> ok" in transcript

    def test_a_zero_ceiling_does_not_lose_everything(self):
        transcript = render_transcript(history(10), ContextBudget(max_chars=1))
        assert transcript.strip(), "an impossible ceiling returned nothing at all"


class TestRedactionStillApplies:
    def test_a_secret_in_an_old_step_is_redacted_in_the_compact_form(self):
        rows = history(50)
        rows[2]["args"] = {"password": "hunter2", "ref": "e2"}
        transcript = render_transcript(
            rows, ContextBudget(detail_steps=3), redact=lambda d: {
                k: ("***" if "password" in k.lower() else v) for k, v in d.items()
            }
        )
        assert "hunter2" not in transcript

    def test_a_secret_in_a_recent_step_is_redacted_in_the_full_form(self):
        rows = history(50)
        rows[-1]["args"] = {"password": "hunter2", "ref": "e49"}
        transcript = render_transcript(
            rows, ContextBudget(detail_steps=3), redact=lambda d: {
                k: ("***" if "password" in k.lower() else v) for k, v in d.items()
            }
        )
        assert "hunter2" not in transcript


class TestThePlannerActuallySeesThePage:
    """A bug this module's sibling found by accident.

    _render tested ``row["tool"] == "snapshot"``. No tool has that name - it is
    browse_snapshot - so last_snapshot was always empty, and the ``if
    last_snapshot:`` guard meant the planner was never sent the current page at
    all. It re-planned from the goal and its own history, blind.

    Every end-to-end test uses a scripted planner, so nothing noticed.
    """

    def test_a_snapshot_row_produces_a_page_description(self):
        rows = history(3) + [
            {
                "kind": "tool",
                "step": 4,
                "tool": "browse_snapshot",
                "args": {},
                "result": {
                    "ok": True,
                    "url": "https://example.test/cart",
                    "title": "Your cart",
                    "items": [{"ref": "e1", "label": "Buy now"}],
                    "body": "Total 42.00",
                },
            }
        ]
        _transcript, snapshot = LLMPlanner._render(rows)
        assert snapshot, "the planner was sent no page at all"
        assert "https://example.test/cart" in snapshot
        assert "Your cart" in snapshot
        assert "Buy now" in snapshot
        assert "Total 42.00" in snapshot

    def test_the_most_recent_snapshot_wins(self):
        """A planner must see where it is now, not where it was."""
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://example.test/old", "title": "Old",
                        "items": [], "body": ""}},
            {"kind": "tool", "step": 2, "tool": "browse_click", "args": {}, "result": {"ok": True}},
            {"kind": "tool", "step": 3, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://example.test/new", "title": "New",
                        "items": [], "body": ""}},
        ]
        _transcript, snapshot = LLMPlanner._render(rows)
        assert "new" in snapshot and "Old" not in snapshot

    def test_a_failed_snapshot_does_not_become_the_page(self):
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": False, "error": "navigation failed"}},
        ]
        _transcript, snapshot = LLMPlanner._render(rows)
        assert snapshot == "", "a failed snapshot was reported as the current page"

    def test_a_huge_page_does_not_blow_up_the_snapshot(self):
        """A long page must not be able to crowd out the goal and history."""
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://x.test", "title": "T",
                        "items": [{"ref": f"e{n}", "label": "x" * 500} for n in range(500)],
                        "body": "y" * 200_000}},
        ]
        _transcript, snapshot = LLMPlanner._render(rows)
        assert len(snapshot) < 30_000, f"snapshot was {len(snapshot)} chars"


class TestCompactRowInIsolation:
    def test_a_missing_result_is_labelled_rather_than_assumed_ok(self):
        assert "no result" in compact_row({"step": 1, "tool": "t"}, ContextBudget())

    def test_a_failed_result_says_failed(self):
        row = {"kind": "tool", "step": 1, "tool": "t", "args": {}, "result": {"ok": False}}
        assert "FAILED" in compact_row(row, ContextBudget())

    def test_a_successful_result_says_ok(self):
        row = {"kind": "tool", "step": 1, "tool": "t", "args": {}, "result": {"ok": True}}
        assert compact_row(row, ContextBudget()).endswith("-> ok")


class TestWhichStepsSurviveTruncation:
    """Which end gets cut matters more than that something gets cut.

    Dropping the *oldest* loses background. Dropping the *newest* loses what the
    agent just did, so it repeats it - and for an irreversible action that means
    paying twice. The ceiling must cut from the old end only.
    """

    def test_the_newest_step_survives_a_hard_ceiling(self):
        transcript = render_transcript(history(60), ContextBudget(max_chars=3000))
        assert "step 60:" in transcript, (
            "the most recent step was truncated away - the planner would not "
            "know what it just did"
        )

    def test_the_newest_few_steps_all_survive(self):
        transcript = render_transcript(history(60), ContextBudget(max_chars=6000))
        for step in (57, 58, 59, 60):
            assert f"step {step}:" in transcript, f"step {step} was lost to the ceiling"

    def test_an_old_error_is_dropped_before_a_recent_success(self):
        """The right way round: recent facts beat old ones."""
        rows = history(60)
        rows[2] = {"kind": "error", "step": 2, "error": "ancient failure"}
        transcript = render_transcript(rows, ContextBudget(max_chars=3000))
        assert "step 60:" in transcript
        assert "ancient failure" not in transcript, (
            "the ceiling kept old history and dropped recent steps"
        )


class TestPerResultClipping:
    """Distinct from the ceiling, and separately load-bearing.

    The ceiling bounds the *total*. Per-result clipping bounds one result, so a
    single huge page cannot consume the whole prompt and squeeze out the goal and
    the other steps. A ceiling alone does not achieve this - it would silently
    drop everything after the big result.
    """

    def test_one_huge_result_is_clipped_even_with_a_generous_ceiling(self):
        rows = history(6)
        rows[3]["result"]["body"] = "z" * 400_000
        budget = ContextBudget(max_chars=10_000_000, max_result_chars=1500)
        transcript = render_transcript(rows, budget)
        assert len(transcript) < 10_000, (
            f"a single 400KB result produced {len(transcript)} chars despite a "
            "generous ceiling - only per-result clipping can prevent this"
        )
        assert "[clipped]" in transcript, "the clip is not even marked"

    def test_the_other_steps_survive_a_huge_result(self):
        """The point of clipping rather than ceiling-trimming: nothing else is lost."""
        rows = history(6)
        rows[3]["result"]["body"] = "z" * 400_000
        transcript = render_transcript(
            rows, ContextBudget(max_chars=10_000_000, max_result_chars=1500)
        )
        for step in (1, 2, 4, 5, 6):
            assert f"step {step}:" in transcript, f"step {step} was lost to one big result"


class TestThePlannerIsActuallySentThePage:
    """decide() is where the snapshot reaches the model.

    _render returning a snapshot is not the same as the message being sent, and
    only this level can tell the difference - the guard that silently dropped it
    was a single ``if last_snapshot:``.
    """

    def _sent_messages(self, history_rows, goal="do the thing"):
        """Run decide() against a stub provider and return what it was sent.

        ``decide`` does ``import httpx`` inside the function body, so patching
        the attribute on the planner module has no effect - the local import
        rebinds it. The real module's ``post`` is what has to be replaced.
        """
        import httpx

        captured: dict = {}

        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": '{"done": true}'}}]}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["messages"] = json["messages"]
            captured["url"] = url
            captured["auth"] = headers
            return FakeResp()

        original = httpx.post
        httpx.post = fake_post
        try:
            p = LLMPlanner(base="http://local.test/v1", key="k", model="m")
            p.decide(goal, history_rows)
        finally:
            httpx.post = original
        return captured

    def test_a_snapshot_reaches_the_model(self):
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://example.test/cart",
                        "title": "Your cart", "items": [{"ref": "e1", "label": "Buy now"}],
                        "body": "Total 42.00"}},
        ]
        captured = self._sent_messages(rows)
        sent = "\n".join(str(m.get("content", "")) for m in captured["messages"])
        assert "Current page snapshot" in sent, (
            "the snapshot was rendered but never sent to the planner"
        )
        assert "Your cart" in sent
        assert "Buy now" in sent
        assert captured["url"].startswith("http://local.test/v1"), (
            "the test did not intercept the real request path"
        )

    def test_the_goal_and_the_page_both_reach_the_model(self):
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://example.test/cart",
                        "title": "Cart", "items": [], "body": ""}},
        ]
        captured = self._sent_messages(rows, goal="buy the milk")
        sent = "\n".join(str(m.get("content", "")) for m in captured["messages"])
        assert "buy the milk" in sent
        assert "Current page snapshot" in sent

    def test_with_no_snapshot_there_is_no_snapshot_message(self):
        """Not sending an empty section is correct; not sending a real one is not."""
        captured = self._sent_messages(
            [{"kind": "tool", "step": 1, "tool": "browse_click", "args": {},
              "result": {"ok": True}}]
        )
        assert not any(
            "Current page snapshot" in str(m.get("content", ""))
            for m in captured["messages"]
        )

    def test_a_password_in_the_page_is_not_sent_to_the_model(self):
        rows = [
            {"kind": "tool", "step": 1, "tool": "browse_snapshot", "args": {},
             "result": {"ok": True, "url": "https://example.test/login",
                        "title": "Login", "items": [], "body": "",
                        "password": "hunter2"}},
        ]
        captured = self._sent_messages(rows)
        sent = "\n".join(str(m.get("content", "")) for m in captured["messages"])
        assert "hunter2" not in sent, "a password reached the model"
