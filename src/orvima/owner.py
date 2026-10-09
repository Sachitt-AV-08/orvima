"""The owner's page: measured facts about this orvima install, behind a passphrase.

The approvals page is for anyone the operator hands the token to. This page is
for the operator alone: how many sessions have run, how many steps the agent has
taken, what the gate has judged and how the queue looks right now. It answers
"is this thing I leave running actually being used" without shipping anything
identifiable about *what* was browsed.

It is gated by a passphrase rather than the API token, because the token may be
shared (with a phone, with the MCP client) while these numbers are the owner's.

How the passphrase is handled, which is load-bearing:

- **The passphrase is never in the repo.** What is in the repo is a salted
  PBKDF2-HMAC-SHA256 verifier: `_VERIFIER_SALT` + `_VERIFIER_HASH`. The default
  passphrase unlocks the page because its derived key matches; nothing in the
  source or tests contains the passphrase itself.
- **It is never in a URL.** The page sends it in the `X-Orvima-Owner` header.
  URLs end up in logs and browser history; a header does not.
- **It is compared constant-time.** `hmac.compare_digest` on the derived key,
  not `==`, so a wrong guess cannot be distinguished character-by-character by
  timing.
- **`ORVIMA_OWNER_PASSPHRASE` overrides the stored verifier.** An operator who
  wants a different key sets it in the environment; no source edit required,
  and the override path is compared constant-time too.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import Counter

from fastapi.responses import HTMLResponse

#: Header the page presents the passphrase in. A custom header rather than the
#: API token header, because the two unlock different things and sharing the
#: wire would let a leaked token open the owner page too.
OWNER_HEADER = "X-Orvima-Owner"

#: PBKDF2-HMAC-SHA256 verifier for the default owner passphrase, derived at
#: release time and stored as salt + hash. 200_000 rounds, 16-byte random salt.
#: The plaintext never appears in this file.
_VERIFIER_SALT = bytes.fromhex("ac54048ede40d2d8b2cedb8dd501ffd8")
_VERIFIER_HASH = bytes.fromhex("1fc17a05a9dcb766905de0ccdefe15f677adf2c709bd6c8876fc7445573ea145")
_VERIFIER_ROUNDS = 200_000


def verify_passphrase(offered: str | None) -> bool:
    """Whether `offered` unlocks the owner page.

    An environment override wins over the stored verifier; otherwise the input
    is derived with the stored salt and compared constant-time to the stored
    hash. Blank input is rejected before any derivation work.
    """
    if not offered:
        return False
    override = os.environ.get("ORVIMA_OWNER_PASSPHRASE", "").strip()
    if override:
        return hmac.compare_digest(offered, override)
    derived = hashlib.pbkdf2_hmac(
        "sha256", offered.encode("utf-8"), _VERIFIER_SALT, _VERIFIER_ROUNDS
    )
    return hmac.compare_digest(derived, _VERIFIER_HASH)


def collect_analytics(store, gate, started: float, version: str) -> dict:
    """Measured numbers about this install, drawn from live state.

    No number here is estimated or remembered; each is counted from the data
    the process already holds. The gate payload mirrors the health endpoint so
    the two cannot disagree about whether gating is in force.
    """
    sessions = store.list()
    by_mode = Counter(s.mode for s in sessions)
    by_status = Counter(s.status for s in sessions)
    steps = 0
    rows = 0
    for s in sessions:
        rows += len(s.transcript)
        steps += sum(1 for t in s.transcript if t["kind"] == "tool_result")

    gate: dict | None = None
    if gate is not None:
        gate = {
            "available": bool(getattr(gate, "available", False)),
            "pending": len(gate.pending()),
            "stats": gate.snapshot_stats(),
        }

    return {
        "version": version,
        "uptime_seconds": round(time.time() - started),
        "sessions": {
            "total": len(sessions),
            "by_mode": dict(by_mode),
            "by_status": dict(by_status),
        },
        "steps": steps,
        "transcript_rows": rows,
        "api_token_configured": bool(os.environ.get("ORVIMA_API_TOKEN", "").strip()),
        "gate": gate,
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>orvima &middot; owner</title>
<style>
  :root {
    --bg: #0e1116; --card: #161b22; --line: #262d38; --ink: #e6edf3;
    --dim: #8b949e; --ok: #3fb950; --no: #f85149; --warn: #d29922;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f6f8fa; --card: #ffffff; --line: #d0d7de; --ink: #1f2328;
      --dim: #57606a; --ok: #1a7f37; --no: #cf222e; --warn: #9a6700;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: env(safe-area-inset-top) 1rem 2rem;
    max-width: 40rem; margin-inline: auto;
  }
  h1 { font-size: 1.1rem; margin: 1.25rem 0 .25rem; letter-spacing: .01em; }
  h1 span { color: var(--dim); font-weight: 400; }
  form#auth { margin: 1rem 0; display: flex; gap: .5rem; }
  input {
    flex: 1; padding: .7rem .8rem; font-size: 1rem; border-radius: 8px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink);
  }
  button {
    font: inherit; font-weight: 600; padding: .8rem 1.1rem; border-radius: 8px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink);
    cursor: pointer; min-height: 48px;
  }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    gap: .6rem; margin-top: 1rem;
  }
  .stat {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: .9rem 1rem;
  }
  .stat b { font-size: 1.35rem; display: block; }
  .stat span { font-size: .78rem; color: var(--dim); text-transform: uppercase;
               letter-spacing: .05em; }
  .wide { grid-column: 1 / -1; }
  dl { margin: .6rem 0 0; font-size: .88rem; display: grid;
       grid-template-columns: auto 1fr; gap: .2rem 1rem; }
  dt { color: var(--dim); }
  dd { margin: 0; text-align: right; font-family: ui-monospace, monospace; }
  #err { color: var(--no); min-height: 1.5em; margin: .5rem 0; }
  #status { color: var(--dim); font-size: .85rem; }
  p.note { font-size: .8rem; color: var(--dim); margin-top: 1.5rem;
           border-top: 1px solid var(--line); padding-top: .9rem; }
</style>
</head>
<body>
<h1>orvima <span>&middot; owner</span></h1>
<p id="status">You hold the keys to this install. Prove it.</p>

<form id="auth">
  <input id="key" type="password" autocomplete="off" autocapitalize="off"
         spellcheck="false" placeholder="owner passphrase" aria-label="owner passphrase">
  <button type="submit">Unlock</button>
</form>
<p id="err" role="alert"></p>

<div id="stats" hidden></div>

<p class="note">
  This page reports what your install has actually done &mdash; sessions, steps,
  gate decisions &mdash; never what was on the pages. Unlocked by a passphrase
  that is stored here only as a salted hash, sent only in a request header, and
  never logged.
</p>

<script>
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const node = (tag, className, text) => {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  };

  function field(dl, label, value) {
    if (value === undefined || value === null || value === "") return;
    dl.appendChild(node("dt", null, label));
    dl.appendChild(node("dd", null, value));
  }

  function render(payload) {
    el("auth").hidden = true;
    el("status").textContent = "unlocked";
    el("err").textContent = "";

    const stats = el("stats");
    stats.textContent = "";
    stats.hidden = false;

    const wrap = node("div", "grid");
    const s = payload.sessions || {};

    const sessions = node("div", "stat wide");
    sessions.appendChild(node("b", null, String(s.total ?? 0)));
    sessions.appendChild(node("span", null, "sessions"));
    const dl = node("dl");
    for (const [mode, n] of Object.entries(s.by_mode || {})) field(dl, "mode " + mode, String(n));
    for (const [status, n] of Object.entries(s.by_status || {})) field(dl, status, String(n));
    sessions.appendChild(dl);
    wrap.appendChild(sessions);

    const steps = node("div", "stat");
    steps.appendChild(node("b", null, String(payload.steps ?? 0)));
    steps.appendChild(node("span", null, "steps"));
    wrap.appendChild(steps);

    const rows = node("div", "stat");
    rows.appendChild(node("b", null, String(payload.transcript_rows ?? 0)));
    rows.appendChild(node("span", null, "transcript rows"));
    wrap.appendChild(rows);

    const uptime = node("div", "stat");
    const secs = Math.max(0, Number(payload.uptime_seconds || 0));
    const days = Math.floor(secs / 86400);
    const hours = Math.floor((secs % 86400) / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const parts = [];
    if (days) parts.push(days + "d");
    if (hours) parts.push(hours + "h");
    parts.push(mins + "m");
    uptime.appendChild(node("b", null, parts.join(" ")));
    uptime.appendChild(node("span", null, "uptime"));
    wrap.appendChild(uptime);

    const v = node("div", "stat");
    v.appendChild(node("b", null, payload.version || "?"));
    v.appendChild(node("span", null, "version"));
    wrap.appendChild(v);

    const cfg = node("div", "stat");
    cfg.appendChild(node("b", null, payload.api_token_configured ? "set" : "none"));
    cfg.appendChild(node("span", null, "api token"));
    wrap.appendChild(cfg);

    const gate = payload.gate;
    const g = node("div", "stat wide");
    if (gate) {
      const gs = gate.stats || {};
      g.appendChild(node("b", null, gate.available ? "on" : "degraded"));
      g.appendChild(node("span", null, "gate"));
      const gdl = node("dl");
      field(gdl, "pending", String(gate.pending ?? 0));
      field(gdl, "evaluated", String(gs.evaluated ?? 0));
      field(gdl, "auto-approved", String(gs.auto_approved ?? 0));
      field(gdl, "prompted", String(gs.prompted ?? 0));
      field(gdl, "approved", String(gs.approved ?? 0));
      field(gdl, "denied", String(gs.denied ?? 0));
      field(gdl, "expired", String(gs.expired ?? 0));
      field(gdl, "degraded", String(gs.degraded ?? 0));
      g.appendChild(gdl);
    } else {
      g.appendChild(node("b", null, "disabled"));
      g.appendChild(node("span", null, "gate"));
    }
    wrap.appendChild(g);

    stats.appendChild(wrap);
  }

  async function unlock(passphrase) {
    const res = await fetch("/api/owner/analytics", {
      headers: { "X-Orvima-Owner": passphrase },
    });
    if (res.status === 403) { throw new Error("wrong passphrase"); }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  el("auth").addEventListener("submit", (event) => {
    event.preventDefault();
    const key = el("key").value;
    if (!key) return;
    el("key").value = "";
    unlock(key)
      .then(render)
      .catch((e) => { el("err").textContent = e.message || "unlock failed"; });
  });
})();
</script>
</body>
</html>
"""


def owner_page() -> HTMLResponse:
    """The owner's analytics page, served by orvima itself.

    Served as one local file so unlocking the owner's dashboard does not depend
    on a third-party script.
    """
    return HTMLResponse(PAGE)
