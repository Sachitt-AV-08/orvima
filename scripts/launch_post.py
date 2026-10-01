"""Publish the Orvima launch post to LinkedIn, driven by Orvima.

The post claims it was composed and published by Orvima driving a logged-in
browser from the command line. This script is that claim, so it has to hold up:
every step is observed, and the run exits non-zero unless a permalink appears.

It drives the already-open Brave tab over page-level CDP. That path exists
because browser-level connect_over_cdp never completes against a real
daily-driver profile (it enumerates every target first - measured still hanging
at 90s on an 18-target Brave profile). Page-level CDP reaches the same logged-in
tab in ~20ms.

Usage:
    python scripts/launch_post.py --dry-run    # compose + verify, never click Post
    python scripts/launch_post.py              # compose + post + confirm permalink
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from orvima.cdp import CDPError, CDPPage  # noqa: E402

CDP = "http://127.0.0.1:9335"
TAB_HINT = "linkedin.com"
TEXT_FILE = ROOT / "scripts" / "launch_post.txt"
IMAGE_FILE = ROOT / "assets" / "orvima-banner.png"
LOG_FILE = ROOT / "scripts" / "launch_post.log"

OPEN_JS = """
(() => {
  const b = document.querySelector('[aria-label*="start a post" i]');
  if (!b) return 'not-found';
  b.click();
  return 'clicked';
})()
"""

SUBMIT_STATE_JS = """
(() => {
  const btn = Array.from(document.querySelectorAll('button'))
    .find(b => (b.innerText || '').trim().toLowerCase() === 'post');
  if (!btn) return {exists: false};
  const r = btn.getBoundingClientRect();
  const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  return {
    exists: true,
    disabled: !!btn.disabled || btn.getAttribute('aria-disabled') === 'true',
    width: Math.round(r.width),
    height: Math.round(r.height),
    hitTag: hit ? hit.tagName : null,
  };
})()
"""

EDITOR_JS = """
(() => {
  const el = document.querySelector(".tiptap.ProseMirror[contenteditable='true']")
          || document.querySelector("[contenteditable='true']");
  return el ? (el.innerText || '') : '';
})()
"""

_n = 0
PACE = False


def beat(what: str) -> None:
    """A visible pause between steps, so a screen recording is watchable."""
    if PACE:
        time.sleep(2.0)
        log(f"  ... {what}")


def log(msg: str, level: str = "INFO") -> None:
    global _n
    _n += 1
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {_n:02d} {level:5s} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def fail(msg: str) -> None:
    log(msg, "FAIL")
    log("run incomplete - nothing was published", "WARN")
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="prepare the composer, never post")
    ap.add_argument("--cdp", default=CDP)
    ap.add_argument("--tab", default=TAB_HINT)
    ap.add_argument(
        "--pace",
        action="store_true",
        help="pause visibly between steps so a screen recording is legible",
    )
    args = ap.parse_args()
    global PACE
    PACE = args.pace

    text = TEXT_FILE.read_text(encoding="utf-8").strip()
    if not IMAGE_FILE.exists():
        fail(f"banner missing: {IMAGE_FILE}")
    log(f"body {len(text)} chars, banner {IMAGE_FILE.name}")

    page = CDPPage(args.cdp, tab_hint=args.tab)
    try:
        t0 = time.monotonic()
        page.open()
        log(f"attached to the {args.tab!r} tab in {(time.monotonic()-t0)*1000:.0f}ms")
    except CDPError as exc:
        fail(f"could not attach: {exc}")
        return 1

    try:
        # 1. session must be live, or there is nothing to post from
        log("navigating to the feed with the existing session")
        page.goto("https://www.linkedin.com/feed/")
        body = page.eval("document.body.innerText.slice(0, 600)") or ""
        if "Messaging" not in body and "Sachitt" not in body:
            fail("the Brave tab is not signed in to LinkedIn")
        log("signed in, on the feed")
        beat("feed is loaded")

        # 2. open the composer
        log("clicking 'Start a post'")
        if page.eval(OPEN_JS) != "clicked":
            fail("could not find the 'Start a post' control")
        if not page.wait_for(".tiptap.ProseMirror[contenteditable='true']", timeout_s=20):
            fail("composer editor never appeared")
        log("composer open")
        beat("composer is open")

        # 3. text in, then read back - a click that did nothing is not a post
        log("typing the post body")
        page.focus(".tiptap.ProseMirror[contenteditable='true']")
        t0 = time.monotonic()
        page.insert_text(text)
        read_back = (page.eval(EDITOR_JS) or "").strip()
        if len(read_back) < len(text) * 0.9:
            fail(f"text did not land ({len(read_back)} of {len(text)} chars read back)")
        log(f"text verified in editor: {len(read_back)} chars in {(time.monotonic()-t0)*1000:.0f}ms")
        beat("body is in the editor")

        # 4. attach the banner
        log("attaching the banner")
        if page.eval(
            "(() => { const b = document.querySelector('[aria-label*=\"media\" i],"
            " [aria-label*=\"photo\" i]'); if (!b) return false; b.click(); return true; })()"
        ):
            time.sleep(1.5)
            page.set_file_input("input[type='file']", [str(IMAGE_FILE)])
            time.sleep(2.0)
            previews = page.eval("document.querySelectorAll('img').length")
            log(f"banner attached (img nodes on page: {previews})")
        else:
            log("no media control found - posting text only", "WARN")
        beat("banner is attached")

        # 5. is Post actually live?
        state = page.eval(SUBMIT_STATE_JS) or {}
        if not state.get("exists"):
            fail("no Post button in the composer")
        if state.get("disabled"):
            fail("Post button is disabled - composer never became ready")
        log(f"Post enabled ({state.get('width')}x{state.get('height')}, top element {state.get('hitTag')})")
        beat("Post button is live")

        if args.dry_run:
            log("DRY RUN: composer fully prepared, Post NOT clicked")
            log("the post is sitting in the LinkedIn composer, ready to click Post")
            return 0

        # 6. post, then insist on proof
        page.eval(
            "(() => { const b = Array.from(document.querySelectorAll('button'))"
            ".find(x => (x.innerText || '').trim().toLowerCase() === 'post');"
            " if (!b) return false; b.click(); return true; })()"
        )
        log("clicked Post")

        for _ in range(30):
            time.sleep(2)
            if "/feed/update/" in (page.url() or ""):
                log(f"PUBLISHED: {page.url()}")
                return 0
        fail(f"no permalink after clicking Post (at {page.url()}) - it did not publish")
        return 1

    except CDPError as exc:
        fail(f"CDP error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        fail(f"unexpected {type(exc).__name__}: {exc}")
        return 1
    finally:
        page.close()
        log("CDP socket closed")


if __name__ == "__main__":
    sys.exit(main())
