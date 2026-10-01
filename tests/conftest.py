"""Test configuration for orvima.

Adds a sibling `sentinel` checkout to `sys.path` when one is present, so the
gate tests in `test_sentinel_gate.py` exercise the real policy rather than a
stub. orvima does not depend on sentinel at runtime, so this is test-only and
the tests skip cleanly when it is absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _find_sentinel_src() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("SENTINEL_SRC")
    if env:
        candidates.append(Path(env))
    candidates.append(ROOT.parent / "sentinel" / "src")
    candidates.append(Path.home() / "agent-stack" / "sentinel" / "src")
    for candidate in candidates:
        if (candidate / "sentinel" / "policy.py").is_file():
            return candidate
    return None


_sentinel = _find_sentinel_src()
if _sentinel is not None and str(_sentinel) not in sys.path:
    sys.path.insert(0, str(_sentinel))


# --- browser isolation for the real-mode tests -------------------------------
#
# Two separate collisions made these tests fail for reasons that had nothing to
# do with the code under test:
#
# 1. Every run used the real profile at ~/.orvima/profile, which the user's own
#    Edge session also opens. Chromium then exits with code 21 - "profile in
#    use" - and the failure surfaces as a misleading "Target page, context or
#    browser has been closed".
# 2. detect_channel() auto-selects msedge when Edge is installed, so the tests
#    launched the user's browser rather than the bundled one the suite expects.
#
# Both are fixed by pointing the tests at a throwaway profile and the bundled
# Chromium. Set before any test module imports orvima.browser, because the
# profile directory is read in BrowserController.__init__.
_TEST_PROFILE = Path(os.environ.get("TEMP", ".")) / "orvima-test-profile"
os.environ.setdefault("ORVIMA_PROFILE", str(_TEST_PROFILE))
os.environ.setdefault("ORVIMA_BROWSER", "chromium")
