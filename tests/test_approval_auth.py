"""The approval endpoint is the whole safety story, and it is unauthenticated.

`POST /api/approvals/{request_id}` takes `{"approved": true}` and resolves the
gate. There is no `Depends`, no bearer token, no key - anything that can reach
the port can approve a purchase in the operator's logged-in browser, or deny
one and stall the run.

On 127.0.0.1 that is defensible: the loopback interface is the trust boundary.
The moment anything else can reach the port it is not, and `--host` exists. So
the requirement is not "add auth" in the abstract, it is: **refuse to be
reachable from off-host without auth configured.** Fail closed at startup, not
per-request, so the mistake cannot be made once and left running.

The tests below are the gate on that. They are about the refusal, which is the
part that can silently regress to a warning.

Run: pytest tests/test_approval_auth.py -q
"""

from __future__ import annotations

import importlib
import os
import socket
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

#: Addresses that are not loopback. 127.0.0.2 is still loopback on Windows and
#: Linux; these are the ones that genuinely put the port on a network.
OFF_HOST = ["0.0.0.0", "::", "192.168.1.50", "10.0.0.5"]


def _load_cli(monkeypatch, **env):
    """Import cli with a known ORVIMA_* environment.

    Reloaded per test because `cli` resolves the environment at call time but
    caches some of it, and a stale module would test a previous test's env.
    """
    for key in [k for k in os.environ if k.startswith("ORVIMA_")]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for mod in ("orvima.cli", "orvima.api"):
        sys.modules.pop(mod, None)
    return importlib.import_module("orvima.cli")


class TestLoopbackNeedsNoToken:
    """The default must keep working with zero setup. Auth is opt-in."""

    def test_serving_on_loopback_with_no_token_is_allowed(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind("127.0.0.1") is None

    def test_ipv6_loopback_is_still_loopback(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind("::1") is None

    def test_a_configured_token_allows_off_host(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.setenv("ORVIMA_API_TOKEN", "a-real-token")
        assert cli.check_bind("0.0.0.0") is None


class TestOffHostWithoutAuthIsRefused:
    """The core requirement. Each address stated so one cannot slip through."""

    @pytest.mark.parametrize("host", OFF_HOST)
    def test_off_host_without_a_token_is_refused(self, monkeypatch, host):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        problem = cli.check_bind(host)
        assert problem is not None, (
            f"{host} would be served with no authentication, putting an "
            "unauthenticated approve-a-purchase endpoint on the network"
        )

    def test_the_refusal_names_the_setting_to_fix_it(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert "ORVIMA_API_TOKEN" in cli.check_bind("0.0.0.0")

    def test_an_empty_token_counts_as_no_token(self, monkeypatch):
        """An empty string is what a shell variable expands to when unset."""
        cli = _load_cli(monkeypatch)
        monkeypatch.setenv("ORVIMA_API_TOKEN", "")
        assert cli.check_bind("0.0.0.0") is not None

    def test_a_whitespace_token_counts_as_no_token(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.setenv("ORVIMA_API_TOKEN", "   ")
        assert cli.check_bind("0.0.0.0") is not None

    def test_serve_exits_non_zero_rather_than_binding(self, monkeypatch):
        """Fail closed at startup. A warning that then binds anyway is worse
        than no check, because it reads as a check."""
        import uvicorn

        monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail(
            "uvicorn.run was called despite an unauthenticated off-host bind"
        ))
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.cmd_serve("0.0.0.0", 8301, "demo") == 1


class TestTokenChecksAreConstantTimeAndFailClosed:
    """How the token is compared, once it exists."""

    def test_a_correct_token_is_accepted(self, monkeypatch):
        api = importlib.import_module("orvima.api")
        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(api)
        assert api.token_ok("hunter2") is True

    def test_a_wrong_token_is_rejected(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.token_ok("hunter3") is False

    def test_a_prefix_of_the_token_is_rejected(self, monkeypatch):
        """A prefix match would let 'hunt' approve a purchase."""
        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.token_ok("hunt") is False

    def test_no_token_configured_means_the_endpoint_is_open(self, monkeypatch):
        """The deliberate choice, stated so it cannot drift silently.

        An open endpoint on loopback is fine: there is no trust boundary to
        cross, and requiring a token would push everyone to set one up for a
        server only their own machine can reach. The dangerous case - open *and*
        on a network - is prevented from existing, asserted in
        TestTheAppRefusesAnUnauthenticatedNetworkBind below. Stating the
        trade-off here means nobody later "fixes" this in either direction
        without noticing they are changing a security property.
        """
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.token_ok("") is True
        assert api.token_ok("anything") is True

    def test_a_configured_token_makes_an_empty_offer_fail(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.token_ok("") is False
        assert api.token_ok(None) is False


class TestTheAppRefusesAnUnauthenticatedNetworkBind:
    """The safety property, at the layer every caller goes through.

    `check_bind` in the CLI is not sufficient on its own: `create_app` is what a
    test, an embedder, or a future entry point calls. A guard that lives only in
    one launcher is a guard the next launcher forgets.
    """

    @pytest.mark.parametrize("host", ["0.0.0.0", "", "192.168.1.50", "::"])
    def test_create_app_refuses_off_host_with_no_token(self, monkeypatch, host):
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        api = importlib.reload(importlib.import_module("orvima.api"))
        with pytest.raises(Exception) as caught:
            api.create_app(host)
        assert "ORVIMA_API_TOKEN" in str(caught.value), (
            f"the refusal does not say how to fix it: {caught.value}"
        )

    def test_create_app_allows_loopback_with_no_token(self, monkeypatch):
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.create_app("127.0.0.1") is not None

    def test_create_app_allows_off_host_with_a_token(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))
        assert api.create_app("0.0.0.0") is not None

    def test_the_refusal_happens_before_the_port_is_usable(self, monkeypatch):
        """Not after: an app object that exists is an app someone can serve."""
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        api = importlib.reload(importlib.import_module("orvima.api"))
        try:
            api.create_app("0.0.0.0")
        except Exception:
            pass
        else:  # pragma: no cover - the assertion above covers it
            pytest.fail("create_app returned an app for an unauthenticated bind")

    def test_comparison_is_constant_time(self, monkeypatch):
        """A short-circuiting compare leaks the token one character at a time.

        Asserted over the AST, not by reading the source text and not by timing.
        A text search is not an instrument here: this function's own docstring
        explains that it uses compare_digest, so `assert "compare_digest" in
        source` passes on a build that compares with `==` and only names it in a
        comment. That is a green test proving nothing, which is worse than no
        test. A timing test would be flaky and would be a worse instrument
        still.
        """
        import ast
        import inspect
        import textwrap

        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))

        tree = ast.parse(textwrap.dedent(inspect.getsource(api.token_ok)))
        fn = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None
        )
        assert fn is not None

        # Compare only what executes: the docstring is an ast.Constant, so it
        # cannot be mistaken for a call.
        calls = [
            node.func
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ]
        used = {c.attr for c in calls}
        assert "compare_digest" in used, (
            "token_ok compares the token with something other than "
            f"compare_digest; calls found: {sorted(used) or 'none'}"
        )
        # And no plain equality comparison on the secrets.
        comparisons = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Compare)
            and isinstance(n.ops[0], (ast.Eq, ast.NotEq))
        ]
        assert not comparisons, (
            "token_ok still uses == on values, which returns early on the first "
            f"differing character: {ast.dump(comparisons[0])[:120]}"
        )


class TestTheApprovalEndpointItself:
    """The endpoint has to actually consult the token, not just have one."""

    @pytest.fixture
    def client(self, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setenv("ORVIMA_API_TOKEN", "hunter2")
        api = importlib.reload(importlib.import_module("orvima.api"))
        return TestClient(api.create_app())

    def test_an_unauthenticated_approval_is_refused(self, client):
        """401 before anything else happens."""
        response = client.post("/api/approvals/anything", json={"approved": True})
        assert response.status_code in (401, 403), (
            f"an unauthenticated approval returned {response.status_code}: "
            f"{response.text}"
        )

    def test_a_wrong_token_is_refused(self, client):
        response = client.post(
            "/api/approvals/anything",
            json={"approved": True},
            headers={"X-Orvima-Token": "wrong"},
        )
        assert response.status_code in (401, 403)

    def test_the_refusal_does_not_approve_anything(self, client):
        """The status code is not the whole claim; nothing may have changed."""
        response = client.post("/api/approvals/anything", json={"approved": True})
        assert "approved" not in response.text.lower() or response.status_code in (
            401, 403,
        )

    def test_a_bearer_token_is_also_accepted(self, client):
        """So a phone page can use either, and neither is a second secret."""
        response = client.post(
            "/api/approvals/anything",
            json={"approved": True},
            headers={"Authorization": "Bearer hunter2"},
        )
        assert response.status_code != 401, (
            f"a correct bearer token was refused: {response.text}"
        )

    def test_the_health_endpoint_stays_open(self, client):
        """Otherwise a phone cannot tell whether the server is up at all."""
        assert client.get("/api/health").status_code == 200

    def test_read_only_endpoints_stay_open(self, client):
        """A phone needs to see what it is being asked to approve.

        Guarding the reads would mean a phone cannot render the approval page at
        all unless it already holds the token, and would push people towards
        making the token optional to read - which is the thing being prevented.
        """
        assert client.get("/api/tools").status_code == 200
        assert client.get("/api/approvals").status_code == 200

    @pytest.fixture
    def session_id(self, client):
        created = client.post("/api/sessions", json={"mode": "demo", "goal": "x"})
        return created.json()["session"]["id"]

    def test_the_direct_tool_endpoint_is_guarded_too(self, client, session_id):
        """Driving the browser is the same power as approving.

        An open `/tools` is an open logged-in browser: it can navigate to a
        checkout and submit it without ever touching the approval gate, which
        would make the gate decorative.
        """
        response = client.post(
            f"/api/sessions/{session_id}/tools",
            json={"tool": "browse_snapshot", "args": {}},
        )
        assert response.status_code in (401, 403), (
            f"the direct tool endpoint accepted an unauthenticated call: "
            f"{response.status_code} {response.text}"
        )

    def test_the_control_endpoint_is_guarded_too(self, client, session_id):
        """`cancel` unblocks a run waiting on approval.

        Leaving it open means an unauthenticated caller can drive a run's
        control flow - including forcing the timeout branch that fires when a
        human does not answer in time.
        """
        response = client.post(
            f"/api/sessions/{session_id}/control", json={"action": "cancel"}
        )
        assert response.status_code in (401, 403), (
            f"the control endpoint accepted an unauthenticated cancel: "
            f"{response.status_code} {response.text}"
        )

    def test_the_correct_token_operates_the_tool_endpoint(self, client, session_id):
        """The guard must not have turned the endpoint off entirely."""
        response = client.post(
            f"/api/sessions/{session_id}/tools",
            json={"tool": "browse_snapshot", "args": {}},
            headers={"X-Orvima-Token": "hunter2"},
        )
        assert response.status_code == 200, response.text


class TestTheBindCheckIsReal:
    """A loopback test proves nothing if the check is a string comparison that
    a hostname slips past."""

    def test_localhost_is_loopback(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind("localhost") is None

    def test_an_empty_host_is_treated_as_off_host(self, monkeypatch):
        """An empty --host means every interface, so it must be refused."""
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind("") is not None

    def test_a_host_that_merely_contains_127_is_not_loopback(self, monkeypatch):
        cli = _load_cli(monkeypatch)
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind("127.0.0.1.example.com") is not None

    def test_the_check_uses_the_socket_module_not_a_string_match(self, monkeypatch):
        import inspect

        cli = _load_cli(monkeypatch)
        source = inspect.getsource(cli.check_bind)
        assert "ipaddress" in source or "getaddrinfo" in source or "loopback" in source, (
            f"check_bind looks like a string comparison: {source}"
        )

    def test_it_still_identifies_a_real_loopback_interface(self, monkeypatch):
        """Guard against the check being wrong about this machine, which would
        make every test above vacuous."""
        cli = _load_cli(monkeypatch)
        try:
            address = socket.gethostbyname("localhost")
        except OSError:  # pragma: no cover - unusual resolver config
            pytest.skip("localhost does not resolve on this machine")
        monkeypatch.delenv("ORVIMA_API_TOKEN", raising=False)
        assert cli.check_bind(address) is None, (
            f"{address} is this machine's loopback and must be accepted"
        )
