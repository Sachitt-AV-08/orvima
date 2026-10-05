"""Real must be the default at every door, not just the CLI.

orvima had one silent-demo defect and then a second one hiding behind it. The
first was `resolve_mode` defaulting to `demo`, so `orvima mcp` with no flags
answered `{"ok": true}` about a scripted site. The second was that fixing only
that function would have left `POST /api/sessions` still defaulting to `demo`
and to `https://acme.dev` -- the same lie through a different door, for anyone
using the HTTP API or importing the library.

So this file asserts the default at each entry point separately. They are
separate defaults in separate modules and can drift apart, which is exactly what
happened once already.

It also pins the two things that must *stay* available: the offline tour has to
remain one flag away, and it must never be described as ready.

Run: pytest tests/test_real_is_the_default.py -q
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from orvima import api, cli, mcp_server
from orvima.agent import Session, SessionStore


class TestEveryEntryPointDefaultsToReal:
    def test_the_cli_resolver(self):
        assert cli.resolve_mode(None) == "real", (
            "an invocation with no --mode and no ORVIMA_MODE would not drive a "
            "real browser"
        )

    def test_an_explicit_flag_still_wins(self):
        assert cli.resolve_mode("demo") == "demo", "the offline tour must stay reachable"

    def test_the_environment_variable_still_works(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_MODE", "demo")
        assert cli.resolve_mode(None) == "demo", (
            "ORVIMA_MODE is the documented switch; it must still take effect"
        )

    def test_the_http_api_request_model(self):
        """Checked on the model, not on the endpoint.

        The model is where the default lives; a test that posts to the endpoint
        could pass while the default was silently reinstated elsewhere.
        """
        assert api.CreateSession().mode == "real", (
            "POST /api/sessions with no body would create a simulated session"
        )

    def test_a_new_session_is_not_parked_on_a_fictional_site(self):
        assert api.CreateSession().start_url == "", (
            "a session with no URL is silently pointed at a fictional storefront; "
            "start_url must default to empty so the browser sits at about:blank"
        )

    def test_the_mcp_server_library_default(self):
        """`run()` is public. Its default is what an importer gets."""
        default = inspect.signature(mcp_server.run).parameters["demo"].default
        assert default is False, (
            "mcp_server.run() defaults to a simulator; an importing caller who "
            "passes nothing gets a fake browser"
        )

    def test_the_session_store_default_url(self):
        default = inspect.signature(SessionStore.create).parameters["start_url"].default
        assert default == "", f"SessionStore.create still defaults start_url to {default!r}"

    def test_the_session_dataclass_default_url(self):
        assert Session.__dataclass_fields__["start_url"].default == "", (
            "a bare Session still claims to start on a fictional storefront"
        )


class TestTheRealDefaultIsHonouredEndToEnd:
    """The defaults above are only useful if they reach an actual response."""

    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setenv("ORVIMA_SENTINEL", "off")
        return TestClient(api.create_app("127.0.0.1"))

    def test_a_session_created_with_no_body_asks_for_a_real_browser(self, client, monkeypatch):
        # No mode is sent. If the app tried to launch a browser this test would
        # open a real window, so the factory is stubbed -- what is under test is
        # the mode the request resolved to, not Playwright.
        seen: dict = {}

        def fake_create(self, mode: str, start_url: str = "", goal: str = ""):
            seen["mode"] = mode
            seen["start_url"] = start_url
            return Session(id="stubbed01", mode=mode, browser=None, start_url=start_url)

        monkeypatch.setattr(api.SessionStore, "create", fake_create)
        body = client.post("/api/sessions", json={}).json()
        assert body["session"]["mode"] == "real", body
        assert seen["mode"] == "real", (
            f"the API created a {seen['mode']!r} session for a client that asked for nothing"
        )
        assert seen["start_url"] == "", seen["start_url"]

    def test_demo_is_still_available_through_the_api(self, client, monkeypatch):
        seen: dict = {}

        def fake_create(self, mode: str, start_url: str = "", goal: str = ""):
            seen["mode"] = mode
            return Session(id="stubbed02", mode=mode, browser=None, start_url=start_url)

        monkeypatch.setattr(api.SessionStore, "create", fake_create)
        client.post("/api/sessions", json={"mode": "demo"})
        assert seen["mode"] == "demo", "the offline tour must remain reachable over HTTP"


class TestRealModeUsesTheUrlTheCallerAskedFor:
    """`start_url` used to be accepted by the API and then thrown away.

    An earlier version of this test monkeypatched `_make_browser` itself, which
    meant it asserted that its own stub was called and passed no matter what the
    real factory did. The mutation harness caught that. So the real factory runs
    here, with only Playwright's controller swapped out.
    """

    def test_the_browser_factory_is_given_the_requested_url(self, monkeypatch):
        from orvima import agent

        built: dict = {}

        class Recorder:
            def __init__(self, **kwargs):
                built.update(kwargs)

            def start(self):
                built["started"] = True

        monkeypatch.setattr("orvima.browser.BrowserController", Recorder)
        agent._make_browser("real", "https://example.org/start")
        assert built.get("base_url") == "https://example.org/start", (
            f"real mode ignored the requested URL and started at {built.get('base_url')!r}"
        )
        assert built.get("started") is True, "the browser was built but never started"

    def test_the_env_var_is_still_a_fallback(self, monkeypatch):
        from orvima import agent

        built: dict = {}

        class Recorder:
            def __init__(self, **kwargs):
                built.update(kwargs)

            def start(self):
                pass

        monkeypatch.setattr("orvima.browser.BrowserController", Recorder)
        monkeypatch.setenv("ORVIMA_START_URL", "https://from-env.example")
        agent._make_browser("real", "")
        assert built.get("base_url") == "https://from-env.example", built

        agent._make_browser("real", "https://explicit.example")
        assert built.get("base_url") == "https://explicit.example", (
            "the caller's own URL must beat the environment"
        )

    def test_demo_mode_does_not_consult_any_url(self, monkeypatch):
        from orvima import agent

        class Exploding:
            def __init__(self, **kwargs):
                raise AssertionError("demo mode must not build a real browser")

        monkeypatch.setattr("orvima.browser.BrowserController", Exploding)
        browser = agent._make_browser("demo")
        assert type(browser).__name__ == "DemoBrowser"
