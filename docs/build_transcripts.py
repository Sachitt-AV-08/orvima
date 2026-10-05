"""Capture a REAL orvima run for the website.

Every byte this emits comes from actually running orvima against the built-in
demo site. Nothing here is typed by hand to look plausible, because a marketing
page whose sample output was invented is exactly the thing this project exists
to be able to disprove.

Run from docs/:  ..\\.venv\\Scripts\\python.exe build_transcripts.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
PY = REPO / ".venv" / "Scripts" / "python.exe"

# The two goals worth showing from the agent loop.
GOALS = [
    ("happy", "send a message to Acme support"),
    ("unverified", "delete everything in my account"),
]

# The page's third panel is the approval gate. This cannot come from `orvima
# run`: the demo planner stops after a snapshot and never attempts a destructive
# click, so a run here shows nothing being held -- which is why an earlier draft
# of this page captioned a plain `ok: true` transcript "held for a human". The
# gate is therefore driven directly, through the same SentinelGate the MCP server
# and the HTTP API use, so what the page shows is orvima's own decision on
# orvima's own demo page.
GATE_PROBE = {
    "goal": "delete everything in my account",
    "url": "https://acme.dev",
    "selector": "button:has-text('Delete everything')",
}


def run_demo(goal: str, steps: int = 20) -> dict:
    env = {**os.environ, "ORVIMA_SENTINEL": "off"}
    proc = subprocess.run(
        [str(PY), "-m", "orvima.cli", "run", "--mode", "demo",
         "--max-steps", str(steps), goal],
        cwd=REPO, capture_output=True, text=True, env=env, timeout=300,
    )
    text = proc.stdout + proc.stderr
    # The CLI prints a JSON result then a human transcript. Split them.
    end = text.find("\ntranscript:")
    header = json.loads(text[:end]) if end > 0 else {}
    return {"result": header, "transcript": text[end + 1:] if end > 0 else text}


def demo_snapshot(path: str) -> dict:
    """What the agent actually sees on a page, straight from DemoBrowser."""
    env = {**os.environ, "ORVIMA_SENTINEL": "off"}
    code = (
        "import json\n"
        "from orvima.demo import DemoBrowser\n"
        f"b = DemoBrowser()\n"
        f"b.navigate({path!r})\n"
        "s = b.snapshot()\n"
        "print(json.dumps(s))\n"
    )
    proc = subprocess.run([str(PY), "-c", code], cwd=REPO,
                          capture_output=True, text=True, env=env, timeout=120)
    return json.loads(proc.stdout) if proc.returncode == 0 else {"error": proc.stderr}


def gate_probe() -> dict:
    """Drive the real SentinelGate against the real demo page and record it.

    Nothing here is simulated. `make_gate` is the constructor orvima itself
    uses, and `check` is the code path every tool call goes through before it is
    allowed to run.
    """
    probe_json = json.dumps(GATE_PROBE)
    code = f"""
import json, pathlib, sys
sys.path.insert(0, {str(REPO / 'src')!r})
sys.path.insert(0, {str(REPO.parent / 'sentinel' / 'src')!r})
from orvima.demo import DemoBrowser
from orvima.sentinel_gate import make_gate

class _Risk:
    \"\"\"`request_approval` reads risk/reason off the decision object.\"\"\"
    def __init__(self, risk, reason):
        self.risk = risk
        self.reason = reason

probe = json.loads({probe_json!r})
lines = []
browser = DemoBrowser()
browser.navigate(probe['url'])
snap = browser.snapshot()
labels = [i.get('text') or i.get('label') or '' for i in snap.get('items', [])]
lines.append("  page: " + probe['url'])
lines.append("  on it: " + ', '.join(repr(l) for l in labels if l))

gate = make_gate()
lines.append("  gate available: " + repr(gate.available))
args = {{'selector': probe['selector']}}
lines.append("  step 1: browse_click(%s)" % args)
result = gate.check('browse_click', args, session_id='orvima.dev')
lines.append("      -> allowed=%s risk=%s" % (result.allowed, result.risk))
lines.append("         reason: " + result.reason)
out = {{'goal': probe['goal'], 'allowed': result.allowed, 'risk': result.risk,
       'reason': result.reason,
       'degraded': bool(getattr(result, 'degraded', False)),
       'page': probe['url'], 'args': args, 'labels': labels}}

if not result.allowed:
    rid = gate.request_approval('orvima.dev', 'browse_click', args,
                                _Risk(result.risk, result.reason))
    pend = gate.pending()
    out['pending'] = [p.public() for p in pend]
    out['request_id'] = rid
    card = pend[-1].public() if pend else {{}}
    lines.append("  step 2: the gate stops and asks")
    lines.append("      -> pending approval %s" % rid)
    lines.append("         risk shown to the human: %s" % card.get('risk'))
    lines.append("         reason shown: %s" % card.get('reason'))
    lines.append("      the click never ran.")
    out['transcript'] = '\\n'.join(lines)
else:
    out['transcript'] = '\\n'.join(lines)
    out['allowed'] = True
print(json.dumps(out))
"""
    proc = subprocess.run([str(PY), "-c", code], cwd=REPO,
                          capture_output=True, text=True, env={**os.environ, "ORVIMA_SENTINEL": "on"}, timeout=120)
    if proc.returncode != 0:
        return {"error": proc.stderr[-800:], "transcript": ""}
    data = json.loads(proc.stdout)
    return data


def main() -> int:
    if not PY.exists():
        print(f"no interpreter at {PY}", file=sys.stderr)
        return 2

    out = {
        "note": (
            "Captured by running orvima, not written by hand. "
            "The demo site (acme.dev) is fictional and built into orvima; "
            "every tool call, result and verified flag below is real output."
        ),
        "goals": {},
        "snapshots": {},
    }

    for key, goal in GOALS:
        print(f"capturing {key}: {goal}")
        out["goals"][key] = {"goal": goal, **run_demo(goal)}

    for path in ("https://acme.dev", "https://acme.dev/contact"):
        print(f"snapshot {path}")
        out["snapshots"][path] = demo_snapshot(path)

    print(f"gate probe: {GATE_PROBE['selector']}")
    out["gate"] = gate_probe()
    g = out["gate"]
    print(f"  allowed={g.get('allowed')} risk={g.get('risk')}")
    if g.get("error"):
        print(f"  ERROR: {g['error']}", file=sys.stderr)

    dest = HERE / "transcript.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    size = dest.stat().st_size
    print(f"wrote {dest} ({size} bytes)")

    for key, entry in out["goals"].items():
        result = entry.get("result", {})
        steps = result.get("steps")
        print(f"  {key}: ok={result.get('ok')} steps={steps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
