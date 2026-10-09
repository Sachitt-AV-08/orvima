/* orvima — install tabs, and the transcript replay.
 *
 * The transcripts are NOT written by hand. build_transcripts.py runs orvima for
 * real and writes transcript.json; this file only renders what came back. If the
 * fetch fails the page says so rather than showing a plausible-looking sample,
 * because a demo transcript that was typed by hand is the one thing this site
 * must never contain.
 */

"use strict";

const CMDS = {
  win: {
    cmd: "irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex",
    note: 'Installs the v0.1.6 release &mdash; 22 tools.',
  },
  unix: {
    cmd: "curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh",
    note: 'Installs the v0.1.6 release &mdash; 22 tools.',
  },
  src: {
    cmd: "git clone https://github.com/Sachitt-AV-08/orvima\ncd orvima && uv sync",
    note: "Runs from source, so you get all 22 tools on <code>main</code>.",
  },
};

/* ---------------- install tabs ---------------- */

const out = document.getElementById("installcmd");
const note = document.getElementById("installnote");
const tabs = Array.from(document.querySelectorAll(".tab"));

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    const entry = CMDS[tab.dataset.os];
    if (!entry) return;
    out.textContent = entry.cmd;
    note.innerHTML = entry.note;
  });
});

/* ---------------- transcript rendering ---------------- */

const el = (tag, className, text) => {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = String(text);
  return n;
};

/* A step line looks like:
 *   step 5: browse_click({'selector': "button:has-text('Send')"})
 *       -> ok=True {'ok': True, ..., 'verified': False}
 * The point of the whole page is that `verified` is rendered distinctly from
 * `ok`, so it gets its own span rather than being flattened into the result. */
function renderLine(raw) {
  const line = el("span", "line");
  const step = raw.match(/^(\s*)step (\d+): (\w+)\((.*)\)\s*$/);

  if (step) {
    line.appendChild(el("span", "stepno", `${step[1]}step ${step[2]}: `));
    line.appendChild(el("span", "tool", step[3]));
    line.appendChild(el("span", "meta", `(${step[4]})`));
    return line;
  }

  /* The gate panel, not the agent loop. `allowed=False` is the most important
     string on this page, so it is styled as a refusal rather than falling
     through to grey. */
  const gate = raw.match(/^(\s*)-> allowed=(True|False)\s+risk=(\w+)\s*$/);
  if (gate) {
    line.appendChild(el("span", "stepno", `${gate[1]}-> `));
    line.appendChild(el("span", gate[2] === "True" ? "ok" : "fail", `allowed=${gate[2]}`));
    line.appendChild(el("span", "meta", ` risk=${gate[3]}`));
    return line;
  }

  const res = raw.match(/^(\s*)-> (\w+)=(True|False)\s*(\{.*\})?\s*$/);
  if (res) {
    line.appendChild(el("span", "stepno", `${res[1]}-> `));
    const ok = res[2] === "ok";
    line.appendChild(el("span", ok ? "ok" : "fail", `ok=${res[3]}`));
    const payload = res[4];
    if (payload) {
      /* Pull verified out so it can be styled by meaning, not by luck. */
      const verified = payload.match(/'verified':\s*(True|False)/);
      const rest = payload.replace(/,?\s*'verified':\s*(True|False)/, "");
      line.appendChild(el("span", "meta", ` ${rest}`));
      if (verified) {
        line.appendChild(el("span", verified[1] === "True" ? "ok" : "unverified",
          ` 'verified': ${verified[1]}`));
      }
    }
    return line;
  }

  /* "risk shown to the human:" / "reason shown:" -- the card the approver gets. */
  const shown = raw.match(/^(\s*)(risk shown to the human|reason shown): (.*)$/);
  if (shown) {
    line.appendChild(el("span", "stepno", `${shown[1]}${shown[2]}: `));
    line.appendChild(el("span", "unverified", shown[3]));
    return line;
  }

  line.appendChild(el("span", /goal:|the click never ran/.test(raw) ? "tool" : "meta", raw));
  return line;
}

function paint(node, text) {
  node.textContent = "";
  for (const raw of String(text).split("\n")) {
    if (!raw.trim()) continue;
    node.appendChild(renderLine(raw));
  }
}

function failed(node, why) {
  node.textContent = "";
  node.appendChild(el("span", "fail", `transcript unavailable: ${why}`));
  node.appendChild(el("span", "meta", " (run build_transcripts.py to generate)"));
}

async function load() {
  let data;
  try {
    const res = await fetch("transcript.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    failed(document.getElementById("term-happy"), String(e.message || e));
    failed(document.getElementById("term-gate"), String(e.message || e));
    return;
  }

  const happy = data.goals && data.goals.happy;
  const gate = data.gate;

  if (happy) paint(document.getElementById("term-happy"), happy.transcript);

  if (gate && gate.transcript) {
    paint(document.getElementById("term-gate"), gate.transcript);
    /* Caption from the decision, not from prose. If a future capture ever comes
     back allowed=True, the caption must not still claim the click was stopped. */
    const foot = document.querySelector(".runner.highlight .runnerfoot");
    const count = document.querySelector(".runner.highlight .stepcount");
    if (gate.allowed === false) {
      if (count) count.textContent = "held";
      if (foot) {
        foot.innerHTML =
          "The gate read the selector, judged it <code>" +
          (gate.risk || "unknown") +
          "</code>, and stopped. The click never ran.";
      }
    } else {
      if (count) count.textContent = "allowed";
      if (foot) foot.textContent = "This capture came back allowed. Treat it as stale.";
    }
  } else {
    failed(document.getElementById("term-gate"), "no gate capture in transcript.json");
  }
}

load();

/* ---------------- difference mini terminals ---------------- */

/* The "typical" side returns plain ok: True and nothing else -- no verified
   field, because it never re-reads the DOM. That absence is the whole point
   of the pair, so this sample must not grow a verified key. */
const otherLines = [
  "step 1: browse_navigate({'url': 'https://shop.example.com/checkout'})",
  "  -> ok=True {'ok': True, 'url': 'https://shop.example.com/checkout'}",
  "step 2: browse_click({'selector': 'button:has-text(\"Place order\")'})",
  "  -> ok=True {'ok': True}",
];

const orvimaLines = [
  "step 1: browse_navigate({'url': 'https://shop.example.com/checkout'})",
  "  -> ok=True {'ok': True, 'url': 'https://shop.example.com/checkout', 'verified': True}",
  "step 2: browse_click({'selector': 'button:has-text(\"Place order\")'})",
  "  -> ok=True {'ok': True, 'verified': False, 'note': 'Button disabled; click dispatched but no navigation'}",
  "step 3: browse_snapshot({})",
  "  -> ok=True {'ok': True, 'dom': '<button disabled>Place order</button>', 'verified': False}",
  "step 4: browse_eval({'script': 'document.querySelector(\"button\").disabled'})",
  "  -> ok=True {'ok': True, 'result': true, 'verified': True, 'note': 'Confirmed button is still disabled'}",
];

function paintMini(node, lines) {
  node.textContent = "";
  for (const raw of lines) {
    if (!raw.trim()) continue;
    node.appendChild(renderLine(raw));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  /* Only the index has the difference pair; docs.html shares this script and
     must not throw for elements it never had. */
  const other = document.getElementById("term-other");
  const orvima = document.getElementById("term-orvima");
  if (other) paintMini(other, otherLines);
  if (orvima) paintMini(orvima, orvimaLines);
});

/* ---------------- scroll reveal ---------------- */

const revealObserver = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);
    }
  }
}, { threshold: 0.12, rootMargin: "0px 0px -60px 0px" });

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".reveal").forEach((el) => revealObserver.observe(el));
});