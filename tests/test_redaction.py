"""Redaction: what must be hidden, and what must not.

The function this covers had no direct test at all, despite being the thing that
decides whether a user's password reaches an LLM. It also matched substrings, so
it was wrong in both directions at once:

  destroyed ordinary page content - author, keyword, keynote, monkey and
  authorship all contain "auth" or "key", so a planner reading a blog post saw
  the author replaced by ***REDACTED***
  missed "bearer", a real credential name, because no entry was "bearer"

Both classes are pinned below, because the fix is a plausible-looking change
someone could "simplify" back into substring matching, and the failure is silent
in exactly the way that matters: over-redaction looks like it worked.

Run: pytest tests/test_redaction.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from orvima.agent import _is_sensitive_key, _key_tokens, _redact_sensitive  # noqa: E402

REDACTED = "***REDACTED***"


class TestRealSecretsAreRedacted:
    def test_the_obvious_ones(self):
        data = {
            "password": "hunter2",
            "passwd": "hunter2",
            "secret": "s3cr3t",
            "token": "abc123",
            "authorization": "Bearer abc",
            "ssn": "123-45-6789",
            "cvv": "123",
            "credit_card": "4111111111111111",
        }
        out = _redact_sensitive(data)
        for key in data:
            assert out[key] == REDACTED, f"{key} was not redacted"

    def test_compound_and_camel_case_names(self):
        data = {
            "api_key": "sk-live-1",
            "apiKey": "sk-live-2",
            "accessToken": "t3",
            "client_secret": "s",
            "refreshToken": "t4",
            "sessionId": "sess",
            "privateKey": "pk",
            "creditCardNumber": "4111",
            "userPassword": "p",
            "x-api-key": "sk-header",
        }
        out = _redact_sensitive(data)
        for key in data:
            assert out[key] == REDACTED, f"{key} was not redacted"

    def test_bearer_is_caught_though_it_never_was(self):
        """A real credential name the substring list omitted entirely."""
        assert _redact_sensitive({"bearer": "xyz"})["bearer"] == REDACTED

    def test_csrf_and_cookie(self):
        data = {"csrf_token": "c", "XSRF-TOKEN": "x", "Cookie": "session=abc"}
        out = _redact_sensitive(data)
        assert all(v == REDACTED for v in out.values()), out

    def test_nested_structures_are_walked(self):
        data = {"form": {"fields": [{"name": "login", "password": "hunter2"}]}}
        out = _redact_sensitive(data)
        assert out["form"]["fields"][0]["password"] == REDACTED

    def test_a_nested_list_of_dicts(self):
        out = _redact_sensitive({"items": [{"token": "t"}, {"name": "ok"}]})
        assert out["items"][0]["token"] == REDACTED
        assert out["items"][1]["name"] == "ok", "a non-secret sibling was touched"

    def test_a_secret_under_an_innocuous_key_is_a_stated_limitation(self):
        """This redactor works on key names, not values.

        ``{"value": "hunter2"}`` is not caught, and cannot be: "value" carries no
        signal, and redacting every string under a common key would destroy the
        page content the agent needs.

        The real exposure is handled at the source instead - the outline marks a
        password input's value as "***" before it ever reaches here - and this
        test exists so the limit is written down rather than discovered. Any
        future caller that puts user secrets under neutral keys needs value-aware
        redaction, not a wider key list.
        """
        out = _redact_sensitive({"value": "hunter2"})
        assert out["value"] == "hunter2"  # documented, not endorsed


class TestOrdinaryContentSurvives:
    """The over-redaction half, which is just as much a bug.

    Losing the author of a page the agent is reading is a capability loss, not a
    safety win, and it is invisible unless something checks for it.
    """

    def test_words_that_merely_contain_a_sensitive_word(self):
        data = {
            "author": "Grace Hopper",
            "authorship": "me",
            "keyword": "python",
            "keynote": "slides",
            "monkey": "banana",
            "authenticated": "yes",
            "tooltip": "help",
            "bookshelf": "study",
        }
        out = _redact_sensitive(data)
        for key, value in data.items():
            assert out[key] == value, f"{key} was wrongly redacted"

    def test_page_content_fields_a_planner_needs(self):
        data = {
            "title": "Sign in to your account",
            "text": "Enter your password to continue",
            "label": "Password",
            "body": "Forgot your password? Reset it here.",
            "url": "https://example.test/login?session=x",
        }
        out = _redact_sensitive(data)
        for key, value in data.items():
            assert out[key] == value, (
                f"{key} was redacted, so the planner cannot read the page it is "
                "acting on"
            )

    def test_a_count_under_a_sensitive_name_is_not_a_secret(self):
        """token_count is 42. Redacting it destroys information for nothing."""
        assert _redact_sensitive({"token_count": 42})["token_count"] == 42
        assert _redact_sensitive({"auth": True})["auth"] is True
        assert _redact_sensitive({"session": 0})["session"] == 0

    def test_a_string_still_counts_as_a_secret_under_those_names(self):
        """The numeric exemption must not become a hole."""
        assert _redact_sensitive({"token_count": "abc"})["token_count"] == REDACTED


class TestTokenization:
    def test_separators_and_camel_case_both_split(self):
        assert _key_tokens("api_key") == ["api", "key"]
        assert _key_tokens("apiKey") == ["api", "key"]
        assert _key_tokens("x-api-key") == ["x", "api", "key"]
        assert _key_tokens("XSRF-TOKEN") == ["xsrf", "token"]

    def test_consecutive_capitals_stay_together(self):
        """xsrf/CSRF are acronyms, not camelCase runs."""
        assert _key_tokens("APIKEY") == ["apikey"]
        assert _key_tokens("CSRFToken") == ["csrf", "token"]

    def test_digits_are_their_own_token(self):
        assert _key_tokens("key2") == ["key", "2"]


class TestThePredicateItself:
    def test_it_is_the_seam_that_matters(self):
        """Pin the decision separately from the walk, so a future refactor of
        the recursion cannot quietly change the rule."""
        assert _is_sensitive_key("password", "x")
        assert _is_sensitive_key("api_key", "x")
        assert not _is_sensitive_key("author", "x")
        assert not _is_sensitive_key("monkey", "x")

    def test_a_non_dict_passes_through_untouched(self):
        assert _redact_sensitive("not a dict") == "not a dict"
        assert _redact_sensitive(None) is None
