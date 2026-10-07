"""The browser the agent lives in.

Two ways to reach "your browser":

* default — launch **your installed Chrome or MS Edge** with a persistent
  Orvima profile (~/.orvima/profile). Visible, headful, and your logins
  survive restarts; your everyday profile is never touched.
* ``--attach`` — connect over CDP to a browser that is *already running*
  (``orvima setup`` can start one), driving its real tabs and logins as-is.

Every op returns confirmation from the page itself (verify-first). ``snapshot``
renders a compact, LLM-friendly outline of the DOM so an agent can decide
without megabytes of HTML.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .backend import NavigationBackend
from .errors import BrowserError
from .identity import ElementIdentity, RefRegistry
from .occlusion import uncover
from .recovery import looks_irreversible

DEFAULT_PROFILE = str(Path.home() / ".orvima" / "profile")

# Playwright's default connect_over_cdp timeout is 180s. When another CDP client
# already owns the browser the handshake never completes, so that default turns a
# clear mistake into a silent three-minute freeze. Fail fast and say why instead.
DEFAULT_ATTACH_TIMEOUT_S = 10.0


def _attach_timeout_ms() -> int:
    """Bounded CDP attach budget, overridable with ORVIMA_ATTACH_TIMEOUT (seconds)."""
    raw = os.environ.get("ORVIMA_ATTACH_TIMEOUT")
    try:
        seconds = float(raw) if raw else DEFAULT_ATTACH_TIMEOUT_S
    except ValueError:
        seconds = DEFAULT_ATTACH_TIMEOUT_S
    if seconds <= 0:
        seconds = DEFAULT_ATTACH_TIMEOUT_S
    return int(seconds * 1000)


def _type_delay_ms() -> int:
    """Per-character typing delay, overridable with ORVIMA_TYPE_DELAY_MS.

    Defaults to 0: an agent pays this cost on every character it sends, and
    human-style pacing is the product layer's job (see parley's HumanPacing),
    not the browser driver's.
    """
    raw = os.environ.get("ORVIMA_TYPE_DELAY_MS")
    try:
        ms = float(raw) if raw else 0.0
    except ValueError:
        ms = 0.0
    return max(0, int(ms))


# Common ports where users run browsers with --remote-debugging-port
_DEFAULT_DEBUG_PORTS = (9222, 9223, 9224, 9225, 9229)


def _cdp_endpoint_alive(attach: str) -> bool:
    """True when something answers on the CDP HTTP endpoint."""
    if attach.startswith(("ws://", "wss://")):
        return True  # can't cheaply probe a websocket URL; let connect try
    base = attach.rstrip("/")
    url = f"{base}/json/version" if base.startswith("http") else attach
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - fixed loopback endpoint
            return resp.status < 500
    except urllib.error.HTTPError:
        return True  # something is listening, just not on this path
    except Exception:
        return False


def _auto_detach_url() -> str | None:
    """Return a CDP HTTP endpoint (http://127.0.0.1:PORT) if a browser is already
    running with remote debugging enabled on a common port.

    Scans default ports in order and returns the first one that answers
    /json/version with a valid browser response. This lets orvima adapt to
    the user's already-running Brave/Chrome/Edge instead of launching its own.
    """
    for port in _DEFAULT_DEBUG_PORTS:
        url = f"http://127.0.0.1:{port}"
        if _cdp_endpoint_alive(url):
            return url
    return None


def _cdp_page_sockets(attach: str) -> list[dict]:
    """List the open page targets on a CDP endpoint."""
    base = attach.rstrip("/")
    if not base.startswith("http"):
        return []
    try:
        with urllib.request.urlopen(f"{base}/json/list", timeout=3) as resp:  # noqa: S310
            targets = json.loads(resp.read().decode())
    except Exception:
        return []
    return [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def _page_socket_for(attach: str, hint: str) -> str:
    """Find a page target's own debugger socket.

    Browser-level ``connect_over_cdp`` enumerates and auto-attaches to every
    target before finishing its handshake, so against a real daily-driver profile
    (extension service workers, reCAPTCHA iframes, a dozen tabs) it never
    completes - measured past 90s with no other client attached. Connecting to a
    single page's socket skips that entirely and returns in milliseconds.

    Returns "" when no target matches, so the caller can fall back.
    """
    pages = _cdp_page_sockets(attach)
    if not pages:
        return ""
    if hint:
        hint_l = hint.lower()
        for target in pages:
            if hint_l in (target.get("url") or "").lower():
                return target["webSocketDebuggerUrl"]
            if hint_l in (target.get("title") or "").lower():
                return target["webSocketDebuggerUrl"]
        return ""
    return pages[0]["webSocketDebuggerUrl"]

_BROWSER_PATHS = {
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
    "msedge": (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ),
    # Brave is Chromium, so it speaks CDP and drives through the same code path
    # as Chrome and Edge. It is listed here rather than left to autodetection
    # because `--browser brave` was rejected by argparse's `choices`, which meant
    # the documented way to select it could not be used at all.
    "brave": (
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ),
}

#: Walks a document *and* its open shadow roots and same-origin frames, so a
#: snapshot sees what a user sees. Playwright reaches all of these through its
#: own API, but a single JS walk keeps the outline logic in one place and means
#: the same code produces the ref numbering the identity registry depends on.
#:
#: Cross-origin frames are reported by src and nothing more. Their DOM is not
#: reachable and must not be pretended otherwise.
_OUTLINE_JS = """(() => {
  const out = [];

  // Depth is bounded. A page that nests frames or shadow roots inside each
  // other forever would otherwise hang the agent, and a snapshot that never
  // returns is indistinguishable from a hung browser.
  const MAX_DEPTH = 6;

  const text = (el) => (el.innerText || "").trim().replace(/\\s+/g, " ").slice(0, 400);
  const role = (el) => {
    if (el.tagName === "A" || el.tagName === "BUTTON") return el.tagName.toLowerCase();
    return el.getAttribute("role") || "";
  };
  const isVisible = (el) => {
    // The hidden attribute is display:none by UA stylesheet, but a page that
    // sets `display: flex` on the element beats it - so check it directly.
    if (el.hasAttribute("hidden")) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (style.opacity === "0") return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    if (el.closest("[hidden]")) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  // Which document an element belongs to, so the snapshot can say whether a ref
  // sits behind a shadow boundary. querySelectorAll on a document already
  // pierces open shadow roots, so most elements are found directly and this
  // only confirms it rather than driving a second traversal.
  const inShadowRoot = (el) => {
    try {
      const root = el.getRootNode ? el.getRootNode() : document;
      return Boolean(root && root.host);
    } catch (_) { return false; }
  };

  const shadowHosts = Array.from(document.querySelectorAll("*")).filter((el) => {
    try { return Boolean(el.shadowRoot); } catch (_) { return false; }
  }).length;

  const seen = new Set();
  let idx = 0;
  const LIMIT = 60;

  const walk = (root, depth, frameChain) => {
    if (depth > MAX_DEPTH || idx >= LIMIT) return;
    let items;
    try { items = root.querySelectorAll(
      "a,button,input,textarea,select,label,h1,h2,h3,h4,h5,h6,[role='button'],[role='link'],[role='textbox'],[aria-label]"
    ); }
    catch (_) { return; }

    for (const el of items) {
      if (idx >= LIMIT) return;
      if (seen.has(el)) continue;
      seen.add(el);
      if (!isVisible(el)) continue;
      idx++;
      const ref = "e" + idx;
      try { el.setAttribute("data-orvima-ref", ref); } catch (_) {}
      const r = role(el);
      const label = el.getAttribute("aria-label") || el.getAttribute("placeholder") ||
                    el.getAttribute("title") || (el.tagName === "LABEL" ? text(el) : "");
      const own = text(el);
      // Redact password values in snapshots
      const isPassword = el.type === "password";
      const rawVal = el.value !== undefined && el.value ? String(el.value).slice(0, 80) : "";
      const val = (el.value !== undefined && el.value)
          ? ` value=${JSON.stringify(isPassword ? "***" : rawVal)}`
          : "";
      const info = [r, label || own, val].filter(Boolean).join(" | ");
      if (info) {
        out.push({
          ref,
          tag: el.tagName.toLowerCase(),
          role: r,
          label: label || own,
          text: own,
          value: isPassword ? "***" : (el.value || ""),
          // How to get back to this element, for click/type/fill/extract.
          inShadow: inShadowRoot(el),
          framePath: frameChain,
        });
      }
    }

    // Open shadow roots are already covered by querySelectorAll piercing, but a
    // nested root inside a root still needs an explicit pass for elements the
    // host's own query cannot reach.
    for (const el of root.querySelectorAll("*")) {
      if (idx >= LIMIT) return;
      if (el.shadowRoot) walk(el.shadowRoot, depth + 1, frameChain);
    }
  };

  walk(document, 0, []);

  const body = document.body ? text(document.body) : "";
  return {
    url: location.href,
    title: document.title,
    items: out,
    body: body.slice(0, 3000),
    truncated: idx >= LIMIT,
    shadowHosts: shadowHosts,
  };
})()
"""


#: Resolves a ref to the element it currently points at, or null if the
#: attribute is gone. Used to notice a hijacked ref before clicking it.
#: Takes the ref as an argument rather than reading a global, so a page cannot
#: spoof the value and convince the guard it is looking at something else.
_IDENTITY_JS = """(ref) => {
  // In-page querySelectorAll does NOT pierce shadow roots - only Playwright's own
  // engine does. A plain document search therefore reports every shadow-hosted
  // ref as gone, and the guard then refuses a perfectly valid click. Walk the
  // open roots by hand.
  const sel = '[data-orvima-ref="' + ref + '"]';
  let el = null;
  const search = (root, depth) => {
    if (el || depth > 6) return;
    try {
      const direct = root.querySelector(':scope > ' + sel);
      if (direct) { el = direct; return; }
    } catch (_) { /* fall through to the full query */ }
    try {
      const hit = root.querySelector(sel);
      if (hit) { el = hit; return; }
    } catch (_) { /* ignore */ }
    let hosts;
    try { hosts = root.querySelectorAll('*'); } catch (_) { return; }
    for (const host of hosts) {
      if (el) return;
      if (host.shadowRoot) search(host.shadowRoot, depth + 1);
    }
  };
  search(document, 0);
  if (!el) return null;
  const text = (e) => (e.innerText || "").trim().replace(/\\s+/g, " ").slice(0, 400);
  const role = (e) => {
    if (e.tagName === "A" || e.tagName === "BUTTON") return e.tagName.toLowerCase();
    return e.getAttribute("role") || "";
  };
  const label = el.getAttribute("aria-label") || el.getAttribute("placeholder") ||
                el.getAttribute("title") || (el.tagName === "LABEL" ? text(el) : "");
  return {
    tag: el.tagName.toLowerCase(),
    role: role(el),
    label: label || text(el),
    text: text(el),
  };
}"""


#: Cap on outlined elements, matching what the per-frame JS walk allows.
_OUTLINE_LIMIT = 60 * 4

#: Matches the ref selector tools hand around, including the per-frame prefix.
#: Refs are ``e3`` on the main document and ``f2:e3`` inside a frame, so a regex
#: that only accepted ``e3`` silently sent every frame ref down the main-document
#: path - which is how a click aimed at a frame timed out.
_REF_SELECTOR_RE = re.compile(r'^\[data-orvima-ref="((?:f(\d+):)?e(\d+))"\]$')


def attachment_verified(attached, resolved) -> bool:
    """Whether the page really holds the files we said we attached.

    Three ways this is False, and each is a way a caller could otherwise be told
    a resume was ready to send:

    - the readback failed entirely (``attached is None``) - the attachment was
      never confirmed
    - the page holds nothing, or holds a different number of files - a filtered
      or rejected upload
    - the page holds a *different* file - the worst case, because something was
      attached and it was the wrong thing

    Named rather than inlined so the rule can be tested directly. Reaching the
    "page holds the wrong file" case through a real page is contrived, and a rule
    that cannot be tested is a rule that quietly stops being true.
    """
    if attached is None or not resolved:
        return False
    if len(attached) != len(resolved):
        return False
    got = sorted(f.get("name") for f in attached)
    want = sorted(Path(p).name for p in resolved)
    return got == want


def _bare_ref(ref: str) -> str:
    """The eN part of a ref, dropping any frame prefix.

    Defined once because getting it wrong is silent: an empty result turns into
    the selector ``[data-orvima-ref=""]``, which matches nothing and then times
    out for ten seconds on a page that was perfectly readable.

    ``partition(":")[2]`` is the obvious implementation and is wrong - for an
    unprefixed ref like ``e3`` there is no separator, so it returns the empty
    string rather than the ref itself.
    """
    head, sep, tail = ref.partition(":")
    return tail if sep and head.startswith("f") and head[1:].isdigit() else ref


def _describe_frames(total: int, traversed: int, not_traversed: list[dict]) -> str:
    """A short, honest account of what happened to the frames on this page."""
    if not total:
        return "none"
    if not not_traversed:
        return f"{total} frame(s), all traversed"
    return (
        f"{total} frame(s); {traversed} traversed; "
        f"{len(not_traversed)} not reachable (see notTraversed)"
    )


def _frame_is_readable(frame, data: dict) -> bool:
    """Whether a frame really gave us its DOM.

    Chromium exposes a cross-origin frame as a frame object that ``evaluate``
    accepts without raising, returning an empty result. Counting that as a
    traversal produces a snapshot claiming "all frames traversed" when part of
    the page was never read - the exact dishonesty this phase is meant to avoid.
    """
    url = (frame.url or "").strip()
    if not url:
        return False
    if url.startswith("chrome-error://") or url.startswith("about:blank"):
        # A load failure or an empty placeholder, never real content.
        return False
    try:
        ready = frame.evaluate("() => document.readyState")
    except Exception:
        return False
    if not ready:
        return False
    # A readable document with genuinely nothing in it is legitimate - an empty
    # frame is not the same as an unreadable one, and the outline having no
    # items is not by itself evidence of anything.
    return True


def detect_channel() -> str | None:
    """Return 'chrome', 'msedge', 'brave', or None (use bundled chromium)."""
    env = (os.environ.get("ORVIMA_BROWSER") or "").strip().lower()
    if env in ("chrome", "msedge", "brave", "chromium"):
        return None if env == "chromium" else env
    for name, candidates in _BROWSER_PATHS.items():
        if sys.platform == "win32" and any(
            # expandvars, because a per-user install path is written with
            # %LOCALAPPDATA% and Path(...).exists() does not expand it - the
            # entry would look present in the table and never match on disk.
            Path(os.path.expandvars(p)).exists() for p in candidates
        ):
            return name
    return None


def bundled_chromium_path() -> str | None:
    """Path to Playwright's bundled Chromium, or ``None`` if it is not present.

    ``detect_channel`` returns ``None`` to mean "use bundled Chromium" - the
    docstring of that function promises a browser when one is found, so a
    ``None`` here is only a real browser if the bundle is actually downloaded.
    Real mode drives this binary, so doctor must treat a present bundle as a
    usable browser rather than as a failure: the previous code reported "no
    Chrome/Edge/Chromium/Brave found on PATH" while a working browser was right
    there, which is the exact lie this check used to tell.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        with sync_playwright() as p:
            path = p.chromium.executable_path
    except Exception:
        return None
    # executable_path may return a non-existent path before `playwright install`;
    # existence is the only thing that means "a browser is available".
    if path and Path(path).exists():
        return str(path)
    return None


class BrowserController(NavigationBackend):
    """Owns a browser + one active page, over Playwright."""

    def __init__(
        self,
        *,
        base_url: str = "https://example.com",
        headless: bool | None = None,
        profile_dir: str | None = None,
        attach: str | None = None,
        attach_tab: str | None = None,
        download_dir: str | None = None,
    ):
        self._base_url = base_url
        env_headless = os.environ.get("ORVIMA_HEADLESS")
        if env_headless:
            self._headless = env_headless.lower() in ("1", "true", "yes")
        else:
            self._headless = headless
        self._profile_dir = profile_dir or os.environ.get("ORVIMA_PROFILE", DEFAULT_PROFILE)
        self._attach = attach or os.environ.get("ORVIMA_ATTACH", "") or None
        self._attach_tab = attach_tab or os.environ.get("ORVIMA_ATTACH_TAB", "") or ""
        self._channel = None if self._attach else detect_channel()
        self._context = None
        self.page = None
        self._pw = None
        self._closed = False
        # What each ref described at the last snapshot. Populated by snapshot()
        # and consulted before every ref-based action.
        self._registry = RefRegistry()
        # ref -> frame index, so an f2:e1 ref is looked up in frame 2.
        self._ref_frames: dict[str, int] = {}
        # Where downloads are saved. Overridable per instance.
        self._download_dir = download_dir or os.environ.get(
            "ORVIMA_DOWNLOAD_DIR", str(Path.home() / ".orvima" / "downloads")
        )
        # A record of every eval that ran, for an agent holding arbitrary JS on a
        # logged-in page. Bounded so it cannot become a leak.
        self.eval_audit: list[dict] = []
        self.eval_audit_limit = 200

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            if self._attach:
                if not _cdp_endpoint_alive(self._attach):
                    raise BrowserError(
                        f"no browser is listening at {self._attach}. Start the browser with a "
                        f"debugging port (for example --remote-debugging-port=9334), or drop "
                        f"--attach to let orvima launch its own browser."
                    )
                timeout_ms = _attach_timeout_ms()
                page_ws = _page_socket_for(self._attach, self._attach_tab)
                if self._attach_tab and not page_ws:
                    open_tabs = ", ".join(
                        f"{(t.get('title') or t.get('url') or '?')[:40]}" for t in _cdp_page_sockets(self._attach)
                    )
                    raise BrowserError(
                        f"no open tab matches {self._attach_tab!r} in {self._attach}. "
                        f"Open tabs: {open_tabs or 'none'}"
                    )
                try:
                    # A page target's own socket skips browser-level target
                    # enumeration, which is what stalls on a busy real profile.
                    endpoint = page_ws or self._attach
                    browser = self._pw.chromium.connect_over_cdp(endpoint, timeout=timeout_ms)
                except Exception as exc:
                    if page_ws:
                        raise BrowserError(
                            f"could not attach to the {self._attach_tab!r} tab in "
                            f"{self._attach} within {timeout_ms // 1000}s: {exc}"
                        ) from exc
                    raise BrowserError(
                        f"could not attach to {self._attach} within {timeout_ms // 1000}s. The "
                        f"endpoint answered but the CDP browser handshake never completed. "
                        f"Chromium's connect_over_cdp enumerates and auto-attaches to every "
                        f"target, so a busy profile - extension service workers, reCAPTCHA "
                        f"iframes, many open tabs - can stall it indefinitely. Pass "
                        f"ORVIMA_ATTACH_TAB=<substring of the tab url or title> to attach to a "
                        f"single page instead, or let orvima launch its own browser."
                    ) from exc
                self._context = browser.contexts[0] if browser.contexts else None
                if self._context is None:
                    self._context = browser.new_context()
            elif self._channel:
                self._context = self._pw.chromium.launch_persistent_context(
                    self._profile_dir,
            accept_downloads=True,
                    channel=self._channel,
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            else:
                self._context = self._pw.chromium.launch_persistent_context(
                    self._profile_dir,
            accept_downloads=True,
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            pages = self._context.pages
            self.page = pages[0] if pages else self._context.new_page()
            self._goto(self._base_url)
        except BrowserError:
            self._teardown_playwright()
            raise  # already actionable - don't bury the real cause
        except Exception as exc:  # pragma: no cover - launch failures vary
            self._teardown_playwright()
            raise BrowserError(f"could not start a browser: {exc}") from exc

    def _teardown_playwright(self) -> None:
        """Stop the Playwright driver after a failed start.

        Without this, a failed start leaks the driver process *and* its asyncio
        loop. The next sync_playwright() start in the same process then fails
        with the misleading "you are using Playwright Sync API inside the asyncio
        loop" - so one failure cascades into unrelated ones.
        """
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # pragma: no cover - best effort
                pass
            self._pw = None
        self._context = None
        self.page = None

    #: Playwright reports a real load state, so this backend states one.
    REPORTS_LOAD_STATE = True

    def _perform_navigate(self, url: str) -> None:
        """The primitive NavigationBackend.navigate is written in terms of.

        Named `_goto` historically because only this class called it. It is now
        also how the shared navigate() reaches Playwright, so it is aliased
        rather than wrapped: `_goto` returns the load state and is called on its
        own during `start()` to reach the base url, where there is no
        expectation to judge.
        """
        self._goto(url)

    def _goto(self, url: str) -> dict:
        self._require_open()
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"navigation failed: {exc}") from exc
        return self._state()

    # ------------------------------------------------------- element identity --

    def _target(self, selector: str):
        """The Playwright target a selector should run against.

        For a ref that lives in a frame, that is the frame. For a plain selector
        it is the page, exactly as before - the 19-tool contract is unchanged,
        this only decides *where* an already-parsed ref is looked up.
        """
        m = _REF_SELECTOR_RE.match(selector or "")
        if not m:
            return self.page
        return self._frame_for_ref(m.group(1))

    @staticmethod
    def _locate(selector: str) -> str:
        """Rewrite a ref selector so it is valid in whichever frame owns the ref.

        Inside a frame the attribute is written as a plain ``eN`` - that frame's
        own document, not the top one - so the frame prefix has to be stripped
        back off for the attribute selector to mean anything. Group 1 is the full
        ref, so the eN form is just its last segment.
        """
        m = _REF_SELECTOR_RE.match(selector or "")
        if not m:
            return selector
        return f'[data-orvima-ref="{_bare_ref(m.group(1))}"]'

    def _guard_ref(self, selector: str) -> str:
        """Check that a ref still means what the last snapshot said it meant.

        A ref is the attribute ``[data-orvima-ref="eN"]``, assigned by numbering
        whatever was visible at snapshot time. If the page re-renders, the
        numbering is reassigned and the ref silently points at a *different*
        element - a click that looks successful and does the wrong thing. That
        is worse than an error, so this refuses rather than redirects.

        Returns the selector to use: either the original, or a replacement
        selector when the ref went stale but the element it described is still
        on the page. Raises when the ref is stale with no unambiguous
        substitute, or when it now points at something else entirely.
        """
        m = _REF_SELECTOR_RE.match(selector or "")
        if not m:
            return selector  # a plain selector is the caller's business
        ref = m.group(1)
        if not self._registry.identity_for(ref):
            return selector  # never described; nothing to compare against

        current = self._current_identity(ref)
        verdict = self._registry.resolve(ref, current)

        if verdict.safe:
            return selector
        if verdict.replacement is None:
            raise BrowserError(
                f"ref {ref} is stale: {verdict.reason}. Take a fresh snapshot to "
                "get current refs rather than reusing an old one"
            )

        replacement = self._selector_for(verdict.replacement)
        # The registry only knows what the *last snapshot* saw. A candidate found
        # there may be gone too, and handing back a selector for a dead node
        # just trades a clear error for a 10s Playwright timeout. Confirm it is
        # really on the page before committing to it.
        try:
            matches = self.page.locator(replacement).count()
        except Exception:
            matches = 0
        if matches == 0:
            raise BrowserError(
                f"ref {ref} is stale: {verdict.reason}, and nothing matching it is on the "
                "page now either. Take a fresh snapshot to get current refs"
            )
        return replacement

    def _frame_for_ref(self, ref: str):
        """The frame a ref lives in, or the main page.

        Refs are namespaced per frame, so this is a lookup rather than a guess.
        Without it, an ``f2:e1`` ref would be looked up on the main document,
        find nothing, and be reported stale when the element is sitting right
        there in the frame.
        """
        # The prefix is authoritative; the registry is the fallback for refs
        # whose prefix was lost in transit.
        head, _, _tail = ref.partition(":")
        if head.startswith("f") and head[1:].isdigit():
            index = int(head[1:])
        else:
            index = getattr(self, "_ref_frames", {}).get(ref, 0)
        if not index:
            return self.page
        try:
            return self.page.frames[index]
        except (IndexError, AttributeError):
            return self.page

    def _current_identity(self, ref: str):
        """What the ref points at right now, or None if nothing matches.

        Tri-state on purpose. ``None`` means "the selector matched nothing",
        which is the stale case. It must be distinguished from "the attribute
        is present, so the ref is fine" - conflating those two sent every
        still-valid ref down the re-resolution path and rebuilt a text-based
        selector that then timed out on a perfectly good ref.
        """
        bare = _bare_ref(ref)
        frame = self._frame_for_ref(ref)
        # Presence first: if the attribute is still there, the ref resolves and
        # the only question is whether it resolves to the *right* element.
        try:
            count = frame.locator(f'[data-orvima-ref="{bare}"]').count()
        except Exception:
            count = 0
        if count == 0:
            return None

        try:
            raw = frame.evaluate(_IDENTITY_JS, bare)
        except Exception:
            raw = None
        if not raw:
            # The attribute is present but the probe failed. Rather than guess
            # that it is safe, report it as unidentifiable: the caller treats an
            # unknown identity as a mismatch and refuses, which is the safe side.
            return ElementIdentity(ref=ref)
        return ElementIdentity(
            ref=ref,
            role=raw.get("role") or "",
            label=raw.get("label") or "",
            text=raw.get("text") or "",
            tag=raw.get("tag") or "",
        )

    def _selector_for(self, identity: ElementIdentity) -> str:
        """A selector that targets a re-resolved element.

        Built from the *recorded* identity rather than the live one, so it keeps
        working for the click that is about to happen even if the page shifts
        again immediately afterwards.

        Every candidate is comma-separated so Playwright tries them in turn. An
        earlier version emitted a single ``button:has-text("Publish")`` and that
        is far too loose - it matches any button containing the word, so a page
        with "Publish draft" and "Publish" would click whichever came first.
        Text matching is now an exact full-string match.
        """
        parts: list[str] = []
        label = identity.selector_label
        text = identity.selector_text
        if label:
            escaped = label.replace('"', '\\"')
            if identity.tag:
                parts.append(f'{identity.tag}[aria-label="{escaped}"]')
            parts.append(f'[aria-label="{escaped}"]')
        if text:
            # :text-is pins the match to the element's own full text, so a
            # button reading "Publish draft" cannot satisfy a ref recorded as
            # "Publish". It is case-sensitive, hence selector_text rather than
            # the normalised label.
            parts.append(f'{identity.tag or "*"}:text-is("{text}")')
        if not parts and identity.tag:
            parts.append(identity.tag)
        if not parts:
            raise BrowserError(
                f"cannot build a selector for {identity.ref!r}: it had no label, "
                "text, or tag to identify it by. Take a fresh snapshot"
            )
        return ", ".join(parts)

    def _state(self) -> dict:
        return {"url": self.page.url, "title": self.page.title()}

    def _dom_signature(self) -> str:
        """Signature of DOM state for click verification.

        Node count alone is not evidence: it changes on any unrelated mutation
        (ads, timers) and stays identical when a click only mutates attributes
        or text. This includes a text digest, so clicking something that updates
        a counter or swaps content is detected, while clicking inert elements is
        not.
        """
        try:
            parts = self.page.evaluate(
                """() => {
                  const body = document.body;
                  const text = (body && body.innerText) ? body.innerText.slice(0, 20000) : "";
                  let h = 0;
                  for (let i = 0; i < text.length; i++) {
                    h = (Math.imul(31, h) + text.charCodeAt(i)) | 0;
                  }
                  return {
                    url: location.href,
                    title: document.title,
                    nodes: document.querySelectorAll('*').length,
                    hash: h,
                  };
                }"""
            )
            return f"{parts['url']}|{parts['title']}|{parts['nodes']}|{parts['hash']}"
        except Exception:
            return ""

    # ------------------------------------------------------ expectations ----
    # `_check_expectations` is not defined here. It lives in NavigationBackend,
    # alongside `navigate`, because it was on this class alone for long enough
    # that the other two backends shipped without it - and one of them is the
    # harness the benchmark measures the agent through. See orvima/backend.py.
    def _read_page_state(self) -> dict:
        """Url and visible text, for expectation polling."""
        try:
            text = self.page.evaluate(
                "() => { const b = document.body;"
                " return b ? (b.innerText || '').slice(0, 20000) : ''; }"
            )
        except Exception:
            text = ""
        return {"url": self.page.url, "text": text}

    def _count_matching(self, selector: str | None) -> int | None:
        """How many elements a selector matches, or None if it cannot be read."""
        if not selector:
            return None
        try:
            return self.page.locator(selector).count()
        except Exception:
            return None

    def _read_value(self, selector: str, target=None) -> str | None:
        """Read a field's current value, whichever kind of element it is.

        `input_value()` only works on input/textarea/select, so contenteditable
        targets (rich editors, tiptap/ProseMirror composers) used to read back
        as a hard failure. Returns None only if the element can't be found.

        `target` is the frame a ref lives in, so verification does not silently
        read the wrong document.
        """
        target = target if target is not None else self.page
        try:
            return target.input_value(selector)
        except Exception:
            pass
        try:
            return target.inner_text(selector)
        except Exception:
            return None

    # ------------------------------------------------------------- actions ----
    # `navigate` and `click` are inherited from NavigationBackend, which owns
    # both the action and the judgement of it.

    def _perform_click(self, selector: str) -> dict:
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        # Move the page if a sticky or fixed header is covering the element.
        #
        # Playwright scrolls an element into view by *centring* it, so an element
        # near the top of the page can end up under a pinned header, where no
        # click is possible. Playwright's actionability check correctly refuses -
        # the pointer would land on the header - but it reports a bare timeout
        # that never mentions the header, so the failure reads as flakiness rather
        # than as a layout problem with a known fix.
        #
        # Only attempted when the element is actually covered: scrolling a page
        # that was fine changes its state and can move things under the cursor.
        moved = self._uncover_if_occluded(selector, target)
        # The element is covered and the geometry is fixed: no scroll can move it
        # out from under the occluder. Playwright would spend its full 10s
        # timeout rediscovering exactly this, so the wait buys nothing - it only
        # delays a report the caller could act on now. The named reason is the
        # whole value here: a bare "intercepts pointer events" timeout says
        # nothing about a sticky header.
        self._refuse_if_unreachable(selector, "click", moved)
        before_sig = self._dom_signature()
        try:
            target.click(selector, timeout=10000)
        except Exception as exc:
            raise BrowserError(
                f"click {selector!r} failed: {exc}"
                + (f" {moved['reason']}" if moved.get("reason") else "")
            ) from exc
        after_sig = self._dom_signature()
        return {**self._state(), "verified": before_sig != after_sig}

    def _refuse_if_unreachable(self, selector: str, action: str, moved: dict) -> None:
        """Fail fast when the probe has already proved the element is unreachable.

        Once `uncover` reports that the element is covered and no scroll can clear
        it, waiting out Playwright's 10s actionability timeout buys nothing: it
        re-derives the same geometry and reports a call log that names no header.

        Only raises when the probe was *certain* - an unfixable occlusion with a
        reason. A probe that merely failed, or a missing element, is left to
        Playwright, which is the authority on whether an action is possible.

        The message says what this action specifically did *not* do. It has to:
        a caller reading "click '#x' failed ... Nothing was typed" has been told
        about the wrong action, and a caller retrying after a timeout cannot tell
        from a vague message whether a half-typed value landed in a field.
        """
        if moved.get("uncovered") is False and moved.get("reason"):
            # What a refusal means, per action. A blanket "nothing happened" is
            # true of all of them but tells the caller nothing about which state
            # to trust - and for `type` and `fill` that is the whole question.
            untouched = {
                "click": "Nothing was clicked, so the page is unchanged",
                "hover": "Nothing was hovered, so no menu or tooltip opened",
                "type into": (
                    "Nothing was typed, so the field still holds its previous value"
                ),
                "fill": (
                    "Nothing was filled, so the field still holds its previous value"
                ),
                "select": (
                    "Nothing was selected, so the dropdown keeps its previous value"
                ),
                "click to download": (
                    "Nothing was clicked, so no download was started and no file "
                    "was written"
                ),
            }.get(action, "Nothing happened on the page")
            raise BrowserError(
                f"{action} {selector!r} failed: {moved['reason']}. "
                f"{untouched} - closing or dismissing the overlay, or acting on a "
                f"different element, is the next step."
            )

    def _uncover_if_occluded(self, selector: str, target) -> dict:
        """Scroll a covering header out of the way, if there is one.

        Returns a dict describing what happened, including ``reason`` when the
        element could not be uncovered - that is appended to any click failure so
        the cause names the header instead of leaving a bare timeout.

        Never clicks, types or fills. The decision to act belongs to the caller,
        which has seen whether the element was reachable.
        """
        try:
            outcome = uncover(target, selector)
        except Exception as exc:  # pragma: no cover - defensive
            # A failure here must not stop a click that would otherwise work:
            # uncovering is an optimisation, and Playwright's own actionability
            # check remains the backstop.
            return {"uncovered": True, "reason": None, "skipped": str(exc)}
        if outcome.get("error"):
            return {"uncovered": True, "skipped": outcome["error"]}
        return outcome

    def hover(self, selector: str) -> dict:
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        # Measured: a hover onto a header-covered element spent the full 10s
        # Playwright timeout and reported a call log naming no header. Hovers
        # open menus and reveal tooltips, so this is the common way an agent
        # discovers that a control exists.
        moved = self._uncover_if_occluded(selector, target)
        self._refuse_if_unreachable(selector, "hover", moved)
        try:
            target.hover(selector, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"hover {selector!r} failed: {exc}") from exc
        return self._state()

    def type(self, selector: str, text: str, delay_ms: int | None = None) -> dict:
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        delay = _type_delay_ms() if delay_ms is None else max(0, int(delay_ms))
        # Focusing a field means clicking it first, so this has exactly the same
        # exposure to a covering header as `click` does - and it matters more
        # here, because a sign-in form under a sticky header is the ordinary case
        # rather than an edge case. Measured before the change: `type` into a
        # header-covered field spent the full 10s timeout and reported a
        # Playwright call log naming no header.
        moved = self._uncover_if_occluded(selector, target)
        self._refuse_if_unreachable(selector, "type into", moved)
        try:
            target.click(selector, timeout=10000)
            self.page.keyboard.type(text, delay=delay)
        except Exception as exc:
            raise BrowserError(f"type into {selector!r} failed: {exc}") from exc
        value = self._read_value(selector, target)
        if value is None:
            raise BrowserError(f"typed into {selector!r} but could not read it back to verify")
        verified = value.strip() == text.strip()
        return {"typed": text, "value": value, "verified": verified, **self._state()}

    def fill(self, selector: str, text: str) -> dict:
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        # `fill` sets the value without clicking, so it *succeeds* on a field a
        # header is covering - measured, not assumed. That is worse than failing:
        # it reports `verified: true` for a field the user cannot see, so a
        # credential goes into an invisible box and the next `click` lands
        # somewhere else entirely. Scrolling it into view first is a no-op when
        # nothing covers it, and makes the action visible when something does.
        moved = self._uncover_if_occluded(selector, target)
        self._refuse_if_unreachable(selector, "fill", moved)
        try:
            target.fill(selector, text, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"fill {selector!r} failed: {exc}") from exc
        value = self._read_value(selector, target)
        if value is None:
            raise BrowserError(f"filled {selector!r} but could not read it back to verify")
        verified = value.strip() == text.strip()
        return {"value": value, "verified": verified, **self._state()}

    def select(self, selector: str, value: str) -> dict:
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        # Measured: `select_option` sets the value through the DOM and therefore
        # *succeeds* on a header-covered field - the same invisible-action problem
        # `fill` had. The user watching the live viewport sees a dropdown that
        # never changed, and a form submitted with a value they did not choose.
        moved = self._uncover_if_occluded(selector, target)
        self._refuse_if_unreachable(selector, "select", moved)
        try:
            values = target.select_option(selector, value, timeout=10000)
        except Exception as exc:
            raise BrowserError(f"select {selector!r}={value!r} failed: {exc}") from exc
        verified = value in (values or [])
        return {"selected": values, "verified": verified, **self._state()}

    def press(self, key: str) -> dict:
        try:
            self.page.keyboard.press(key)
        except Exception as exc:
            raise BrowserError(f"press {key!r} failed: {exc}") from exc
        return self._state()

    def go_back(self) -> dict:
        try:
            self.page.go_back()
        except Exception as exc:
            raise BrowserError(f"go_back failed: {exc}") from exc
        return self._state()

    def wait(self, ms: int = 500) -> dict:
        self.page.wait_for_timeout(ms)
        return self._state()

    def wait_for(self, selector: str, timeout_ms: int = 10000) -> dict:
        try:
            self.page.wait_for_selector(selector, timeout=timeout_ms)
        except Exception as exc:
            raise BrowserError(f"wait_for {selector!r} failed: {exc}") from exc
        return self._state()

    def scroll(self, direction: str = "down") -> dict:
        amount = "window.scrollBy(0, 800)" if direction == "down" else "window.scrollBy(0, -800)"
        self.eval(amount)
        return self._state()

    def eval(self, expression: str, reason: str | None = None) -> dict:
        """Run a JS expression in the page, with an audit record.

        This is an escape hatch, not a sandbox. The previous docstring claimed
        "read-only where possible" and nothing enforced it - arbitrary JS runs
        with full page privileges. Rather than pretend, this makes the two things
        that matter visible and checked:

        - **Irreversible JS is refused before it runs.** An expression is
          classified with the same machinery that protects a click, so
          ``fetch('/api/delete-all')`` or ``document.forms[0].submit()`` is
          stopped on the *action*, before the error - or the damage - exists.
          Classification happens from the expression text alone, so this costs
          nothing and cannot be raced.
        - **Mutation is reported, not assumed.** The DOM signature is compared
          before and after, so the caller learns whether the expression actually
          changed anything rather than having to guess.

        Every call is appended to :attr:`eval_audit`, because an agent that can
        run arbitrary JS in a logged-in page needs a record of what it ran.
        """
        irreversible, why = looks_irreversible("browse_eval", {"expression": expression})
        if irreversible:
            raise BrowserError(
                f"refusing to run this expression: {why}. It looks like a one-way "
                f"action and eval cannot be undone or retried safely. Use the "
                f"purpose-built tool instead, or rephrase if this is in fact "
                f"read-only.\n  expression: {expression[:200]}"
            )

        before = self._dom_signature()
        try:
            result = self.page.evaluate(expression)
        except Exception as exc:
            self._record_eval(expression, reason, mutated=None, ok=False, error=str(exc))
            raise BrowserError(f"eval failed: {exc}") from exc
        after = self._dom_signature()
        mutated = before != after

        self._record_eval(expression, reason, mutated=mutated, ok=True, error=None)
        return {
            "result": result,
            "mutating": mutated,
            "auditIndex": len(self.eval_audit) - 1,
            **self._state(),
        }

    def _record_eval(self, expression, reason, *, mutated, ok, error) -> None:
        """Append one entry to the audit trail."""
        self.eval_audit.append(
            {
                "at": time.time(),
                "expression": expression[:500],
                "reason": reason or "not stated",
                "mutating": mutated,
                "ok": ok,
                "error": (error or "")[:200] or None,
            }
        )
        # Bounded: an audit trail that grows without limit is a memory leak, and
        # an unbounded one is no more useful to read than the last hundred.
        if len(self.eval_audit) > self.eval_audit_limit:
            del self.eval_audit[: len(self.eval_audit) - self.eval_audit_limit]

    def eval_audit_trail(self) -> dict:
        """The eval audit, newest last. Cheap to call; meant to be read."""
        return {"count": len(self.eval_audit), "entries": list(self.eval_audit)}

    def download(self, selector: str, timeout_ms: int = 15000) -> dict:
        """Click something that triggers a download and save the file.

        Returns the saved path and the browser's suggested filename. Fails
        explicitly when no download starts, rather than reporting success because
        a click was delivered - a download that never began is the common case
        (an expired link, a permission prompt) and must not look like a win.
        """
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        # Measured before wiring: a download link under a sticky header spent
        # 10s on the click and then another 15s waiting for a download that
        # could never start, before failing with a message blaming the link.
        # The link was fine. This is the worst instance of the problem, because
        # the failure is reported as "expired link" when the cause is a header.
        moved = self._uncover_if_occluded(selector, target)
        self._refuse_if_unreachable(selector, "click to download", moved)
        try:
            with self.page.expect_download(timeout=timeout_ms) as info:
                target.click(selector, timeout=10000)
            download = info.value
        except Exception as exc:
            raise BrowserError(
                f"clicking {selector!r} did not start a download within "
                f"{timeout_ms}ms: {exc}. The link may be expired, or the site may "
                "be waiting on a permission prompt or a login."
            ) from exc

        suggested = download.suggested_filename
        target_path = Path(self._download_dir) / suggested
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(target_path))
        except Exception as exc:
            raise BrowserError(
                f"the download started as {suggested!r} but could not be saved "
                f"to {target_path}: {exc}"
            ) from exc

        size = target_path.stat().st_size if target_path.exists() else 0
        return {
            "savedTo": str(target_path),
            "filename": suggested,
            "bytes": size,
            **self._state(),
        }

    def set_files(self, selector: str, paths: list[str]) -> dict:
        """Attach files to an ``<input type=file>``.

        Fails explicitly when the target is not a file input, or a path does not
        exist. Silently attaching nothing - or attaching the wrong file - is how
        a resume goes out with the wrong attachment.
        """
        self._require_open()
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)

        if not paths:
            # set_input_files([]) succeeds and clears the field, so an empty
            # list is a real action rather than a no-op - but it is never what
            # the caller meant by "attach these files", and reporting success
            # would hide that nothing was attached.
            raise BrowserError(
                "no files given. This attaches files; an empty list would "
                "silently clear the field instead, so it is refused. Pass at "
                "least one path, or use a different tool to clear it."
            )

        resolved: list[str] = []
        for raw in paths or []:
            path = Path(raw).expanduser()
            if not path.is_file():
                raise BrowserError(
                    f"no such file: {raw!r}. Attach a real path; the contents "
                    "cannot be invented."
                )
            resolved.append(str(path.resolve()))

        # set_input_files lives on Locator, not on Page - calling it on the page
        # raises a TypeError that reads like a bad element rather than a bad call.
        locator = target.locator(selector)
        try:
            locator.set_input_files(resolved)
        except Exception as exc:
            raise BrowserError(
                f"could not attach files to {selector!r}: {exc}. The element is "
                "probably not an <input type=file>."
            ) from exc

        # Read back what the page actually holds. set_input_files silently
        # accepts a directory or a non-file, and the page can then reject it
        # later with no clue why.
        attached = []
        try:
            attached = target.eval_on_selector(
                selector,
                "el => Array.from(el.files || []).map(f => ({name: f.name, size: f.size}))",
            )
        except Exception:
            attached = None

        return {
            "attached": resolved,
            "pageSaw": attached,
            "verified": attachment_verified(attached, resolved),
            **self._state(),
        }

    # ----------------------------------------------------------------- tabs ----
    def open_tab(self, url: str) -> dict:
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"new tab to {url!r} failed: {exc}") from exc
        self.page = page
        return {"tabs": len(self._tabs()), **self._state()}

    def list_tabs(self) -> dict:
        tabs = self._tabs()
        return {
            "tabs": [
                {"index": i, "url": p.url, "title": p.title(), "active": p is self.page}
                for i, p in enumerate(tabs)
            ]
        }

    def switch_tab(self, index: int) -> dict:
        tabs = self._tabs()
        try:
            self.page = tabs[int(index)]
        except (IndexError, ValueError) as exc:
            raise BrowserError(f"no tab at index {index!r}") from exc
        return {"index": int(index), **self._state()}

    def close_tab(self, index: int) -> dict:
        tabs = self._tabs()
        try:
            page = tabs[int(index)]
        except (IndexError, ValueError) as exc:
            raise BrowserError(f"no tab at index {index!r}") from exc
        if len(tabs) == 1:
            raise BrowserError("refusing to close the last tab")
        page.close()
        self.page = self._tabs()[0]
        return {"closed": int(index), "tabs": len(self._tabs()), **self._state()}

    def _tabs(self) -> list:
        return self._context.pages if self._context else []

    # --------------------------------------------------------------- reads ----
    def snapshot(self) -> dict:
        """Outline the page, including open shadow roots and same-origin frames.

        Each frame is walked separately through Playwright's own frame API rather
        than by recursing into ``contentDocument`` from the parent. That matters:
        on a ``file://`` page every origin is opaque, so ``contentDocument`` is
        null for a frame that is in truth perfectly reachable - a same-origin
        child was being reported as cross-origin and skipped. Playwright already
        knows which frames exist and can evaluate in each one.

        Refs are namespaced per frame (``f2:e3``) because each frame numbers its
        own elements from 1, and a bare ``e3`` would be ambiguous the moment a
        page has more than one frame.
        """
        frames = []
        for n, frame in enumerate(self.page.frames):
            try:
                frames.append((n, frame, frame.evaluate(_OUTLINE_JS)))
            except Exception as exc:  # a frame that cannot be read is reported
                frames.append((n, frame, None, str(exc)[:120]))

        main = next((d for _, _, d, *rest in frames if d and not rest), None)
        if main is None:
            first = next((d for _, _, d, *_ in frames if d), None)
            if first is None:
                raise BrowserError("snapshot failed: no frame could be read")
            main = first

        items: list[dict] = []
        not_traversed: list[dict] = []
        traversed = 0
        # Playwright lists the main document first; that is the frame whose url
        # and title the snapshot reports.
        main_index = 0
        for entry in frames:
            n, frame, data = entry[0], entry[1], entry[2]
            # A cross-origin frame that failed to load - or was blocked - shows up
            # as a frame Chromium can evaluate in but which has no document, an
            # empty url, or no reachable items. Treating that as "traversed" is a
            # false all-clear: the planner would believe it had read the frame.
            if data is not None and n != main_index and not _frame_is_readable(frame, data):
                not_traversed.append(
                    {
                        "src": (frame.url or "(no url - blocked or failed to load)")[:160],
                        "name": frame.name or "",
                        "reason": (
                            "frame is cross-origin or failed to load, so its DOM is "
                            "not reachable from this page"
                        ),
                    }
                )
                continue
            if data is None:
                # A frame the browser could not give us. Reported by src and
                # reason, never silently dropped - a planner needs to know part
                # of the page is out of reach.
                not_traversed.append(
                    {
                        "src": (frame.url or "(unknown)")[:160],
                        "name": frame.name or "",
                        "reason": (
                            f"frame could not be read: {entry[3]}"
                            if len(entry) > 3
                            else "frame could not be read"
                        ),
                    }
                )
                continue
            if n != main_index:
                traversed += 1
            prefix = "" if n == main_index else f"f{n}:"
            for item in data.get("items", []):
                entry_item = dict(item)
                entry_item["ref"] = f"{prefix}{item['ref']}"
                entry_item["frame"] = n
                if n != main_index:
                    entry_item["framePath"] = [frame.name or f"frame-{n}"]
                items.append(entry_item)

        shadow_hosts = sum(
            (d.get("shadowHosts") or 0) for _, _, d, *_ in frames if d
        )
        out = {
            **main,
            "items": items,
            "truncated": main.get("truncated") or len(items) >= _OUTLINE_LIMIT,
            "iframes": _describe_frames(len(self.page.frames) - 1, traversed, not_traversed),
            "shadowDom": (
                f"{shadow_hosts} open shadow host(s) traversed"
                if shadow_hosts
                else "none"
            ),
            # Anything not walked is named here rather than quietly omitted.
            "notTraversed": not_traversed,
        }
        # Record what each ref described, so a later action can tell whether the
        # ref still means the same element.
        self._registry.record_snapshot(items)
        self._ref_frames = {i["ref"]: i.get("frame", main_index) for i in items}
        return out

    def screenshot(self) -> dict:
        try:
            png = self.page.screenshot(type="png", full_page=False)
        except Exception as exc:
            raise BrowserError(f"screenshot failed: {exc}") from exc
        return {"png_b64": base64.b64encode(png).decode("ascii")}

    def extract(self, selector: str) -> dict:
        selector = self._guard_ref(selector)
        target = self._target(selector)
        selector = self._locate(selector)
        try:
            el = target.locator(selector).first
            text = el.inner_text() if el.count() else ""
        except Exception as exc:
            raise BrowserError(f"extract {selector!r} failed: {exc}") from exc
        return {"text": text, "selector": selector, **self._state()}

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # pragma: no cover
            pass
        self._teardown_playwright()
        self._closed = True

    def _require_open(self) -> None:
        """Fail loudly and usefully if the controller was already closed.

        Without this, any action on a closed controller surfaces Playwright's
        cryptic "Event loop is closed! Is Playwright already stopped?", which
        reads like an internal bug rather than a lifecycle mistake.
        """
        if self._closed:
            raise BrowserError(
                "this browser controller is closed - construct a new one and call start() "
                "(restarting on a closed controller is not supported)"
            )
        if self.page is None:
            raise BrowserError("no active page - call start() first")

    # Context manager protocol for sync `with` statement
    def __enter__(self) -> BrowserController:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
