"""The website must be checkable, not just true today.

orvima.in is served straight from `docs/`, so nothing in the build pipeline
validates it. A marketing page is exactly where a number drifts away from the
code it describes, because editing prose is easy and re-measuring is not. This
file makes the site falsifiable:

1. **The tool count cannot drift.** Every ``browse_*`` name on the page must
   exist in `orvima.tools.TOOLS`, and the counts the page states must equal the
   real release count and the real `main` count. The page used to say 21, which
   was neither.
2. **The transcript cannot be hand-written.** The page ships no run output of
   its own; it renders `transcript.json`, and that file is checked against a
   fresh real run. A marketing page whose sample output was invented is the
   exact claim this project exists to disprove, so it is worth a test.
3. **The stylesheet cannot silently collide.** Two rules using the same class
   name for different things once applied ``white-space: nowrap`` to the whole
   gate list, which pushed the document 700px sideways. A duplicate selector is
   now a failure.
4. **The rendered page is the thing being tested.** Layout, tap targets and
   console errors are checked in a real browser, because a source grep cannot
   tell whether text wrapped.
5. **The docs page cannot drift.** docs.html is a build artifact sharing this
   stylesheet, so it is diffed against its generator, its classes are checked
   against the CSS, and its sections are rendered to prove they kept their box.

Run: pytest tests/test_site_docs.py -q
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from orvima.tools import TOOLS

REPO = pathlib.Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
INDEX = DOCS / "index.html"
CSS = DOCS / "style.css"
MAIN_JS = DOCS / "main.js"
TRANSCRIPT = DOCS / "transcript.json"

RELEASE_TAG = "v0.1.5"


def tool_names() -> set[str]:
    """The names in `tools.TOOLS`.

    `TOOLS` is a tuple of functions named `tool_browse_*`, not dicts, and
    `\bbrowse_` cannot match inside `tool_browse_` because `_` is a word
    character. Both mistakes silently produce an empty set, which then looks
    like "the page invented everything".
    """
    out = set()
    for fn in TOOLS:
        name = getattr(fn, "__name__", "")
        if name.startswith("tool_"):
            name = name[len("tool_") :]
        out.add(name)
    assert len(out) == len(TOOLS), "two tools share a name"
    return out


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css() -> str:
    return CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def transcript() -> dict:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))


def _shipped_tools() -> set[str]:
    """The tool names in the release the install command actually pulls."""
    try:
        blob = subprocess.run(
            ["git", "show", f"{RELEASE_TAG}:src/orvima/tools.py"],
            cwd=REPO, capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip(f"cannot read {RELEASE_TAG} from git")
    # No leading \b: the names appear as `tool_browse_click`, and `_` is a word
    # character so there is no boundary between `tool_` and `browse_`.
    return {m.removeprefix("tool_") for m in re.findall(r"browse_[a-z_]+", blob)}


# --------------------------------------------------------------------------
# 1. the numbers on the page
# --------------------------------------------------------------------------


class TestTheToolCountIsNotALie:
    def test_every_tool_named_on_the_page_exists(self, html: str) -> None:
        named = set(re.findall(r"browse_[a-z_]+", html))
        assert named, "the page should name its tools at all"
        invented = named - tool_names()
        assert not invented, f"page advertises tools that do not exist: {sorted(invented)}"

    def test_the_chip_list_is_exactly_the_shipped_release(self, html: str) -> None:
        """The chips are the visitor's install, so they are the release's set."""
        block = re.search(r'<div class="chips">(.*?)</div>', html, re.S)
        assert block, "the tool chip list is missing from the page"
        chips = set(re.findall(r"<span>(browse_[a-z_]+)</span>", block.group(1)))
        shipped = _shipped_tools()
        assert chips, "the chip list is empty"
        assert chips == shipped, (
            f"chips claim {len(chips)} tools, the release has {len(shipped)}; "
            f"only in chips: {sorted(chips - shipped)}, missing: {sorted(shipped - chips)}"
        )

    def test_the_two_stated_counts_are_the_real_ones(self, html: str) -> None:
        shipped = len(_shipped_tools())
        on_main = len(tool_names())
        # The page states the release count and the main count, and must not
        # state a third number anywhere as a tool count.
        for claimed in (shipped, on_main):
            assert re.search(rf"\b{claimed}\b", html), f"page never states the real count {claimed}"
        stated = {int(n) for n in re.findall(r"(\d+)\s+(?:<code>browse_\*</code>\s+)?tools\b", html)}
        stated |= {int(n) for n in re.findall(r"ahead at (\d+)", html)}
        allowed = {shipped, on_main}
        assert stated <= allowed, (
            f"page states tool counts {sorted(stated)} but the real ones are {sorted(allowed)}"
        )

    def test_unreleased_tools_are_labelled_as_such(self, html: str) -> None:
        """A tool on `main` but not in the release must not read as installed."""
        shipped = _shipped_tools()
        for name in sorted(tool_names() - shipped):
            idx = html.find(name)
            if idx == -1:
                continue
            window = html[max(0, idx - 700) : idx + 700]
            assert (
                "main" in window or "next release" in window or "ship in" in window
            ), f"{name} is on the page with no note that it is not in the install"

    def test_the_stats_match_a_measurement_not_a_memory(self, html: str) -> None:
        # Counted from disk, not from `git ls-files`: this file is one of them,
        # and a tracked-only count would make the assertion wrong by construction.
        test_files = sorted((REPO / "tests").glob("test_*.py"))
        assert re.search(rf"\b{len(test_files)}\s+files\b", html), (
            f"page should state the real test-file count ({len(test_files)})"
        )
        source = list((REPO / "src" / "orvima").glob("*.py"))
        total = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in source)
        # `</b><span>` sits between the number and its label, so allow a short
        # run of markup rather than requiring literal whitespace.
        assert re.search(rf"\b{total / 1000:.1f}k\b.{{0,40}}?lines of source", html), (
            f"page should state the real source line count ({total}, i.e. {total / 1000:.1f}k)"
        )
        # The test count is the number easiest to let drift, because nothing
        # else on the page depends on it. Collected, not estimated: `addopts`
        # supplies the first `-q`, the command adds the second, and double-quiet
        # collect prints one `file: count` line per test file.
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=300,
        )
        counts = [
            int(n)
            for n in re.findall(r"^tests[/\\]\S+\.py: (\d+)$", proc.stdout, flags=re.M)
        ]
        assert counts, (
            "collection printed no per-file counts, so the page's test number "
            f"cannot be checked at all (exit {proc.returncode})"
        )
        collected = sum(counts)
        assert re.search(rf"<b>{collected}</b><span>tests,", html), (
            f"page should state the real test count ({collected})"
        )


# --------------------------------------------------------------------------
# 2. the transcript is captured, not composed
# --------------------------------------------------------------------------


class TestTheTranscriptIsCapturedNotComposed:
    def test_the_page_ships_no_run_output_of_its_own(self, html: str) -> None:
        """Any `step N: browse_` text in the HTML would be a hand-typed run."""
        assert not re.search(r"step \d+:\s*browse_", html), (
            "the page contains literal run output; it must be rendered from transcript.json"
        )

    def test_the_transcript_is_fetched_not_inlined(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        assert "transcript.json" in source, "main.js does not read transcript.json"
        assert re.search(r"fetch\(\s*['\"]transcript\.json", source), (
            "main.js must fetch transcript.json rather than embed it"
        )

    def test_a_failed_fetch_says_so_instead_of_faking_it(self) -> None:
        """No fallback sample. Silence is honest; a plausible fake is not."""
        source = MAIN_JS.read_text(encoding="utf-8")
        assert "transcript unavailable" in source, (
            "a failed transcript fetch must render an explicit error"
        )
        assert not re.search(r"const\s+SAMPLE|fallbackTranscript|FAKE_TRANSCRIPT", source), (
            "main.js must not carry a hand-written sample transcript"
        )

    def test_every_goal_on_the_page_comes_from_the_capture(self, html: str, transcript: dict) -> None:
        goals = {entry["goal"] for entry in transcript["goals"].values()}
        goals.add(transcript["gate"]["goal"])
        shown = set(re.findall(r'<span class="goal">([^<]+)</span>', html))
        assert shown == goals, f"page goals {sorted(shown)} != captured {sorted(goals)}"

    def test_the_capture_is_still_what_orvima_actually_does(self, transcript: dict) -> None:
        """Re-run the happy path and require the same shape of result.

        This is the load-bearing check. If a change to the agent loop alters the
        steps or breaks the run, the published transcript is stale and this
        fails rather than letting the site keep quoting old output.
        """
        entry = transcript["goals"]["happy"]
        env = {**os.environ, "ORVIMA_SENTINEL": "off"}
        proc = subprocess.run(
            [sys.executable, "-m", "orvima.cli", "run", "--mode", "demo",
             "--max-steps", "20", entry["goal"]],
            cwd=REPO, capture_output=True, text=True, env=env, timeout=300,
        )
        assert proc.returncode == 0, f"demo run failed: {proc.stderr[-400:]}"
        end = proc.stdout.find("\ntranscript:")
        assert end > 0, "demo run printed no transcript"
        fresh = json.loads(proc.stdout[:end])
        assert fresh["ok"] is True
        assert fresh["steps"] == entry["result"]["steps"], (
            f"published transcript says {entry['result']['steps']} steps, "
            f"a fresh run does {fresh['steps']}"
        )
        published = entry["transcript"]
        for call in re.findall(r"step \d+: (browse_\w+)", published):
            assert call in proc.stdout[end:], f"published step {call} no longer happens"

    def test_the_destructive_click_really_was_held(self, transcript: dict) -> None:
        """The site's best asset is a real refusal. Assert it is still refused.

        This is the check that should have existed before the page shipped a
        caption reading "held for a human" on top of a transcript that contained
        no hold at all.
        """
        gate = transcript["gate"]
        assert gate["goal"] == "delete everything in my account"
        assert gate["allowed"] is False, (
            "the capture now allows the delete click; the page says it was stopped"
        )
        assert gate["risk"], "a refusal must name the risk that caused it"
        assert "allowed=False" in gate["transcript"]
        assert "Delete everything" in gate["transcript"]
        # With sentinel available, the gate queues a pending approval for a human
        if gate.get("degraded"):
            assert not gate.get("pending"), "degraded gate should not queue approvals"
        else:
            assert gate.get("pending"), "no approval was actually queued"
            card = gate["pending"][0]
            assert card["risk"] == gate["risk"], "the human would see a different risk than the transcript states"
            assert card["reason"] == gate["reason"], "the human would see a different reason"

    def test_the_gate_capture_is_reproducible(self, transcript: dict) -> None:
        """Re-run the real gate and require the same refusal.

        If a change to the policy stops refusing this selector, the published
        claim is wrong and this fails rather than letting the page keep it.
        """
        import os

        gate = transcript["gate"]
        env = {**os.environ, "ORVIMA_SENTINEL": "on"}
        code = (
            "import json,sys\n"
            f"sys.path.insert(0, {str(REPO / 'src')!r})\n"
            "from orvima.sentinel_gate import make_gate\n"
            "g = make_gate()\n"
            f"r = g.check('browse_click', {gate['args']!r}, session_id='t')\n"
            "print(json.dumps({'allowed': r.allowed, 'risk': r.risk, 'reason': r.reason}))\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                              capture_output=True, text=True, env=env, timeout=180)
        assert proc.returncode == 0, f"gate probe failed: {proc.stderr[-400:]}"
        fresh = json.loads(proc.stdout)
        assert fresh["allowed"] is False, f"a fresh gate now allows it: {fresh}"
        assert fresh["risk"] == gate["risk"], (
            f"published risk {gate['risk']!r}, a fresh gate says {fresh['risk']!r}"
        )





# --------------------------------------------------------------------------
# 3. the stylesheet
# --------------------------------------------------------------------------


def css_rules(css: str) -> dict[tuple[str, str], set[str]]:
    """Map (at-rule context, exact selector) -> the bodies seen for it.

    Two details matter, and getting either wrong makes the check useless.
    Pseudo-classes are kept, because `.btn` and `.btn:hover` are the same
    class on purpose. Media queries are part of the key, because `.hero` at
    the top level and `.hero` inside `max-width: 620px` are a deliberate
    override rather than a collision. Module-level because the docs-page
    checks below read this same stylesheet.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found: dict[tuple[str, str], set[str]] = {}

    def walk(text: str, ctx: str) -> None:
        while text:
            # A newline between two rules is not an error: after any block
            # the remainder starts with whitespace, and a comment strips to
            # whitespace too. Without this lstrip, `re.match` fails on the
            # leading newline before an @media block, the walk stops there,
            # and every rule after the block silently escapes the checks --
            # which is exactly how the duplicate-rule pile-up in this
            # stylesheet went unnoticed.
            text = text.lstrip()
            if not text:
                break
            at = re.match(r"@([\w-]+)([^{]*)\{", text)
            if at:
                name, cond, rest = at.group(1), at.group(2).strip(), text[at.end():]
                depth, i = 1, 0
                while i < len(rest) and depth:
                    if rest[i] == "{":
                        depth += 1
                    elif rest[i] == "}":
                        depth -= 1
                    i += 1
                walk(rest[: i - 1], f"{ctx}@{name} {cond}".strip())
                text = rest[i:]
                continue
            block = re.match(r"([^{}]+)\{([^{}]*)\}", text)
            if not block:
                return
            body = block.group(2).strip()
            for one in block.group(1).split(","):
                sel = re.sub(r"\s+", " ", one).strip()
                if sel and body:
                    found.setdefault((ctx, sel), set()).add(body)
            text = text[block.end():]

    walk(css, "")
    return found


class TestTheStylesheetHasNoSilentCollisions:
    """The bug this guards: `.steps` styled the runner's step count *and* the
    gate's ordered list, so `white-space: nowrap` reached the whole gate and the
    page grew 700px sideways. `.btn` and `.btn:hover` are the same class doing
    two things on purpose, so only an identical *base* selector counts."""

    def test_no_selector_is_styled_twice_with_different_rules(self, css: str) -> None:
        clashes = {k: v for k, v in css_rules(css).items() if len(v) > 1}
        assert not clashes, (
            "these selectors have more than one distinct rule block, so a later "
            f"one silently overrides the earlier: {sorted(cl[1] for cl in clashes)}\n"
            + "\n".join(f"  {k}: {sorted(v)}" for k, v in clashes.items())
        )

    def test_class_names_are_unique_across_the_page(self, html: str, css: str) -> None:
        """Every class the HTML uses must have a rule behind it."""
        groups = set(re.findall(r'class="([^"]+)"', html))
        used = {c for group in groups for c in group.split()}
        styled = {
            name
            for (_, sel) in css_rules(css)
            for name in re.findall(r"\.([A-Za-z][\w-]*)", sel)
        }
        unstyled = used - styled
        assert not unstyled, f"classes in the HTML with no CSS rule: {sorted(unstyled)}"

    def test_body_text_colours_clear_wcag_aa(self, css: str) -> None:
        """Read the declared values, so the check cannot drift from the CSS."""

        def srgb(c: float) -> float:
            c /= 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        def lum(h: str) -> float:
            h = h.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = (srgb(int(h[i : i + 2], 16)) for i in (0, 2, 4))
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        def ratio(a: str, b: str) -> float:
            la, lb = lum(a), lum(b)
            hi, lo = max(la, lb), min(la, lb)
            return (hi + 0.05) / (lo + 0.05)

        declared = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{3,6})\s*;", css))
        for fg, bg in (
            ("fg", "bg"), ("fg-dim", "bg"), ("fg-faint", "bg"),
            ("fg-faint", "bg-soft"), ("fg-dim", "bg-soft"),
            ("accent", "bg"), ("good", "bg"),
        ):
            assert fg in declared and bg in declared, f"stylesheet is missing --{fg} or --{bg}"
            r = ratio(declared[fg], declared[bg])
            assert r >= 4.5, f"--{fg} on --{bg} is {r:.2f}:1, needs 4.5:1"

    def test_the_accent_is_the_brand_colour(self, css: str) -> None:
        """#F5A524, deliberately outside GitHub's reserved gate colours.

        Comments are stripped first: the stylesheet *names* the reserved colours
        in a comment explaining why it avoids them, and reading the comment as a
        declaration would fail the check on the correct file.
        """
        code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        declared = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{3,6})\s*;", code))
        assert declared["accent"].lower() == "#f5a524"
        for reserved in ("#3fb950", "#d29922", "#cf222e"):
            assert reserved not in code.lower(), f"{reserved} is GitHub's, not ours"


# --------------------------------------------------------------------------
# 4. the rendered page
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def served():
    """Serve docs/ the way GitHub Pages will, and yield the base URL."""
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        # `directory` has to be passed here. Subclassing a
        # functools.partial(SimpleHTTPRequestHandler, directory=...) and handing
        # the subclass to the server drops the kwarg, so the server serves the
        # pytest cwd instead and every selector below finds nothing.
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(DOCS), **kwargs)

        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()


@pytest.fixture(scope="module")
def pages(browser, served):
    """Two real viewports, loaded the way a visitor loads them."""
    out = {}
    for w, h, tag in ((1280, 900, "desktop"), (390, 844, "phone")):
        pg = browser.new_page(viewport={"width": w, "height": h})
        errors: list[str] = []

        def record(msg, sink=errors):
            if msg.type == "error":
                sink.append(msg.text)

        def failed(exc, sink=errors):
            sink.append(str(exc))

        pg.on("console", record)
        pg.on("pageerror", failed)
        pg.goto(served, wait_until="networkidle")
        pg.wait_for_timeout(600)
        out[tag] = (pg, errors)
    yield out
    for pg, _ in out.values():
        pg.close()


class TestTheRenderedPage:
    def test_the_document_actually_loaded(self, pages) -> None:
        """Guard the guard: if the server ever serves the wrong directory again,
        every selector below would quietly time out instead of telling us why."""
        for tag, (pg, _) in pages.items():
            assert pg.title(), f"{tag}: no document served"
            assert pg.query_selector("a.brand img") is not None, (
                f"{tag}: the page is not the one in docs/ -- check the served fixture"
            )

    def test_nothing_console_errors(self, pages) -> None:
        for tag, (_, errors) in pages.items():
            assert not errors, f"{tag} console errors: {errors}"

    @pytest.mark.parametrize("tag", ["desktop", "phone"])
    def test_the_page_does_not_scroll_sideways(self, pages, tag: str) -> None:
        """A transcript wide enough to widen the document is a real bug.

        This is the check that would have caught the `.steps` collision.
        """
        pg, _ = pages[tag]
        over = pg.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert over <= 1, f"{tag}: content is {over}px wider than the viewport"

    @pytest.mark.parametrize("tag", ["desktop", "phone"])
    def test_nothing_overflows_its_container(self, pages, tag: str) -> None:
        pg, _ = pages[tag]
        offenders = pg.evaluate(
            """() => {
                const vw = document.documentElement.clientWidth;
                const bad = [];
                for (const n of document.querySelectorAll('body *')) {
                    const cs = getComputedStyle(n);
                    if (cs.position === 'fixed' || cs.display === 'none') continue;
                    // only elements that are not inside a scroll container
                    let p = n.parentElement, scrolls = false;
                    while (p && p !== document.body) {
                        if (getComputedStyle(p).overflowX !== 'visible') { scrolls = true; break; }
                        p = p.parentElement;
                    }
                    if (scrolls) continue;
                    const r = n.getBoundingClientRect();
                    if (r.width > vw + 1) bad.push([n.tagName, n.className, Math.round(r.width)]);
                }
                return bad.slice(0, 6);
            }"""
        )
        assert not offenders, f"{tag}: elements wider than the viewport: {offenders}"

    def test_the_transcript_actually_rendered(self, pages) -> None:
        """If the fetch broke, the page must say so rather than look fine."""
        for tag, (pg, _) in pages.items():
            happy = pg.inner_text("#term-happy").strip()
            assert "browse_navigate" in happy, f"{tag}: no transcript rendered"
            assert "unavailable" not in happy, f"{tag}: transcript failed to load"
            assert "verified" in happy, f"{tag}: the verified flag is not shown"

    def test_verified_and_unverified_look_different(self, pages) -> None:
        """The whole point is that `verified: false` is visually distinct."""
        for tag, (pg, _) in pages.items():
            colours = pg.eval_on_selector_all(
                "#term-happy .ok, #term-happy .unverified",
                "ns => ns.map(n => getComputedStyle(n).color)",
            )
            assert len(colours) > 1, f"{tag}: no verified flags rendered"
            assert len(set(colours)) > 1, (
                f"{tag}: verified and unverified render identically ({set(colours)})"
            )

    def test_the_gate_run_shows_the_hold(self, pages) -> None:
        for tag, (pg, _) in pages.items():
            gate = pg.inner_text("#term-gate")
            assert gate.strip(), f"{tag}: the gate transcript is empty"
            assert "unavailable" not in gate

    def test_tap_targets_are_big_enough_on_a_phone(self, pages) -> None:
        pg, _ = pages["phone"]
        small = pg.eval_on_selector_all(
            "a.btn, .tab, .navlinks a, a.brand",
            "ns => ns.map(n => { const r = n.getBoundingClientRect();"
            " return [n.textContent.trim().slice(0, 16), Math.round(r.height)]; })"
            ".filter(x => x[1] < 44)",
        )
        assert not small, f"interactive targets under 44px: {small}"

    def test_the_logo_is_visible_not_black_on_black(self, pages) -> None:
        """The brand SVGs ship with currentColor; a hardcoded black fill would
        render as nothing on a dark page."""
        for tag, (pg, _) in pages.items():
            size = pg.eval_on_selector(
                "a.brand img", "n => { const r = n.getBoundingClientRect(); return [r.width, r.height]; }"
            )
            assert size[0] > 8 and size[1] > 8, f"{tag}: logo has no size {size}"
            colour = pg.eval_on_selector("a.brand img", "n => getComputedStyle(n).color")
            assert colour != "rgb(0, 0, 0)", f"{tag}: logo is black on a dark page"
            raw = (DOCS / "mark.svg").read_text(encoding="utf-8")
            assert "currentColor" in raw, "mark.svg should paint with currentColor"
            assert "#000000" not in raw, "mark.svg still hardcodes a black fill"

    def test_the_install_tabs_actually_switch(self, pages) -> None:
        pg, _ = pages["desktop"]
        first = pg.inner_text("#installcmd")
        pg.click(".tab[data-os='unix']")
        after = pg.inner_text("#installcmd")
        assert after != first, "the unix tab did not change the command"
        assert after.strip().startswith("curl"), after
        pg.click(".tab[data-os='win']")
        assert pg.inner_text("#installcmd") == first

    def test_the_difference_minis_render(self, pages) -> None:
        """main.js guards these elements so docs.html can share the script;
        the guard must not become a silent no-op on the page that has them."""
        pg, _ = pages["desktop"]
        for sel in ("#term-other", "#term-orvima"):
            text = pg.inner_text(sel)
            assert "ok=True" in text, f"{sel} did not paint: {text!r}"

    def test_every_anchor_resolves(self, pages) -> None:
        """A dead in-page link on a one-page site is a dead end for a visitor."""
        pg, _ = pages["desktop"]
        broken = pg.evaluate(
            """() => [...document.querySelectorAll('a[href^="#"]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => h !== '#' && !document.querySelector(h))"""
        )
        assert not broken, f"anchors with no target: {broken}"

    def test_every_asset_loads(self, pages) -> None:
        pg, _ = pages["desktop"]
        missing = pg.evaluate(
            """() => [...document.querySelectorAll('img')]
                 .filter(i => !i.complete || i.naturalWidth === 0)
                 .map(i => i.getAttribute('src'))"""
        )
        assert not missing, f"images that did not load: {missing}"


# --------------------------------------------------------------------------
# 5. the docs page
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def docs_html() -> str:
    return (DOCS / "docs.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def docs_page(browser, served):
    """The generated page, loaded the way a visitor loads it."""
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    errors: list[str] = []

    def record(msg, sink=errors):
        if msg.type == "error":
            sink.append(msg.text)

    def failed(exc, sink=errors):
        sink.append(str(exc))

    pg.on("console", record)
    pg.on("pageerror", failed)
    pg.goto(served + "docs.html", wait_until="networkidle")
    pg.wait_for_timeout(600)
    yield pg, errors
    pg.close()


class TestTheDocsPageIsNotForgotten:
    """docs.html is generated by docs/build_docs.py and ships beside the
    index, sharing this stylesheet while using classes the index never does.
    It drifted twice: from its generator (the page is a build artifact with
    nothing enforcing a rebuild), and from the stylesheet (when the index's
    sections were renamed, the generic rule that dressed docs.html went with
    them, and every section collapsed to flush-left text with no separators).
    Both failure modes live here."""

    def test_the_shipped_page_matches_its_generator(self, docs_html: str) -> None:
        sys.path.insert(0, str(DOCS))
        try:
            import build_docs
        finally:
            sys.path.remove(str(DOCS))
        assert build_docs.render() == docs_html, (
            "docs/docs.html is stale -- rebuild it: python docs/build_docs.py"
        )

    def test_every_class_on_the_docs_page_is_styled(self, docs_html: str, css: str) -> None:
        """The index's coverage check reads index.html; docs.html has its own
        class vocabulary (`.badge`, `.endpoint`, `.docsec`...) that it also    has to keep in the stylesheet."""
        groups = set(re.findall(r'class="([^"]+)"', docs_html))
        used = {c for group in groups for c in group.split()}
        styled = {
            name
            for (_, sel) in css_rules(css)
            for name in re.findall(r"\.([A-Za-z][\w-]*)", sel)
        }
        unstyled = used - styled
        assert not unstyled, f"docs.html classes with no CSS rule: {sorted(unstyled)}"

    def test_the_docs_page_names_exactly_the_real_tools(self, docs_html: str) -> None:
        """The generator lists every tool, but its prose names some by hand;
        `browse_snapshot` in the architecture section would still be there
        after the tool was deleted, which is drift the freshness check above
        cannot see because the prose lives in the generator."""
        named = set(re.findall(r"browse_[a-z_]+", docs_html))
        assert named, "the docs page should name its tools at all"
        real = tool_names()
        assert named == real, (
            f"docs.html drifts from orvima.tools: invented {sorted(named - real)}, "
            f"missing {sorted(real - named)}"
        )


class TestTheRenderedDocsPage:
    """The static checks above prove the rules exist; these prove a browser
    actually applies them. The padding check is the one that would have
    caught the collapse: an unstyled section computes padding-left: 0px."""

    def test_the_docs_page_loads_cleanly(self, docs_page) -> None:
        pg, errors = docs_page
        assert pg.title(), "no document served"
        assert not errors, f"console errors: {errors}"
        over = pg.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert over <= 1, f"content is {over}px wider than the viewport"

    def test_every_docs_section_has_its_box(self, docs_page) -> None:
        pg, _ = docs_page
        for sel in (
            "#tool-reference",
            "#api-reference",
            "#mcp-configs",
            "#mcp-prompts",
            "#architecture",
            "#proof",
        ):
            pad = pg.evaluate(
                f"getComputedStyle(document.querySelector('{sel}')).paddingLeft"
            )
            assert pad not in ("0px", ""), f"{sel} has no padding: it is unstyled"
        assert pg.query_selector(".badge"), "tool badges did not render"
        assert pg.query_selector(".endpoint .method"), "endpoint methods did not render"

    def test_the_docs_page_renders_the_real_transcripts(self, docs_page) -> None:
        """main.js serves two pages from one script; a missing element there
        used to be a console error waiting to happen."""
        pg, _ = docs_page
        assert pg.inner_text("#term-happy").strip(), "docs.html renders no transcript"

    def test_every_docs_anchor_resolves(self, docs_page) -> None:
        pg, _ = docs_page
        broken = pg.evaluate(
            """() => [...document.querySelectorAll('a[href^="#"]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => h !== '#' && !document.querySelector(h))"""
        )
        assert not broken, f"anchors with no target: {broken}"

