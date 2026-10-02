"""Clauses the probe carries that Chromium will not let a test reach.

Two mutations survived the last harness run. Both are the same shape of thing, and
neither is a gap in the tests in the usual sense - they are clauses that this
browser makes unreachable. They are pinned here so they are not silently dropped,
with the reason recorded so nobody later "cleans them up" as dead code.

1. `pointer-events: none`

   Measured: Chrome omits such elements from `elementsFromPoint` altogether, so
   the walk never encounters one. An earlier version of this file asserted that
   the overlay was topmost, and that assertion failed - which is how it was
   learned. The filter is still correct and still needed for other engines, where
   the behaviour differs, so it stays.

2. The ancestor clause, `!node.contains(el)`

   Measured across four wrappings - plain, wrapper z-index 5 with child auto,
   wrapper 5 with child 1, wrapper 1 with child 5 - an ancestor never appears
   above its own child in the stack. Chromium paints a container beneath its
   content regardless of z-index. So the clause cannot be exercised here either.

And one clause that is deliberately *absent*: there is no z-index arithmetic.
An earlier version filtered blockers with `Number(style.zIndex) <= elZ`, which
looked like a safeguard but was inert - `z-index: auto` parses to `NaN` and every
comparison against `NaN` is false, so it never fired for the `z-index: auto` that
most elements carry. That inert filter was one of the two defects that made orvima
refuse Google's sign-in field. Reinstating it cannot be a meaningful mutation,
because on the corrected code it would only ever run against nodes already known
to be painted above the target, where comparing z-indices adds a way to be wrong
and removes none.
"""

from __future__ import annotations

import inspect
import re

import pytest

import orvima.occlusion as mod
from orvima.occlusion import uncover


def _js_code(script: str) -> str:
    """The script with comments removed.

    Several assertions below are about code that must not exist. Run against the
    raw string they trip over the explanatory comments instead - the probe
    documents *why* it avoids z-index, so the word appears in the source twice
    over, and an assertion that cannot tell prose from code is measuring the
    wrong thing.

    String literals are left intact, because the other assertions here match on
    them (`pointerEvents === 'none'`).
    """
    script = re.sub(r"/\*.*?\*/", " ", script, flags=re.S)
    return re.sub(r"//[^\n]*", " ", script)


class TestClausesChromiumWillNotLetUsReach:
    def test_pointer_events_is_filtered(self):
        """Correct for other engines; unexercised in this one.

        A source assertion rather than a behavioural one, because the behaviour
        cannot be produced here. It is worth keeping precisely because it looks
        removable: `elementsFromPoint` never yields such a node in Chromium, so
        the next person to read this has no way to tell a deliberate
        cross-browser guard from leftover code.
        """
        js = mod._UNCOVER_JS
        assert "pointerEvents" in js, (
            "the pointer-events filter is gone. It cannot be exercised in "
            "Chromium, so its absence is silent."
        )
        match = re.search(r"pointerEvents\s*===\s*'none'\s*\)\s*return null", js)
        assert match, (
            "pointer-events is referenced but no longer short-circuits the node. "
            "A 'transparent to input' overlay blocks nothing and must be seen "
            "through rather than recorded."
        )

    def test_the_pointer_filter_skips_rather_than_stops_the_walk(self):
        """Skipping is the whole point.

        Returning early would abandon the point, leaving it unexamined - and the
        target might be under a real overlay further down the stack.
        """
        js = mod._UNCOVER_JS
        assert re.search(
            r"if \(cs\.pointerEvents === 'none'\) return null;.*?"
            r"if \(!info\) continue;",
            js,
            re.S,
        ), (
            "a pointer-transparent node must be skipped so the walk continues to "
            "what is beneath it, not recorded as an obstacle"
        )

    def test_an_ancestor_is_never_treated_as_a_scrollable_overlay(self):
        """Defensive: measured unreachable in Chromium, kept anyway.

        If an ancestor ever did appear above its own child, calling it `pinned`
        would make the probe try to scroll the page to escape it, which is
        meaningless - the two move together.
        """
        js = mod._UNCOVER_JS
        assert re.search(r"!node\.contains\(el\)", js), (
            "the ancestor clause is gone. It cannot be exercised in Chromium, so "
            "nothing else would notice its removal."
        )

    def test_there_is_no_z_index_arithmetic_left(self):
        """The NaN defect's real fix: the comparison is not there at all.

        `Number('auto')` is `NaN`, and `NaN <= anything` is false, so a guard
        written that way never fires. Asserting the absence of the arithmetic is
        the only form that holds: any z-index comparison reintroduces the class of
        bug, whether or not this particular spelling is inert.

        Scoped to `zIndex`, not to `Number(` in general. `z-index` is the one
        computed style that can be the keyword `auto`; `opacity` and the rest are
        always numeric strings, so `Number()` on them is sound. A blanket ban on
        numeric parsing would be a test written for tidiness rather than
        correctness, and would fail on code that is right.
        """
        code = _js_code(mod._UNCOVER_JS)
        assert "zIndex" not in code, (
            "the probe compares z-index again. It cannot be right: 'auto' parses "
            "to NaN, no comparison against NaN is true, and the filter silently "
            "does nothing - which is what made Google refuse to sign in."
        )
        assert "z-index" not in code, (
            "a z-index comparison came back, spelled as a CSS string literal"
        )

    def test_the_remaining_numeric_parses_are_sound(self):
        """`Number()` survives only where computed style cannot return a keyword.

        Keeps the previous test from being satisfied by deleting a legitimate
        parse instead of the broken one.
        """
        js = mod._UNCOVER_JS
        parses = set(re.findall(r"Number\(\s*([a-zA-Z.]+)\s*\)", js))
        assert parses <= {"cs.opacity"}, (
            f"unexpected numeric parses: {parses - {'cs.opacity'}}. Any property "
            "that can be a keyword ('auto', 'inherit', 'none') must not be "
            "compared numerically - the comparison silently never fires."
        )


class TestUncoverStillOnlyMeasures:
    """Unchanged from the safety boundary, restated so it stays true.

    The hit-test rewrite was substantial. These are the properties that must
    survive it: the module moves the page and reports, and never acts.
    """

    def test_uncover_calls_no_page_actions(self):
        source = inspect.getsource(uncover)
        for forbidden in (".click(", ".fill(", ".type(", ".press(", ".tap(", ".check("):
            assert forbidden not in source

    def test_the_js_dispatches_no_input_events(self):
        js = mod._UNCOVER_JS
        for forbidden in (".click()", "dispatchEvent", "MouseEvent", "KeyboardEvent", ".submit("):
            assert forbidden not in js, f"the in-page script contains {forbidden!r}"

    def test_the_walk_still_stops_at_the_target(self):
        """The fix for the Google false positive, pinned at the source.

        Scanning past the target treats anything overlapping in *any* direction
        as an obstacle. On Google's outlined text field that turned two border
        divs painted underneath the input into a wall, and orvima refused to
        type an email address. The behavioural test is
        `test_an_outlined_field_is_reachable`; this is here because the bug is
        one character of control flow and easy to reintroduce innocently.
        """
        assert re.search(
            r"if \(node === el \|\| el\.contains\(node\)\) break;", mod._UNCOVER_JS
        ), (
            "the walk no longer stops at the target. Elements painted below it "
            "will be reported as occluding it again."
        )

    @pytest.mark.parametrize("needle", ["elementsFromPoint", "getComputedStyle"])
    def test_the_probe_uses_the_browser_hit_test(self, needle):
        assert needle in mod._UNCOVER_JS
