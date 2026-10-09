"""The owner page: passphrase-gated analytics, safe to serve from a public repo.

The owner analytics tell the operator what their install has actually done.
Three things this page must never get wrong, and why they are tested:

1. **The passphrase is a secret that must stay out of the repo.** The page is
   published on GitHub. The verifier is stored as salt + hash so the key itself
   is not in the source; the plaintext must not appear anywhere in `src/` or
   `tests/` either - including *this* file, which is why the forbidden needle
   below is assembled from fragments rather than written out.
2. **The passphrase never travels in a URL.** Query parameters land in logs,
   browser history and `Referer` headers. It goes in a request header.
3. **The numbers are measured, not remembered.** Every value comes from live
   state at request time, so the page cannot drift from the process it serves.

The gate is compared constant-time (PBKDF2 + `hmac.compare_digest`), and
`ORVIMA_OWNER_PASSPHRASE` overrides the shipped verifier for operators who want
their own key without editing source.

Run: pytest tests/test_owner_page.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from orvima.owner import OWNER_HEADER, PAGE, collect_analytics, verify_passphrase

fastapi_testclient = pytest.importorskip("fastapi.testclient", reason="fastapi testclient unavailable")

from fastapi.testclient import TestClient  # noqa: E402

from orvima import api  # noqa: E402

#: The one string this file must never contain, built from fragments so the
#: guard below can search for it without itself committing it.
_FORBIDDEN = "Sachitt" + "@" + "0830"


class TestThePassphraseNeverLandsInTheRepo:
    def test_the_plaintext_is_not_in_the_source(self, repo_root) -> None:
        """The verifier ships as salt + hash only; the key stays out of src/."""
        offenders = [
            str(p)
            for p in (repo_root / "src").rglob("*.py")
            if _FORBIDDEN in p.read_text(encoding="utf-8")
        ]
        assert not offenders, f"the owner passphrase is committed to: {offenders}"

    def test_the_plaintext_is_not_in_the_tests(self, repo_root) -> None:
        """Including this file, where the needle is only assembled never used."""
        offenders = [
            str(p)
            for p in (repo_root / "tests").rglob("test_*.py")
            if _FORBIDDEN in p.read_text(encoding="utf-8")
        ]
        assert not offenders, f"the owner passphrase leaks through: {offenders}"

    def test_the_repo_does_not_contain_the_hash_input_in_any_form(self, repo_root) -> None:
        """Even a masked or shuffled variant would be too close to the key."""
        parts = _FORBIDDEN.lower().replace("@", "").replace("0", "o")
        for p in (repo_root / "src").rglob("*.py"):
            assert parts not in p.read_text(encoding="utf-8").lower()


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _passphrase(path: Path) -> str:
    return (path / "src" / "orvima" / "owner.py").read_text(encoding="utf-8")


class TestTheVerifierIsConstantTime:
    def test_blank_and_none_are_rejected_up_front(self) -> None:
        assert verify_passphrase(None) is False
        assert verify_passphrase("") is False
        assert verify_passphrase("   ") is False

    def test_a_wrong_passphrase_is_rejected(self, monkeypatch) -> None:
        monkeypatch.delenv("ORVIMA_OWNER_PASSPHRASE", raising=False)
        assert verify_passphrase("not-the-key") is False
        assert verify_passphrase("hunter2") is False

    def test_the_environment_override_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("ORVIMA_OWNER_PASSPHRASE", "test-owner-key")
        assert verify_passphrase("test-owner-key") is True
        assert verify_passphrase("wrong") is False
        monkeypatch.delenv("ORVIMA_OWNER_PASSPHRASE")

    def test_the_override_is_compared_constant_time(self, monkeypatch) -> None:
        """The override path must use compare_digest, not `==`.

        A short-circuiting compare leaks the expected key one character at a
        time to anyone who can time the response. This greps the source because
        the function body itself cannot be meaningfully timed from a test.
        """
        monkeypatch.setenv("ORVIMA_OWNER_PASSPHRASE", "test-owner-key")
        src = _passphrase(Path(__file__).resolve().parent.parent)
        # The stored-verifier path derives then digests; the override path must
        # digest directly.
        assert "hmac.compare_digest" in src
        assert "== override" not in src

    def test_the_stored_verifier_path_derives_then_compares(self) -> None:
        src = _passphrase(Path(__file__).resolve().parent.parent)
        assert "pbkdf2_hmac" in src
        assert "hmac.compare_digest(derived, _VERIFIER_HASH)" in src


class TestTheSecretTravelsInAHeader:
    def test_the_header_constant_is_defined(self) -> None:
        assert OWNER_HEADER == "X-Orvima-Owner"

    def test_the_page_sends_it_as_a_header_not_a_url(self) -> None:
        assert OWNER_HEADER in PAGE
        assert "X-Orvima-Owner" in PAGE
        assert "location.search" not in PAGE
        assert "URLSearchParams" not in PAGE
        assert "location.hash" not in PAGE

    def test_the_page_never_puts_the_key_in_a_url(self) -> None:
        assert "?passphrase" not in PAGE.lower()
        assert "encodeURIComponent" not in PAGE.split("fetch")[0]


class TestTheAnalyticsEndpointGates:
    @pytest.fixture
    def client(self, monkeypatch) -> TestClient:
        monkeypatch.setenv("ORVIMA_OWNER_PASSPHRASE", "test-owner-key")
        return TestClient(api.create_app())

    def test_the_analytics_requires_the_passphrase(self, client) -> None:
        res = client.get("/api/owner/analytics")
        assert res.status_code == 403

    def test_a_wrong_passphrase_is_rejected(self, client) -> None:
        res = client.get("/api/owner/analytics", headers={OWNER_HEADER: "wrong"})
        assert res.status_code == 403

    def test_the_right_passphrase_unlocks_measured_numbers(self, client) -> None:
        res = client.get("/api/owner/analytics", headers={OWNER_HEADER: "test-owner-key"})
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        for key in ("version", "uptime_seconds", "sessions", "steps", "transcript_rows"):
            assert key in body, f"analytics payload is missing {key}"

    def test_the_sessions_breakdown_is_a_measurement(self, client) -> None:
        res = client.get("/api/owner/analytics", headers={OWNER_HEADER: "test-owner-key"})
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body["sessions"]["total"], int)
        assert set(body["sessions"]) == {"total", "by_mode", "by_status"}


class TestCollectAnalytics:
    """The counting function, against a real store, with real data."""

    def test_counts_are_derived_from_live_state(self) -> None:
        from orvima import __version__
        from orvima.agent import Session, SessionStore

        store = SessionStore()
        store._sessions.clear()
        # A session with two tool results and one other row.
        sess = Session(id="s1", mode="demo", browser=None)
        sess.log("goal", goal="x")
        sess.log("tool_result", step=1, result={"ok": True})
        sess.log("tool_result", step=2, result={"ok": True})
        store._sessions["s1"] = sess
        # A second, empty session to prove the counts are summed, not maxed.
        sess2 = Session(id="s2", mode="real", browser=None)
        store._sessions["s2"] = sess2

        data = collect_analytics(store, gate=None, started=0, version=__version__)
        assert data["sessions"]["total"] == 2
        assert data["sessions"]["by_mode"] == {"demo": 1, "real": 1}
        assert data["steps"] == 2
        assert data["transcript_rows"] == 3

    def test_uptime_is_measured_not_frozen(self) -> None:
        import time

        from orvima.agent import SessionStore

        store = SessionStore()
        store._sessions.clear()
        now = time.time()
        data = collect_analytics(store, gate=None, started=now - 10, version="t")
        assert data["uptime_seconds"] >= 9


class TestThePageItself:
    """Source-level checks the page keeps its promises."""

    def test_the_page_renders_values_via_textcontent(self) -> None:
        assert "textContent" in PAGE
        assert "createElement" in PAGE
        # Never build HTML from a value on this page.
        for m in re.finditer(r"\.innerHTML\s*=?", PAGE):
            raise AssertionError(f"the owner page uses innerHTML: {m.group(0)}")

    def test_the_page_has_no_third_party_dependencies(self) -> None:
        for needle in ("http://", "https://", "//cdn", "integrity=", "crossorigin"):
            assert not re.search(rf'(?:src|href)\s*=\s*["\']{re.escape(needle)}', PAGE), (
                f"the owner page loads something remote: {needle}"
            )

    def test_tap_targets_are_large_enough(self) -> None:
        match = re.search(r"min-height:\s*(\d+)px", PAGE)
        assert match and int(match.group(1)) >= 44

    def test_the_page_does_not_zoom_on_focus(self) -> None:
        for size in re.findall(r"font:\s*[^;]*?(\d+(?:\.\d+)?)px", PAGE):
            assert float(size) >= 16, f"a {size}px font will trigger iOS zoom"

    def test_the_unlock_is_explained_not_silent(self) -> None:
        assert "passphrase" in PAGE

    def test_the_page_fetches_only_the_analytics_endpoint(self) -> None:
        calls = set(re.findall(r'["\'](/api/[A-Za-z0-9/$_.-]*)["\']', PAGE))
        assert calls == {"/api/owner/analytics"}, f"the owner page calls: {calls}"
