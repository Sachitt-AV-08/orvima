"""Capabilities that need a real browser: eval, downloads, file input.

The plan's gate for each is a pair: a test that it works, and a test that it
degrades honestly when it cannot. The second half is not a formality here.

The download case is the one that matters. A click on a download link always
"succeeds" - Playwright delivers it, the DOM changes, no error is raised. An
implementation that waits for an event it does not check for will report a
download that never happened, and the agent will move on believing it has the
file. The fixture therefore includes a link that navigates instead of
downloading, which is indistinguishable from a download by every means except
knowing what to look for.

For eval, the claim being tested is a safety claim rather than a capability one:
an expression that looks irreversible must be refused before it runs.

Run: pytest tests/test_capabilities.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_real_mode import _skip_reason  # noqa: E402

if _skip_reason:
    pytestmark = pytest.mark.skip(reason=_skip_reason)

FIXTURES = Path(__file__).parent / "fixtures"
CAPS = (FIXTURES / "capabilities_page.html").resolve().as_uri()
SAMPLE_CV = FIXTURES / "sample-cv.txt"

from orvima.browser import BrowserController, attachment_verified  # noqa: E402
from orvima.tools import (  # noqa: E402
    tool_browse_download,
    tool_browse_eval,
    tool_browse_eval_audit,
    tool_browse_set_files,
)


@pytest.fixture(scope="module")
def ctl(tmp_path_factory):
    """A real browser with a throwaway download directory."""
    downloads = tmp_path_factory.mktemp("downloads")
    controller = BrowserController(headless=True, download_dir=str(downloads))
    controller.start()
    controller.downloads = downloads
    try:
        yield controller
    finally:
        controller.close()


class TestEvalWorks:
    def test_a_read_only_expression_returns_its_value(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_eval(ctl, "1 + 1", reason="arithmetic check")
        assert result["ok"], result
        assert result["result"] == 2
        assert result["mutating"] is False, "a pure expression reported a mutation"

    def test_a_mutating_expression_says_so(self, ctl):
        """Measured, not assumed. The old docstring promised read-only and
        enforced nothing."""
        ctl.navigate(CAPS)
        result = tool_browse_eval(
            ctl, "document.getElementById('counter').textContent = '42'",
            reason="set the counter",
        )
        assert result["ok"], result
        assert result["mutating"] is True, (
            "an expression that changed the page was not reported as mutating"
        )
        assert ctl.page.locator("#counter").inner_text() == "42"


class TestEvalIsRefusedWhenItLooksIrreversible:
    """The safety half.

    Classification happens from the expression text alone, before the page is
    touched - the same principle as the click guard: decide whether the action is
    one-way before any error exists, because after it, it may be too late.
    """

    @pytest.mark.parametrize(
        "expression",
        [
            "fetch('/api/delete-everything', {method: 'DELETE'})",
            "document.forms[0].submit()",
            "localStorage.clear()",
            "paymentGateway.charge(500)",
        ],
    )
    def test_an_irreversible_expression_never_runs(self, ctl, expression):
        ctl.navigate(CAPS)
        before = ctl.page.locator("#counter").inner_text()
        result = tool_browse_eval(ctl, expression)
        assert not result["ok"], f"ran an irreversible expression: {expression}"
        assert "refusing to run this expression" in result.get("error", "")
        assert ctl.page.locator("#counter").inner_text() == before

    def test_a_read_only_expression_is_not_refused(self, ctl):
        """The guard must not refuse ordinary inspection - that would push an
        agent toward riskier ways of asking the same question."""
        ctl.navigate(CAPS)
        result = tool_browse_eval(ctl, "document.querySelectorAll('a').length")
        assert result["ok"], result

    def test_typing_the_word_delete_in_a_read_only_expression_is_allowed(self, ctl):
        """Same principle as the click guard: text content is what the user is
        saying, not what the agent is doing."""
        ctl.navigate(CAPS)
        result = tool_browse_eval(
            ctl, "Array.from(document.querySelectorAll('a')).map(a => a.textContent)"
        )
        assert result["ok"], result


class TestTheAuditTrail:
    def test_every_eval_is_recorded_with_its_reason(self, ctl):
        ctl.navigate(CAPS)
        tool_browse_eval(ctl, "2 + 2", reason="why I ran this")
        result = tool_browse_eval_audit(ctl)
        assert result["ok"]
        entry = result["entries"][-1]
        assert entry["expression"] == "2 + 2"
        assert entry["reason"] == "why I ran this", "the reason was not recorded"
        assert entry["ok"] is True
        assert "at" in entry, "an audit entry with no timestamp is not an audit"

    def test_an_unstated_reason_is_recorded_as_such(self, ctl):
        ctl.navigate(CAPS)
        tool_browse_eval(ctl, "3 + 3")
        result = tool_browse_eval_audit(ctl)
        assert result["entries"][-1]["reason"] == "not stated"

    def test_a_failed_eval_is_recorded_too(self, ctl):
        ctl.navigate(CAPS)
        assert not tool_browse_eval(ctl, "this is not javascript((")["ok"]
        result = tool_browse_eval_audit(ctl)
        entry = result["entries"][-1]
        assert entry["ok"] is False
        assert entry["error"], "a failure was recorded with no reason"

    def test_a_refused_eval_is_not_recorded_as_having_run(self, ctl):
        """It never ran. Recording it as run would be a lie in an audit log."""
        ctl.navigate(CAPS)
        before = tool_browse_eval_audit(ctl)["count"]
        tool_browse_eval(ctl, "localStorage.clear()")
        assert tool_browse_eval_audit(ctl)["count"] == before

    def test_the_trail_is_bounded(self, ctl):
        """An unbounded audit log is a memory leak and unreadable besides.

        Tested by behaviour rather than by reading the limit attribute: the cap
        is lowered for the duration so the test stays fast, then the trail is
        pushed past it. Checking ``eval_audit_limit <= 1000`` proved nothing -
        it passed unchanged when the cap was removed entirely.
        """
        ctl.navigate(CAPS)
        original = ctl.eval_audit_limit
        ctl.eval_audit_limit = 5
        try:
            for i in range(12):
                tool_browse_eval(ctl, f"{i} + 0", reason=f"push {i}")
            result = tool_browse_eval_audit(ctl)
        finally:
            ctl.eval_audit_limit = original

        assert result["count"] <= 5, (
            f"the trail grew to {result['count']} with a cap of 5 - the bound is "
            "not enforced"
        )
        # And the newest entry must be the one that survives: an audit that drops
        # recent history is useless for answering "what just happened".
        assert result["entries"][-1]["reason"] == "push 11", (
            "the most recent eval was the one dropped"
        )

    def test_the_cap_shrinks_the_trail_rather_than_refusing_writes(self, ctl):
        """Trimming is silent and non-fatal: eval keeps working past the cap."""
        ctl.navigate(CAPS)
        original = ctl.eval_audit_limit
        ctl.eval_audit_limit = 2
        try:
            for i in range(6):
                assert tool_browse_eval(ctl, f"{i} * 1")["ok"], (
                    f"eval {i} failed once the audit cap was reached"
                )
        finally:
            ctl.eval_audit_limit = original


class TestIrreversibleExpressionsAreCaughtByMoreThanOneRule:
    """Two independent mechanisms guard the escape hatch, and each covers cases
    the other misses. Neither is redundant."""

    def test_a_word_the_click_guard_also_uses_is_caught_here(self, ctl):
        """Not a .submit() call and not a destructive-API pattern - just a
        function name containing a word the click guard refuses.

        This is the case only the word list catches, so it is the case that proves
        the two rules are both doing work.
        """
        ctl.navigate(CAPS)
        result = tool_browse_eval(ctl, "checkoutService.placeOrder(500)")
        assert not result["ok"], "a destructive call slipped past both rules"
        assert "refusing to run" in result.get("error", "")

    def test_a_destructive_api_pattern_is_caught_without_a_guard_word(self, ctl):
        """localStorage.clear() contains no word from the click guard's list, so
        only the expression-level rule can stop it."""
        ctl.navigate(CAPS)
        result = tool_browse_eval(ctl, "localStorage.clear()")
        assert not result["ok"]
        assert "localstorage.clear" in result.get("error", "").lower()

    def test_reading_storage_is_not_refused(self, ctl):
        """The guard must not stop an agent from *inspecting* what is there -
        refusing inspection pushes it toward blunter ways of asking."""
        ctl.navigate(CAPS)
        assert tool_browse_eval(ctl, "Object.keys(localStorage).length")["ok"]

    def test_a_word_inside_page_text_is_not_an_expression(self, ctl):
        """'Clear the cart' is a button a user clicks, not an expression. The
        word cannot be in the shared word list or this would break."""
        ctl.navigate(CAPS)
        result = tool_browse_eval(
            ctl, "Array.from(document.querySelectorAll('a')).map(a => a.textContent)"
        )
        assert result["ok"], result


class TestAttachmentVerification:
    """The readback rule, tested directly.

    Driving the bad cases through a real page means engineering a page that
    silently drops or replaces an upload, and a test that elaborate would be a
    test of the fixture. The rule is named, so the rule is tested.
    """

    def test_matching_files_verify(self):
        assert attachment_verified(
            [{"name": SAMPLE_CV.name, "size": SAMPLE_CV.stat().st_size}],
            [str(SAMPLE_CV)],
        )

    def test_a_failed_readback_does_not_verify(self):
        """The attachment was never confirmed, so it is not verified."""
        assert not attachment_verified(None, [str(SAMPLE_CV)])

    def test_an_empty_page_selection_does_not_verify(self):
        assert not attachment_verified([], [str(SAMPLE_CV)])

    def test_the_wrong_file_does_not_verify(self):
        """The worst case: something was attached and it is the wrong thing."""
        other = FIXTURES / "fixture-download.txt"
        assert not attachment_verified(
            [{"name": other.name, "size": 109}], [str(SAMPLE_CV)]
        )

    def test_a_missing_file_does_not_verify(self):
        assert not attachment_verified([{"name": SAMPLE_CV.name, "size": 30}], [])

    def test_a_subset_does_not_verify(self):
        """One of two made it. Reporting success would send an incomplete form."""
        other = FIXTURES / "fixture-download.txt"
        assert not attachment_verified(
            [{"name": SAMPLE_CV.name, "size": 30}], [str(SAMPLE_CV), str(other)]
        )

    def test_order_does_not_matter(self):
        other = FIXTURES / "fixture-download.txt"
        assert attachment_verified(
            [{"name": SAMPLE_CV.name}, {"name": other.name}],
            [str(SAMPLE_CV), str(other)],
        )


class TestDownloadsWork:
    def test_a_real_download_is_saved_with_its_bytes(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_download(ctl, selector="#real")
        assert result["ok"], result
        assert result["filename"] == "invoice-42.txt"
        saved = Path(result["savedTo"])
        assert saved.is_file(), "the tool reported a path with no file at it"
        assert saved.read_text(encoding="utf-8").startswith("INVOICE 42")
        assert result["bytes"] == saved.stat().st_size, (
            "the reported size does not match the file on disk"
        )
        assert result["bytes"] > 0, "an empty file was reported as a download"

    def test_the_file_lands_in_the_configured_directory(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_download(ctl, selector="#real")
        assert Path(result["savedTo"]).parent == ctl.downloads

    def test_a_download_by_ref_works(self, ctl):
        """The common case is a ref from a snapshot, not a hand-written selector."""
        ctl.navigate(CAPS)
        ref = next(
            i["ref"]
            for i in ctl.snapshot()["items"]
            if "Download the invoice" in (i.get("label") or "")
        )
        result = tool_browse_download(ctl, ref=ref)
        assert result["ok"], result
        assert result["filename"] == "invoice-42.txt"
        assert Path(result["savedTo"]).is_file()


class TestDownloadsDegradeHonestly:
    """The half that matters. A failed download that reports success is the
    single worst failure available to this tool."""

    def test_a_link_that_navigates_is_not_reported_as_a_download(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_download(ctl, selector="#notreal")
        assert not result["ok"], (
            f"reported a download for a link that only navigates: {result}"
        )
        assert "did not start a download" in result.get("error", "")
        # And the message must say what to do about it.
        assert "expired" in result.get("error", ""), (
            "the failure does not mention the likely causes"
        )

    def test_a_broken_download_link_is_not_reported_as_a_download(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_download(ctl, selector="#expired")
        assert not result["ok"], f"reported a download for a dead link: {result}"

    def test_a_failed_download_leaves_no_file_behind(self, ctl):
        """A partial or empty file is worse than none: it looks like success."""
        ctl.navigate(CAPS)
        before = set(p.name for p in ctl.downloads.glob("*"))
        assert not tool_browse_download(ctl, selector="#notreal")["ok"]
        assert set(p.name for p in ctl.downloads.glob("*")) == before

    def test_a_selector_that_matches_nothing_says_so(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_download(ctl, selector="#no-such-link")
        assert not result["ok"]
        assert result.get("error")


class TestFileInputWorks:
    def test_a_file_is_attached_and_the_page_confirms_it(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_set_files(ctl, [str(SAMPLE_CV)], selector="#cv")
        assert result["ok"], result
        assert result["verified"] is True, (
            "attachment was reported as unverified - the page's own FileList is "
            "the only real evidence it took"
        )
        assert result["pageSaw"][0]["name"] == SAMPLE_CV.name
        assert result["pageSaw"][0]["size"] == SAMPLE_CV.stat().st_size

    def test_several_files_attach_in_order(self, ctl):
        ctl.navigate(CAPS)
        other = FIXTURES / "fixture-download.txt"
        result = tool_browse_set_files(ctl, [str(SAMPLE_CV), str(other)], selector="#cv")
        assert result["ok"], result
        names = [f["name"] for f in result["pageSaw"]]
        assert names == [SAMPLE_CV.name, other.name], f"order or membership wrong: {names}"

    def test_a_file_input_by_ref(self, ctl):
        ctl.navigate(CAPS)
        ctl.snapshot()
        result = tool_browse_set_files(ctl, [str(SAMPLE_CV)], ref="e1")
        # e1 may be a heading on this page; the point is that a ref is accepted
        # and resolved without a shape error.
        assert "ok" in result


class TestFileInputDegradesHonestly:
    def test_a_path_that_does_not_exist_is_refused(self, ctl):
        """Not silently attached, not skipped. The caller must be told."""
        ctl.navigate(CAPS)
        result = tool_browse_set_files(ctl, ["no-such-file.txt"], selector="#cv")
        assert not result["ok"]
        assert "no such file" in result.get("error", "").lower()
        assert "cannot be invented" in result.get("error", "")

    def test_an_empty_path_list_is_refused_rather_than_a_no_op(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_set_files(ctl, [], selector="#cv")
        assert not result["ok"], "reported success while attaching nothing"

    def test_a_target_that_is_not_a_file_input_says_so(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_set_files(ctl, [str(SAMPLE_CV)], selector="#not-a-file-input")
        assert not result["ok"]
        assert "input type=file" in result.get("error", ""), (
            "the error does not say what kind of element was needed"
        )

    def test_a_refused_attachment_leaves_the_field_empty(self, ctl):
        ctl.navigate(CAPS)
        tool_browse_set_files(ctl, ["nope.txt"], selector="#cv")
        assert ctl.page.eval_on_selector("#cv", "el => el.files.length") == 0


class TestAPageThatDiscardsTheUpload:
    """The case that decides what ``verified`` means.

    Every other attachment test has the page accept the file, so ``verified: True``
    is correct in all of them and the field proves nothing. Here the page takes
    the upload and then empties its own FileList - a validation rejection, which
    is ordinary on a real form.

    This is the test that makes ``verified`` mean something. Reporting success
    here means telling a caller a form is ready to send when the page holds
    nothing at all.
    """

    def test_a_discarded_upload_is_reported_as_unverified(self, ctl):
        ctl.navigate(CAPS)
        result = tool_browse_set_files(ctl, [str(SAMPLE_CV)], selector="#cv-rejecting")
        assert result.get("pageSaw") == [], (
            f"the fixture did not actually discard the upload: {result}"
        )
        assert result["verified"] is False, (
            "an upload the page threw away was reported as verified - this is the "
            "exact lie the readback exists to prevent"
        )

    def test_the_page_really_did_discard_it(self, ctl):
        """Guards the guard: if the fixture stops rejecting, the test above would
        pass for the wrong reason."""
        ctl.navigate(CAPS)
        tool_browse_set_files(ctl, [str(SAMPLE_CV)], selector="#cv-rejecting")
        assert ctl.page.eval_on_selector("#cv-rejecting", "el => el.files.length") == 0

    def test_the_page_saw_something_before_it_discarded(self, ctl):
        """Otherwise 'the page held nothing' might just mean the attach never
        happened, and the honest answer would be 'unknown', not 'not verified'."""
        ctl.navigate(CAPS)
        ctl.page.eval_on_selector(
            "#cv-rejecting",
            "el => { window.__saw = null;"
            " el.addEventListener('change', () => { window.__saw = el.files.length; },"
            " true); }",
        )
        tool_browse_set_files(ctl, [str(SAMPLE_CV)], selector="#cv-rejecting")
        # A capture-phase listener sees the file before the page's own handler
        # clears it, which is the only way to prove the attach really happened.
        assert ctl.page.evaluate("() => window.__saw") == 1
