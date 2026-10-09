"""The control dashboard: watch the agent live, pause it, approve actions.

The phone page is the approval queue for the moment a run blocks. This is the
surface for the whole run: every session, a live viewport of the selected one
streamed at ~1 fps over SSE, its transcript as it happens, and pause / resume /
cancel. The approval queue is here too, so the operator does not need to switch
surfaces to answer a held action.

It inherits the phone page's load-bearing constraints, because the same things
that make an approvals surface safe make a control surface safe:

- **No framework, no build step, no CDN.** One HTML file served by orvima
  itself. A control surface for a logged-in browser should not need code from a
  third party to decide whether to approve a purchase.
- **Nothing is rendered from page text via innerHTML.** Transcript rows can
  carry the text of pages the agent was browsing - attacker-controlled by
  definition - so every value goes in via textContent.
- **The token is never in the URL.** Not as a query parameter, not in a
  fragment. URLs end up in logs and in browser history.
- **The acting controls are absent when there is no token.** Not disabled:
  absent. Pause, resume, cancel and approve all drive a real browser, so they
  render no buttons unless the operator has presented the token.

The one thing this page adds over the API is that the final approval calls a
server endpoint that reads *both* the token and the live queue - the page never
calls the gate directly, because a control surface that can answer a held action
without the operator knowing what it is would be worse than no surface.
"""

from __future__ import annotations

from fastapi.responses import HTMLResponse

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>orvima &middot; control</title>
<style>
  :root {
    --bg: #0e1116; --card: #161b22; --line: #262d38; --ink: #e6edf3;
    --dim: #8b949e; --ok: #3fb950; --no: #f85149; --warn: #d29922;
    --accent: #F5A524;
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
  }
  h1 { font-size: 1.1rem; margin: 1.25rem 0 .25rem; letter-spacing: .01em; }
  h1 span { color: var(--dim); font-weight: 400; }
  h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em;
       color: var(--dim); margin: 1.4rem 0 .5rem; }
  form#auth { margin: .75rem 0 1rem; display: flex; gap: .5rem; max-width: 30rem; }
  input, select, textarea {
    padding: .7rem .8rem; font-size: 1rem; border-radius: 8px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink);
  }
  input, select { flex: 1; min-width: 0; }
  textarea { width: 100%; resize: vertical; margin-bottom: .5rem; }
  button {
    font: inherit; font-weight: 600; padding: .8rem 1.1rem; border-radius: 8px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink);
    cursor: pointer; min-height: 48px;
  }
  button.primary { background: var(--accent); border-color: var(--accent); color: #0d1117; }
  button.ghost { background: transparent; }
  button.danger { background: var(--no); border-color: var(--no); color: #fff; }
  button.small { min-height: 44px; padding: .5rem .8rem; font-size: .9rem; }
  button:disabled { opacity: .5; cursor: default; }
  .layout { display: grid; grid-template-columns: 24rem 1fr; gap: 1.2rem;
            align-items: start; }
  @media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
           padding: 1rem; }
  ul#sessions { list-style: none; margin: .5rem 0 0; padding: 0; max-height: 40vh;
                overflow-y: auto; }
  li.session { padding: .6rem .7rem; border: 1px solid var(--line); border-radius: 8px;
               margin-bottom: .4rem; cursor: pointer; display: grid; gap: .1rem; }
  li.session:hover { border-color: var(--dim); }
  li.session.active { border-color: var(--accent); }
  li.session .id { font-family: ui-monospace, "Cascadia Code", monospace;
                   font-size: .8rem; color: var(--dim); }
  li.session .meta { font-size: .85rem; display: flex; justify-content: space-between;
                     gap: .5rem; }
  .status { font-size: .85rem; color: var(--dim); }
  .status .dot { display: inline-block; width: .6rem; height: .6rem; border-radius: 50%;
                 background: var(--dim); margin-right: .4rem; vertical-align: 1px; }
  .status.running .dot { background: var(--ok); }
  .status.awaiting_approval .dot { background: var(--warn); }
  .status.paused .dot, .status.cancelled .dot { background: var(--no); }
  img.frame { width: 100%; border-radius: 8px; border: 1px solid var(--line);
              background: var(--bg); aspect-ratio: 16/9; object-fit: contain; }
  .controls { display: flex; gap: .5rem; margin: .75rem 0; flex-wrap: wrap; }
  ol#transcript { list-style: none; margin: .75rem 0 0; padding: 0; max-height: 45vh;
                  overflow-y: auto; font-size: .85rem; }
  ol#transcript li { border-left: 2px solid var(--line); padding: .3rem .7rem;
                     margin-bottom: .3rem; word-break: break-word; }
  ol#transcript li .k { color: var(--dim); font-family: ui-monospace, monospace;
                        font-size: .75rem; text-transform: uppercase; }
  ol#transcript li .t { color: var(--ink); }
  .locked { border-left: 3px solid var(--warn); padding-left: .8rem; color: var(--dim); }
  .empty { color: var(--dim); text-align: center; padding: 2rem 0; }
  #queue .card { background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
                 padding: .8rem; margin-bottom: .6rem; }
  #queue .card .head { display: flex; justify-content: space-between; gap: .5rem; }
  #queue .tool { font-family: ui-monospace, "Cascadia Code", monospace; font-size: .85rem; }
  #queue .risk { font-size: .68rem; font-weight: 700; letter-spacing: .06em;
                 text-transform: uppercase; padding: .2rem .45rem; border-radius: 4px;
                 background: var(--warn); color: #fff; }
  #queue .risk.destructive { background: var(--no); }
  #queue dl { margin: .5rem 0 0; font-size: .78rem; display: grid; gap: .15rem; }
  #queue dt { color: var(--dim); text-transform: uppercase; font-size: .68rem;
              letter-spacing: .05em; }
  #queue dd { margin: 0; word-break: break-all; }
  #queue dd.quote { font-family: inherit; font-weight: 600; }
  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-top: .6rem; }
  #err { color: var(--no); min-height: 1.4em; font-size: .85rem; }
  #stats { color: var(--dim); font-size: .85rem; margin-bottom: .75rem; }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<h1>orvima <span>&middot; control</span></h1>
<p id="stats">connecting&hellip;</p>

<form id="auth" hidden>
  <input id="token" type="password" autocomplete="off" autocapitalize="off"
         spellcheck="false" placeholder="API token" aria-label="API token">
  <button type="submit">Save</button>
</form>

<p class="locked" id="locked" hidden>
  This server has no API token, so it is on loopback only. You can watch, but
  nothing here can pause, cancel or approve &mdash; which is the correct state
  for a machine-reachable port.
</p>
<p id="err" role="alert"></p>

<div class="layout">
  <aside>
    <h2>New session</h2>
    <form id="create">
      <select id="mode" aria-label="mode">
        <option value="real">real browser</option>
        <option value="demo">offline demo</option>
      </select>
      <input id="start_url" type="text" placeholder="start url (optional)"
             aria-label="start url">
      <textarea id="goal" rows="2" placeholder="goal, e.g. summarize the top HN story"
                aria-label="goal"></textarea>
      <button type="submit" class="primary">Start</button>
    </form>

    <h2>Sessions</h2>
    <ul id="sessions"></ul>

    <h2>Approvals</h2>
    <div id="queue"></div>
  </aside>

  <section>
    <h2>Live view</h2>
    <p class="status" id="status"><span class="dot"></span>none selected</p>
    <img id="frame" class="frame" alt="live viewport">
    <div class="controls" id="controls" hidden></div>
    <h2>Transcript</h2>
    <ol id="transcript"><li class="empty">Select a session to watch it live.</li></ol>
  </section>
</div>

<script>
(() => {
  "use strict";

  const TOKEN_KEY = "orvima.token";
  const el = (id) => document.getElementById(id);
  const token = () => localStorage.getItem(TOKEN_KEY) || "";
  const buf = [];
  let current = null;   // selected session id
  let es = null;        // active EventSource
  let ttl = null;       // gate deadline for the approval cards

  // Every value that could have come from a page the agent was browsing goes in
  // as textContent. innerHTML is not used anywhere in this file.
  function node(tag, className, text) {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function headers(extra) {
    const h = {};
    const t = token();
    if (t) h["X-Orvima-Token"] = t;
    if (extra) Object.assign(h, extra);
    return h;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, { ...options, headers: headers(options.headers) });
    if (res.status === 401) { el("err").textContent = "token rejected"; throw new Error("unauthorised"); }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  function duration(seconds) {
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return s + "s";
    const m = Math.floor(s / 60);
    if (m < 60) return m + "m";
    return Math.floor(m / 60) + "h " + (m % 60) + "m";
  }

  // ------------------------------------------------------------------ sessions

  function renderSessions(payload) {
    const list = el("sessions");
    list.textContent = "";
    if (!payload.sessions || !payload.sessions.length) {
      list.appendChild(node("li", "empty", "No sessions yet."));
      return;
    }
    for (const s of payload.sessions) {
      const li = node("li", "session" + (s.id === current ? " active" : ""));
      li.appendChild(node("div", "id", s.id + " · " + s.mode));
      const meta = node("div", "meta");
      meta.appendChild(node("span", null, s.status));
      meta.appendChild(node("span", null, s.steps + " steps"));
      li.appendChild(meta);
      li.addEventListener("click", () => select(s.id));
      list.appendChild(li);
    }
  }

  async function refreshSessions() {
    try { renderSessions(await api("/api/sessions")); }
    catch (e) { /* keep the last list; next tick retries */ }
  }

  // ----------------------------------------------------------------- live view

  function describe(row) {
    // A compact one-line rendering of a transcript row: kind, then the scalar
    // fields that carry the story (tool, step, note, error, result summary).
    const parts = [row.kind];
    for (const k of ["tool", "step", "risk", "note", "reason", "error"]) {
      const v = row[k];
      if (v !== undefined && v !== null && v !== "") parts.push(String(v));
    }
    if (row.result && typeof row.result === "object") {
      try { parts.push(JSON.stringify(row.result).slice(0, 240)); }
      catch (e) { /* non-serialisable */ }
    }
    return parts.join("  ");
  }

  function select(id) {
    if (current === id) return;
    current = id;
    if (es) { es.close(); es = null; }
    el("transcript").textContent = "";
    el("frame").removeAttribute("src");
    el("status").textContent = "";
    el("status").className = "status";
    el("status").appendChild(node("span", "dot", ""));
    el("status").appendChild(node("span", null, "connecting…"));
    el("status").appendChild(document.createTextNode(" " + id));
    refreshSessions();

    es = new EventSource("/api/sessions/" + encodeURIComponent(id) + "/events");
    es.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch (e) { return; }
      if (data.type === "log" && data.row) {
        const row = data.row;
        const li = node("li");
        li.appendChild(node("span", "k", row.kind || "log"));
        li.appendChild(node("span", "t", " " + describe(row)));
        const list = el("transcript");
        const empty = list.querySelector(".empty");
        if (empty) empty.remove();
        list.appendChild(li);
      } else if (data.type === "frame" && data.png_b64) {
        el("frame").src = "data:image/png;base64," + data.png_b64;
      } else if (data.type === "status") {
        setStatus(data.status || "idle");
      }
    };
    es.onerror = () => { /* EventSource retries; the connection drop is normal
                            when a run finishes and closes the stream. */ };
  }

  function setStatus(status) {
    const s = el("status");
    s.textContent = "";
    const live = ["running", "paused", "cancelled", "awaiting_approval"];
    s.className = "status" + (live.includes(status) ? " " + status : "");
    s.appendChild(node("span", "dot", ""));
    s.appendChild(node("span", null, status));
    if (current) s.appendChild(document.createTextNode(" " + current));
  }

  // ---------------------------------------------------------------- controls

  // The acting controls are built only when a token is present, and torn down
  // when it is not - absent, not disabled, so a machine-reachable port renders
  // nothing that can drive the agent. This is the same bar as the approvals
  // surface: a control that cannot work must not look like one that can.
  function buildControls() {
    const wrap = el("controls");
    wrap.textContent = "";
    const button = (id, cls, label, action) => {
      const b = node("button", cls, label);
      b.type = "button";
      b.id = id;
      b.addEventListener("click", () => act(action));
      wrap.appendChild(b);
    };
    button("pause", "ghost", "Pause", "pause");
    button("resume", "ghost", "Resume", "resume");
    button("cancel", "danger", "Cancel", "cancel");
  }

  async function act(action) {
    if (!current || !token()) return;
    try {
      const r = await api("/api/sessions/" + encodeURIComponent(current) + "/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setStatus(r.status);
    } catch (e) { /* next poll shows the truth */ }
  }

  // ----------------------------------------------------------------- approvals

  function remaining(request) {
    if (typeof ttl !== "number" || ttl <= 0) return null;
    if (typeof request.created !== "number") return null;
    return ttl - (Date.now() / 1000 - request.created);
  }

  function field(dl, label, value, quote) {
    if (value === undefined || value === null || value === "") return;
    dl.appendChild(node("dt", null, label));
    dl.appendChild(node("dd", quote ? "quote" : null, value));
  }

  function queueCard(request) {
    const card = node("div", "card");
    const head = node("div", "head");
    head.appendChild(node("span", "tool", request.tool));
    head.appendChild(node("span", "risk" + (request.risk === "destructive" ? " destructive" : ""), request.risk));
    card.appendChild(head);

    const dl = node("dl");
    const detail = request.detail || {};
    field(dl, "on page", detail.page_title);
    field(dl, "url", detail.page_url);
    if (detail.element) {
      field(dl, "element", detail.element.label || detail.element.text, true);
      field(dl, "role", [detail.element.tag, detail.element.role].filter(Boolean).join(" · "));
    }
    card.appendChild(dl);
    if (request.reason) card.appendChild(node("p", null, request.reason));

    const left = remaining(request);
    if (left !== null && left <= 0) {
      card.appendChild(node("p", null, "expired - no longer answerable"));
    } else if (token()) {
      const actions = node("div", "actions");
      const approve = node("button", "small primary", "Approve");
      const deny = node("button", "small danger", "Deny");
      approve.type = deny.type = "button";
      const decide = async (approved) => {
        approve.disabled = deny.disabled = true;
        try {
          await api("/api/approvals/" + encodeURIComponent(request.id), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approved }),
          });
        } catch (e) { /* next poll shows the truth */ }
        pollApprovals();
      };
      approve.addEventListener("click", () => decide(true));
      deny.addEventListener("click", () => decide(false));
      actions.append(approve, deny);
      card.appendChild(actions);
    }
    return card;
  }

  async function pollApprovals() {
    try {
      const payload = await api("/api/approvals?gate=1");
      const queue = el("queue");
      queue.textContent = "";
      if (typeof payload.available === "boolean" && !payload.available) {
        queue.appendChild(node("p", "empty", "gate unavailable - every action needs a human"));
      } else if (payload.approvals && payload.approvals.length) {
        for (const r of payload.approvals) queue.appendChild(queueCard(r));
      } else {
        queue.appendChild(node("p", "empty", "Nothing waiting."));
      }
      ttl = typeof payload.approval_ttl === "number" && payload.approval_ttl > 0
        ? payload.approval_ttl : null;
    } catch (e) { /* keep the last queue */ }
  }

  // ---------------------------------------------------------------- plumbing

  function applyToken() {
    const t = !!token();
    el("auth").hidden = t;
    el("locked").hidden = t;
    const controls = el("controls");
    controls.textContent = "";
    controls.hidden = !t;
    if (t) buildControls();
    if (t) el("err").textContent = "";
  }

  el("auth").addEventListener("submit", (event) => {
    event.preventDefault();
    localStorage.setItem(TOKEN_KEY, el("token").value.trim());
    el("token").value = "";
    applyToken();
    pollApprovals();
  });

  el("create").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const body = {
        mode: el("mode").value,
        start_url: el("start_url").value.trim(),
        goal: el("goal").value.trim(),
      };
      const r = await api("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      el("start_url").value = "";
      el("goal").value = "";
      select(r.session.id);
      await refreshSessions();
    } catch (e) { el("err").textContent = e.message || "create failed"; }
  });

  (async () => {
    applyToken();
    try {
      const health = await api("/api/health");
      el("stats").textContent = "orvima " + (health.version || "?") + " · " +
        (health.sessions || 0) + " session(s)";
    } catch (e) { el("stats").textContent = "server not reachable"; }
    refreshSessions();
    pollApprovals();
    setInterval(refreshSessions, 3000);
    setInterval(pollApprovals, 2500);
  })();
})();
</script>
</body>
</html>
"""


def dashboard_page() -> HTMLResponse:
    """The control dashboard, served by orvima itself.

    One local file: watching a logged-in browser must not depend on a third
    party, and neither should pausing it or answering a held action.
    """
    return HTMLResponse(PAGE)
