"""The navigation contract, enforced on every backend rather than one.

`expect_url` / `expect_text` were implemented once, on BrowserController, and
left as an unconditional `verified: True` on the other two navigation backends.
The tool layer forwards the expectation to whichever backend it was given, so on
those two an explicit "I expect to land on the dashboard" was accepted and
discarded, and the call reported success.

That is the worst shape a verification bug can take, because the harness that
measures the agent (`orvima.bench`, driven through BenchSite) is itself one of
the backends that cannot tell the truth. A harness whose every navigation
reports success cannot be used to detect a navigation that did not succeed, so
its passing score is not evidence about this.

These tests are written against `tools.tool_browse_navigate` - the layer a
caller actually reads - and against every backend that can navigate.

Run: pytest tests/test_navigation_contract.py -q
"""

from __future__ import annotations

import inspect

import pytest

from orvima.backend import NavigationBackend, _landed_on
from orvima.bench_site import BenchSite
from orvima.browser import BrowserController
from orvima.demo import DemoBrowser
from orvima.tools import tool_browse_click, tool_browse_navigate

#: A substring of no page any of these backends can serve. Used to state an
#: expectation that is false wherever the backend ends up, so a backend that
#: folds an unknown url back to somewhere else still has to fail: the caller
#: asked for an outcome and did not get it.
WRONG = "checkout-payment-intent"


def _reachable(factory) -> str:
    """A url this backend can actually be on afterwards."""
    if factory is BenchSite:
        return "https://bench.test/list"
    return "https://acme.dev/products"


@pytest.fixture(params=[BenchSite, DemoBrowser], ids=["bench", "demo"])
def backend(request):
    return request.param()


@pytest.fixture
def target(backend):
    return _reachable(type(backend))


class TestAnUnmetExpectationIsNotSuccess:
    """The direction that matters: a wrong outcome must not read as success."""

    def test_navigating_where_the_caller_did_not_intend_fails(self, backend, target):
        result = tool_browse_navigate(
            backend, target, expect_url=WRONG, expect_timeout_ms=200
        )
        assert not result.get("ok"), (
            f"{type(backend).__name__} accepted a navigation somewhere the "
            f"caller said they did not want, and reported success: {result}"
        )

    def test_the_failure_names_the_mismatch(self, backend, target):
        """The report has to say what was wanted and what turned out instead.

        A bare `ok: false` leaves a caller with nothing to act on, and a message
        naming an internal class is worse than useless.
        """
        result = tool_browse_navigate(
            backend, target, expect_url=WRONG, expect_timeout_ms=200
        )
        error = result.get("error", "")
        assert "expected url to contain" in error, (
            f"{type(backend).__name__} failed without naming the mismatch: {error!r}"
        )
        assert WRONG in error
        assert "Traceback" not in error

    def test_it_never_claims_verified_while_failing(self, backend, target):
        """A failing call must not also carry `verified: true`."""
        result = tool_browse_navigate(
            backend, target, expect_url=WRONG, expect_timeout_ms=200
        )
        assert result.get("verified") is not True, (
            f"{type(backend).__name__} reported an unmet expectation and "
            f"verified the navigation anyway: {result}"
        )


class TestTheOrdinaryPathIsUnchanged:
    """Additive. A caller who states nothing must see exactly today's shape."""

    def test_navigating_without_expectations_succeeds(self, backend, target):
        result = tool_browse_navigate(backend, target)
        assert result.get("ok"), result

    def test_no_expectation_keys_appear_when_none_were_asked_for(self, backend, target):
        result = tool_browse_navigate(backend, target)
        assert "expectationsMet" not in result, (
            f"{type(backend).__name__} grew result keys for a caller that used none"
        )

    def test_an_expectation_that_does_hold_passes(self, backend, target):
        result = tool_browse_navigate(
            backend, target, expect_url=target, expect_timeout_ms=200
        )
        assert result.get("ok"), result
        assert result.get("expectationsMet") is True
        assert result["checks"][0]["ok"] is True


class TestARedirectIsNotVerified:
    """`verified` has to mean we arrived, or it is decoration.

    `_landed_on` exists for one case: the browser went somewhere else. A
    redirect to a sign-in page keeps the call green, keeps the DOM signature
    changed, and leaves the agent on a page it did not ask for - which is how
    an action runs against the wrong account without anything reporting a
    problem.

    This is stated against a backend that redirects, because on the shipped
    backends a redirect cannot be produced without a real network. What is
    being tested is the judgement, and it is the judgement that was wrong.
    """

    @pytest.fixture
    def redirecting(self):
        class RedirectingBackend(NavigationBackend):
            """Lands on a sign-in page whatever was asked for, as a real site does."""

            def __init__(self):
                self.url = "https://shop.test/sign-in"
                self.asked = None

            def _perform_navigate(self, url):
                self.asked = url
                self.url = "https://shop.test/sign-in"

            def _state(self):
                return {"url": self.url, "title": "Sign in"}

            def _read_page_state(self):
                return {"url": self.url, "text": "Sign in to your account"}

        return RedirectingBackend()

    def test_a_redirect_is_not_verified(self, redirecting):
        result = redirecting.navigate("https://shop.test/checkout")
        assert result["url"] == "https://shop.test/sign-in"
        assert result["verified"] is False, (
            "a navigation that landed on the sign-in page reported itself "
            f"verified: {result}"
        )

    def test_a_redirect_still_succeeds_when_no_expectation_was_stated(self, redirecting):
        """It is a real navigation, so it is not an error - just not verified.

        Failing here would break every caller on any site that redirects, which
        is most of them. The honesty has to come from `verified`, not from
        refusing to navigate.
        """
        result = redirecting.navigate("https://shop.test/checkout")
        assert result["url"] == redirecting.asked.replace("/checkout", "/sign-in")

    def test_the_trailing_slash_and_query_are_not_a_different_page(self):
        """Only host and path decide. A site that reorders a query string has
        not gone somewhere else, and treating it as a failure would make
        verification noise people learn to ignore."""
        assert _landed_on("https://shop.test/a?x=1", "https://shop.test/a?x=2")
        assert _landed_on("https://shop.test/a/", "https://shop.test/a")
        assert _landed_on("https://shop.test/a", "https://shop.test/a#top")

    def test_a_different_account_is_a_different_page(self):
        assert not _landed_on("https://shop.test/orders", "https://shop.test/sign-in")
        assert not _landed_on("https://shop.test/a", "https://other.test/a")


class TestCountExpectationsAreAnswerable:
    """`expect_count` is the expectation for lists, and it needs a real count.

    Both in-memory backends report "unreadable" for a selector that matches
    nothing. That is the honest answer and it must fail the expectation - a
    backend that reported 0 instead would let `expect_count=0` pass on a
    selector that does not exist, which verifies nothing.
    """

    def test_a_count_that_holds_passes(self, backend, target):
        browser = type(backend)()
        tool_browse_navigate(browser, target)
        result = tool_browse_click(
            browser, selector=_countable(backend), expect_count=1
        )
        assert result.get("ok"), result
        assert result["checks"][0]["kind"] == "count"
        assert result["checks"][0]["seen"] == 1

    def test_a_wrong_count_fails(self, backend, target):
        browser = type(backend)()
        tool_browse_navigate(browser, target)
        result = tool_browse_click(
            browser, selector=_countable(backend), expect_count=99
        )
        assert not result.get("ok"), (
            f"{type(backend).__name__} passed a count of 99: {result}"
        )
        assert "expected 99 matching element(s)" in result.get("error", "")

    def test_a_selector_that_matches_nothing_is_unreadable_not_zero(self, backend):
        """The distinction that stops a broken expectation passing.

        `expect_count=0` on a selector that does not exist looks like a pass if
        unreadable is reported as zero. It is not a pass; the count was never
        taken.
        """
        count = backend._count_matching("#no-such-element-anywhere")
        assert count is None, (
            f"{type(backend).__name__} reported {count!r} for a selector that "
            "matches nothing; an unreadable count must be None so it cannot "
            "satisfy expect_count=0"
        )


def _countable(backend) -> str:
    """A selector naming one element that is present after `_reachable`."""
    if isinstance(backend, BenchSite):
        return "#title"
    return "Bolt"


class TestTextExpectationsAreAnswerable:
    """`expect_text` has to be checkable wherever a url expectation is.

    A backend with no page content cannot answer an `expect_text`, and before
    these readers existed it reported success anyway. The failure has to be the
    honest one - a mismatch - not an incident.
    """

    def test_page_text_is_readable_on_every_backend(self, backend):
        state = backend._read_page_state()
        assert "url" in state
        assert isinstance(state.get("text"), str), (
            f"{type(backend).__name__} returned no text, so expect_text is "
            f"unanswerable here: {state!r}"
        )

    def test_text_that_the_page_shows_passes(self, backend, target):
        browser = type(backend)()
        tool_browse_navigate(browser, target)
        shown = browser._read_page_state()["text"]
        result = tool_browse_navigate(
            browser, target, expect_text=shown.strip()[:20], expect_timeout_ms=200
        )
        assert result.get("ok"), result
        assert result["checks"][0]["seen"] == "present"

    def test_text_the_page_does_not_show_fails(self, backend, target):
        browser = type(backend)()
        result = tool_browse_navigate(
            browser,
            target,
            expect_text="Order confirmed for order 99887766",
            expect_timeout_ms=200,
        )
        assert not result.get("ok"), (
            f"{type(backend).__name__} accepted text that is not on the page: {result}"
        )
        assert "expected the page to show" in result.get("error", "")


class TestTheContractCannotBeReimplemented:
    """A structural guard, so the next backend cannot quietly stub it.

    The fix for a contract implemented once and stubbed twice is to implement it
    once, in a base class, where a backend supplies only the primitives. That
    only holds if overriding the finished method is itself detectable -
    otherwise the next backend reintroduces the same bug and the tests above
    have to catch it by hand again.
    """

    def test_no_backend_overrides_the_implemented_navigate(self):
        for factory in (BenchSite, DemoBrowser):
            assert factory.navigate is NavigationBackend.navigate, (
                f"{factory.__name__} defines its own navigate, so it owns the "
                "expectation contract again and can drop it again"
            )

    @pytest.mark.parametrize(
        "method", ["navigate", "click", "_check_expectations"]
    )
    def test_no_backend_overrides_a_shared_method(self, method):
        """The same rule for every method the base owns, not just navigate.

        `click` was stubbed on both in-memory backends for the same reason
        navigate was, and a guard that only watched navigate would have let it
        through.
        """
        defining = [
            cls.__name__
            for cls in NavigationBackend.__subclasses__()
            if method in vars(cls)
        ]
        assert not defining, (
            f"backends override {method} directly: {defining}. Implement the "
            f"_perform_ primitive instead."
        )

    def test_every_backend_implements_the_primitives_the_base_calls(self):
        """A primitive left as NotImplementedError is a crash at call time.

        Better caught by an assertion than by whoever first navigates.
        """
        for factory in (BenchSite, DemoBrowser, BrowserController):
            for primitive in ("_perform_navigate", "_perform_click",
                              "_read_page_state", "_count_matching"):
                own = getattr(factory, primitive, None)
                assert own is not getattr(NavigationBackend, primitive), (
                    f"{factory.__name__} does not implement {primitive}"
                )

    def test_every_navigating_backend_inherits_the_contract(self):
        """A backend that does not inherit cannot answer an expectation at all."""
        from orvima.browser import BrowserController

        for factory in (BenchSite, DemoBrowser, BrowserController):
            assert issubclass(factory, NavigationBackend), (
                f"{factory.__name__} can navigate but does not implement the "
                "navigation contract"
            )

    def test_the_check_is_not_hardcoded_true_anywhere_in_the_contract(self):
        """The base must derive `verified`, not assert it.

        `"verified": True` as a literal is what both backends did wrong. Stated
        as a check so the literal cannot come back in the shared code either.
        """
        from orvima.backend import NavigationBackend

        assert '"verified": True' not in inspect.getsource(NavigationBackend)
