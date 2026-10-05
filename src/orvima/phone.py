"""A phone page for the approval queue.

orvima's gate holds an irreversible action until a human answers, and that human
has to be at the laptop. So an unattended run - the thing the gate exists to make
safe - has to be attended, which is the trade the gate was supposed to remove.

This is that surface, and it is deliberately *only* that surface. It reads the
existing endpoints (`/api/approvals`, `/api/sessions/{id}/frame`, `/api/gate/stats`)
and posts a decision back. It adds no new capability and no new authority: it
cannot make orvima do anything the API did not already permit, and it cannot
approve anything the token does not already permit.

Design constraints that are load-bearing rather than stylistic:

- **No framework, no build step, no CDN.** One HTML file served by orvima
  itself. A control surface for a logged-in browser should not need to fetch
  code from a third party to decide whether to approve a purchase.
- **Nothing is rendered from page text via innerHTML.** The page text being
  judged is attacker-controlled by definition - that is the prompt-injection
  case orvima exists to survive - so every value goes in via textContent.
- **The token is never in the URL.** Not as a query parameter, not in a
  fragment. URLs end up in logs and in browser history.
- **The decision buttons are absent when there is no token.** Not disabled:
  absent. A disabled button still renders whatever the page knows.
"""

from __future__ import annotations

from fastapi.responses import HTMLResponse

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>orvima &middot; approvals</title>
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
    max-width: 34rem; margin-inline: auto;
  }
  h1 { font-size: 1.1rem; margin: 1.25rem 0 .25rem; letter-spacing: .01em; }
  h1 span { color: var(--dim); font-weight: 400; }
  #gate { font-size: .8rem; color: var(--dim); margin-bottom: 1rem; }
  #gate.bad { color: var(--warn); }
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
  button.primary { background: var(--ok); border-color: var(--ok); color: #fff; }
  button.danger  { background: var(--no);  border-color: var(--no);  color: #fff; }
  button:disabled { opacity: .5; cursor: default; }
  .card {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 1rem; margin-bottom: .85rem;
  }
  /* Light text on the saturated badge, not dark. The badge is a small block of
     colour with small bold text on it, so the pairing has to clear a real
     contrast ratio to be readable on a phone in daylight. */
  .risk {
    display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; padding: .25rem .5rem; border-radius: 4px;
    background: var(--warn); color: #fff; margin-bottom: .5rem;
  }
  .risk.destructive { background: var(--no); color: #fff; }
  .tool { font-family: ui-monospace, "Cascadia Code", monospace; font-size: .9rem; }
  .why { color: var(--dim); font-size: .9rem; margin: .4rem 0 0; }
  dl { margin: .6rem 0 0; font-size: .88rem; display: grid; gap: .3rem; }
  dt { color: var(--dim); font-size: .72rem; text-transform: uppercase;
       letter-spacing: .06em; margin-top: .35rem; }
  dd { margin: 0; word-break: break-all; font-family: ui-monospace, monospace; }
  dd.quote { font-family: inherit; font-weight: 600; }
  img.frame { width: 100%; border-radius: 8px; border: 1px solid var(--line);
              margin-top: .6rem; display: block; }
  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; margin-top: 1rem; }
  .ttl { font-size: .78rem; color: var(--dim); margin: .55rem 0 0;
         font-family: ui-monospace, "Cascadia Code", monospace; }
  .ttl.soon { color: var(--warn); }
  .ttl.gone { color: var(--no); }
  .empty { color: var(--dim); text-align: center; padding: 2.5rem 0; }
  .note { font-size: .8rem; color: var(--dim); margin-top: 1.5rem;
          border-top: 1px solid var(--line); padding-top: .9rem; }
  .locked { border-left: 3px solid var(--warn); padding-left: .8rem; color: var(--dim); }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<h1>orvima <span>&middot; approvals</span></h1>
<div id="gate">connecting&hellip;</div>

<form id="auth" hidden>
  <input id="token" type="password" autocomplete="off" autocapitalize="off"
         spellcheck="false" placeholder="API token" aria-label="API token">
  <button type="submit">Save</button>
</form>

<p class="locked" id="locked" hidden>
  This server has no API token, so it is on loopback only. Nothing here can
  approve anything &mdash; which is the correct state for a machine-reachable
  port.
</p>

<div id="queue"></div>

<p class="note">
  Held here, not approved by reflex. If an approval looks wrong, deny it and look
  at the page.
</p>

<script>
(() => {
  "use strict";

  const TOKEN_KEY = "orvima.token";
  const el = (id) => document.getElementById(id);
  const token = () => localStorage.getItem(TOKEN_KEY) || "";

  // Gate health from the last poll, so a card can work out its own deadline.
  let ttl = null;

  function duration(seconds) {
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return s + "s";
    const m = Math.floor(s / 60);
    if (m < 60) return m + "m";
    return Math.floor(m / 60) + "h " + (m % 60) + "m";
  }

  // Seconds left before this decision stops being answerable, or null when the
  // gate in force has no deadline. null is not the same as 0: 0 means "already
  // dead, take the buttons away", null means "I do not know, so leave the
  // decision to the human". Removing a control because information is missing
  // would be the same error as removing it because it is unsafe.
  function remaining(request) {
    if (typeof ttl !== "number" || ttl <= 0) return null;
    if (typeof request.created !== "number") return null;
    return ttl - (Date.now() / 1000 - request.created);
  }

  // Every value from the page under judgement goes in as textContent. The page
  // text is attacker-controlled by definition, so innerHTML is not used
  // anywhere in this file.
  function node(tag, className, text) {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function headers() {
    const t = token();
    return t ? { "X-Orvima-Token": t } : {};
  }

  async function api(path, options = {}) {
    const res = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
    if (res.status === 401) { render({ error: "token rejected" }); throw new Error("unauthorised"); }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  function field(dl, label, value, quote) {
    if (value === undefined || value === null || value === "") return;
    dl.appendChild(node("dt", null, label));
    dl.appendChild(node("dd", quote ? "quote" : null, value));
  }

  function card(request) {
    const card = node("div", "card");
    const detail = request.detail || {};

    card.appendChild(node("div", "risk " + (request.risk === "destructive" ? "destructive" : ""), request.risk));
    card.appendChild(node("div", "tool", request.tool));

    const dl = node("dl");
    // The page and the element, in that order: what am I on, and what is it
    // about to touch. A risk label alone is not enough to answer.
    field(dl, "on page", detail.page_title);
    field(dl, "url", detail.page_url);
    if (detail.element) {
      field(dl, "element", detail.element.label || detail.element.text, true);
      field(dl, "role", [detail.element.tag, detail.element.role].filter(Boolean).join(" · "));
    }
    field(dl, "arguments", Object.keys(request.args || {}).length
      ? Object.entries(request.args).map(([k, v]) => k + "=" + JSON.stringify(v)).join("  ")
      : null);
    card.appendChild(dl);

    if (request.reason) card.appendChild(node("p", "why", request.reason));

    // How long this decision is still answerable. A queued approval that has
    // already outlived its deadline cannot be approved - the gate drops it and
    // returns nothing - so showing buttons on it invites a tap that silently
    // does nothing and looks like a broken queue.
    const left = remaining(request);
    if (left !== null) {
      const label = left <= 0
        ? "expired - this decision can no longer be answered"
        : "expires in " + duration(left);
      card.appendChild(node("p", "ttl" + (left <= 0 ? " gone" : left < 30 ? " soon" : ""), label));
    }

    // The decision controls. Absent entirely unless there is a token, and
    // absent on a card that is already past its deadline.
    const dead = left !== null && left <= 0;
    if (token() && !dead) {
      const actions = node("div", "actions");
      const approve = node("button", "primary", "Approve");
      const deny = node("button", "danger", "Deny");
      approve.type = deny.type = "button";
      const decide = async (approved) => {
        approve.disabled = deny.disabled = true;
        try {
          await api("/api/approvals/" + encodeURIComponent(request.id), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approved }),
          });
        } catch (e) { /* rendered by the next refresh */ }
        poll();
      };
      approve.addEventListener("click", () => decide(true));
      deny.addEventListener("click", () => decide(false));
      actions.append(approve, deny);
      card.appendChild(actions);
    }

    return card;
  }

  function render(payload) {
    const gate = el("gate");
    if (payload.error) { gate.textContent = payload.error; gate.className = "bad"; ttl = null; }
    else {
      // Gate health arrives as sibling fields of `approvals`, not nested under
      // `gate` - `gate` itself is the status string. Reading payload.gate as an
      // object silently yields undefined for every field, which is how the
      // "gate unavailable" warning below went years without ever firing.
      const status = typeof payload.gate === "string" ? payload.gate : "?";
      const unavailable = payload.available === false;
      // A gate payload reporting no deadline must clear the cached one, or a
      // card from a later poll keeps counting down against a stale TTL.
      ttl = typeof payload.approval_ttl === "number" && payload.approval_ttl > 0
        ? payload.approval_ttl
        : null;
      gate.textContent = unavailable
        ? "gate unavailable - every action needs a human"
        : ("gate " + (payload.mode || "off") + " · " + status);
      gate.className = unavailable ? "bad" : "";
    }

    const queue = el("queue");
    queue.textContent = "";

    if (payload.approvals && payload.approvals.length) {
      for (const request of payload.approvals) queue.appendChild(card(request));
    } else {
      queue.appendChild(node("p", "empty", "Nothing waiting."));
    }

    // The token field and the explanatory note are complementary: a loopback
    // server genuinely has no buttons to show, and a token one does.
    el("auth").hidden = !!token();
    el("locked").hidden = !!token();
  }

  async function poll() {
    try { render(await api("/api/approvals?gate=1")); }
    catch (e) { /* keep the last render; the next tick retries */ }
  }

  el("auth").addEventListener("submit", (event) => {
    event.preventDefault();
    localStorage.setItem(TOKEN_KEY, el("token").value.trim());
    el("token").value = "";
    poll();
  });

  poll();
  setInterval(poll, 2500);
})();
</script>
</body>
</html>
"""


def phone_page() -> HTMLResponse:
    """The approval page.

    Served from orvima so the whole thing is one file on the machine it governs,
    with no third-party request in the path of a purchase decision.
    """
    return HTMLResponse(PAGE)
