"""Bounded context for a long run.

The problem
-----------
Every planner call re-sends the whole history. That is what lets a planner
re-read what it did, but it also means the prompt grows without limit: measured
on a realistic history, 50 steps cost ~285,000 characters (~71,000 tokens) and
100 steps ~565,000. A run long enough to be interesting does not fit in a
context window, and the failure is silent - the request just gets rejected or
truncated somewhere upstream.

What is kept, and why
---------------------
- The **last N steps keep full detail.** Recent results are what a planner
  actually reasons about; an error three steps ago is still in play.
- **Older steps collapse to one line each**: the tool, its arguments, and
  whether it worked. An earlier failure is still visible as a failure, which is
  the part that changes behaviour. Its 3,000-character body is not, and that is
  what the snapshot is for.
- A hard character ceiling applies last, dropping the *oldest* lines first and
  saying so in the transcript.

The honesty part
----------------
Truncation is always announced. A planner that silently loses its own history
will conclude it never took those steps and take them again - which for an
irreversible action means acting twice. Every dropped span leaves a marker
naming how much went, so a gap is visible rather than inferred.
"""

from __future__ import annotations

from dataclasses import dataclass

#: How many recent steps keep their full result body.
DEFAULT_DETAIL_STEPS = 6

#: Hard ceiling on the rendered transcript. Roughly 30,000 tokens.
DEFAULT_MAX_CHARS = 120_000

#: Results longer than this are clipped even in the detail window. A single
#: 4,000-character result should not be able to crowd out four others.
DEFAULT_MAX_RESULT_CHARS = 1500

#: Longest error text kept in the compact form.
DEFAULT_MAX_ERROR_CHARS = 300


@dataclass
class ContextBudget:
    """How much of the history to render, and in how much detail."""

    detail_steps: int = DEFAULT_DETAIL_STEPS
    max_chars: int = DEFAULT_MAX_CHARS
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS
    max_error_chars: int = DEFAULT_MAX_ERROR_CHARS


def _clip(text: str, limit: int) -> tuple[str, bool]:
    """Trim to a limit, reporting whether anything was dropped."""
    text = str(text or "")
    if limit <= 0 or len(text) <= limit:
        return text, False
    return text[:limit], True


def compact_row(row: dict, budget: ContextBudget, redact=None) -> str:
    """One line for a step outside the detail window.

    Keeps what changes behaviour - which tool, on what, and whether it worked -
    and drops the body. An error's text is kept (clipped) because "this failed
    and here is why" is the single most useful thing to remember about an old
    step.
    """
    step = row.get("step")
    tool = row.get("tool")
    result = row.get("result") or {}
    ok = result.get("ok")
    args = row.get("args") or {}
    if redact is not None:
        args = redact(args)
        result = redact(result)

    if row.get("kind") == "error":
        error, cut = _clip(row.get("error"), budget.max_error_chars)
        return f"step {step}: error: {error}{'...' if cut else ''}"

    marker = "ok" if ok else "FAILED"
    if ok is None:
        marker = "no result"
    if args:
        # Args are short by construction; this is a backstop, not a policy.
        shown, cut = _clip(args, 200)
        return f"step {step}: {tool}({shown}) -> {marker}{'...' if cut else ''}"
    return f"step {step}: {tool} -> {marker}"


def full_row(row: dict, budget: ContextBudget, redact=None) -> str:
    """The full two-line form, for a step inside the detail window."""
    if row.get("kind") == "error":
        error, _ = _clip(row.get("error"), budget.max_result_chars)
        return f"error: {error}"

    args = row.get("args") or {}
    result = row.get("result") or {}
    if redact is not None:
        args = redact(args)
        result = redact(result)
    # items is excluded: the dedicated snapshot message carries the element
    # outline, and inlining it again here is what made each step cost thousands
    # of characters.
    compact = {k: v for k, v in result.items() if k not in ("png_b64", "items")}
    text, cut = _clip(compact, budget.max_result_chars)
    body = f"  -> ok={result.get('ok')} {text}"
    if cut:
        body += " ...[clipped]"
    return f"step {row.get('step')}: {row.get('tool')}({args})\n{body}"


def render_transcript(
    history: list[dict],
    budget: ContextBudget | None = None,
    redact=None,
) -> str:
    """Render a history into a bounded transcript.

    Three passes, in order of what is least valuable to lose:

    1. Older steps are already compact one-liners.
    2. If still over the ceiling, compact rows are dropped oldest-first. The
       detail window is never dropped - an agent that cannot see what it just
       did will do it again, which for an irreversible action means paying
       twice.
    3. If the detail window *alone* cannot fit, it is re-rendered with a smaller
       per-result limit. A budget that quietly stops being a budget is worse
       than one that clips a little harder, and the clipping is marked.

    Every pass that removes anything says so in the transcript.
    """
    budget = budget or ContextBudget()
    rows = history or []
    if not rows:
        return ""

    total = len(rows)
    detail_from = max(0, total - max(0, budget.detail_steps))
    detail_rows = rows[detail_from:]

    boundary_notice = (
        f"[{detail_from} earlier step(s) summarised as tool -> ok/FAILED; "
        "their full results are no longer shown]"
    )
    detail_texts = [full_row(row, budget, redact) for row in detail_rows]

    kept_compact: list[str] = []
    for row in rows[:detail_from]:
        kept_compact.append(compact_row(row, budget, redact))

    def assemble(compact: list[str], detail: list[str], notice: str | None) -> str:
        parts: list[str] = []
        if compact or detail_from:
            parts.append(boundary_notice)
        parts.extend(compact)
        if notice:
            parts.append(notice)
        parts.extend(detail)
        return "\n".join(parts)

    text = assemble(kept_compact, detail_texts, None)
    if len(text) <= budget.max_chars:
        return text

    # Pass 2: drop compact rows, oldest first.
    kept_compact = kept_compact[:]
    while kept_compact and len(assemble(kept_compact, detail_texts, None)) > budget.max_chars:
        kept_compact.pop(0)

    dropped = detail_from - len(kept_compact)
    ceiling_notice = (
        f"[{dropped} more of the oldest step(s) dropped entirely: over the "
        "context ceiling]"
        if dropped
        else None
    )
    text = assemble(kept_compact, detail_texts, ceiling_notice)
    if len(text) <= budget.max_chars:
        return text

    # Pass 3: the detail window alone is over budget. Re-render it with a
    # per-result limit derived from what is actually left, rather than dropping
    # the steps themselves.
    overhead = len(assemble([], [], ceiling_notice))
    per_result = max(80, (budget.max_chars - overhead) // max(1, len(detail_texts)))
    if per_result >= budget.max_result_chars:
        # Already as tight as the configured limit; nothing more to give.
        return text
    squeezed = ContextBudget(
        detail_steps=budget.detail_steps,
        max_chars=budget.max_chars,
        max_result_chars=per_result,
        max_error_chars=budget.max_error_chars,
    )
    detail_texts = [full_row(row, squeezed, redact) for row in detail_rows]
    text = assemble(kept_compact, detail_texts, ceiling_notice)
    return text


def measure(parts: list[str]) -> dict:
    """A size report, so the bound is a measured number rather than a claim."""
    text = "".join(p or "" for p in parts)
    return {
        "chars": len(text),
        # Deliberately a rough ratio, stated as rough.
        "approxTokens": len(text) // 4,
        "parts": len([p for p in parts if p]),
    }
