"""Undo the scroll that hides an element behind a sticky or fixed header.

Playwright scrolls an element into view before clicking, but it centres the
element (`scrollIntoViewIfNeeded`). A `position: sticky` or `position: fixed`
header stays pinned at the top of the viewport, so an element can end up under it
and stay there. Playwright then refuses to click, because the pointer would land
on the header - which is the correct refusal, but it arrives as a bare timeout
that says nothing about the header.

This is measured, not assumed. Seven constructions were tried before writing it:

  header 57px, element 977px down the page      -> Playwright re-centres and
                                                    clicks correctly
  header 180px, document with zero scroll room  -> occluded, 10s timeout, and
                                                    the error never mentions a
                                                    header
  fixed overlay across the viewport middle      -> target clicked anyway
  element near the document bottom              -> never occluded at all
  element parked under a 57px header            -> occluded, scrollable away
  sign inverted in the first implementation     -> scrolled the element *deeper*
                                                    under the header
  occlusion decided before scrolling            -> returned "clear" while the
                                                    header was still on top

The last two are the reason the geometry is checked *after* scrolling rather than
predicted from it. Predicting the outcome of a scroll and reporting that
prediction is how the false negative got in: the numbers were right and the
claim was still wrong.

So the real failure is narrow and specific: the element is occluded *and* the
page cannot be scrolled to clear it. Everything else Playwright already handles,
and this module deliberately does not duplicate that work.

Sign convention, which cost a probe to get right: scrolling the window *down*
moves page content *up*. To move a covered element down and out from under a top
bar, the page must scroll *up*, so the scroll delta is negative.
"""

from __future__ import annotations

#: Where a cleared element should sit vertically: just below the tallest pinned
#: occluder above it, or at the top of the viewport if there is none. The margin
#: keeps a sub-pixel rounding gap from putting the element back under the edge.
_CLEAR_MARGIN_PX = 4

_UNCOVER_JS = """
([selector, margin]) => {
  const el = document.querySelector(selector);
  if (!el) return {error: 'no such element'};

  const viewH = window.innerHeight;
  const viewW = window.innerWidth;
  const maxScroll = Math.max(0, document.documentElement.scrollHeight - viewH);
  const scrollY = window.scrollY;
  const elRect = el.getBoundingClientRect();

  // Which elements, if any, are painted over the target's own area.
  //
  // `elementsFromPoint` returns the whole stack under a point, so an occluder is
  // the first entry that is neither the element nor one of its ancestors or
  // descendants. Probing five points across the element catches an overlay that
  // covers only part of it, which a single centre probe would miss - and a
  // partial cover is exactly the case where a click lands on the wrong thing.
  const inset = Math.min(6, elRect.height / 2, elRect.width / 2);
  const points = [
    [elRect.x + elRect.width / 2, elRect.y + inset],
    [elRect.x + elRect.width / 2, elRect.y + elRect.height / 2],
    [elRect.x + elRect.width / 2, elRect.y + elRect.height - inset],
    [elRect.x + inset, elRect.y + elRect.height / 2],
    [elRect.x + elRect.width - inset, elRect.y + elRect.height / 2],
  ];

  // Is this node able to receive a pointer at all?
  //
  // `pointer-events: none` is the important one: such an element is transparent
  // to input, so an overlay set to none blocks nothing however large it is. It
  // is skipped rather than ending the walk, because the point is still open -
  // the node beneath it may be the target.
  const receivesPointer = (node) => {
    const cs = getComputedStyle(node);
    if (cs.pointerEvents === 'none') return null;
    if (cs.visibility === 'hidden' || cs.display === 'none') return null;
    if (Number(cs.opacity) === 0) return null;
    const r = node.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    return { cs, rect: r };
  };

  const blockers = [];
  const seen = new Set();
  for (const [x, y] of points) {
    // elementsFromPoint returns nothing outside the viewport, and reading a
    // property off that throws a TypeError inside the page which surfaces as an
    // opaque Playwright error. Points outside the viewport are skipped instead.
    if (x < 0 || y < 0 || x >= viewW || y >= viewH) continue;

    // Paint order, topmost first. The first node here that can receive a pointer
    // is where a click at this point lands - that is the browser's rule, and
    // following it removes any need to reason about z-index at all.
    //
    // Only nodes *above* the target can intercept, so the walk ends as soon as
    // it reaches the target or anything inside it. Scanning past that point is
    // what made Google's outlined-field border divs look like walls: they
    // overlap the input geometrically and sit beneath it in the stack.
    for (const node of document.elementsFromPoint(x, y) || []) {
      if (node === el || el.contains(node)) break;   // the point belongs to the element
      const info = receivesPointer(node);
      if (!info) continue;                            // see through it, keep walking
      if (seen.has(node)) break;                      // already recorded by another probe
      seen.add(node);
      const cs = info.cs;
      // Sticky and fixed elements stay put while the page moves, so they are the
      // ones a scroll can escape. An in-flow element that covers the target is a
      // different problem - a modal scrim, a cookie wall in normal flow - and
      // scrolling will not help, so it must not be lumped in with them.
      blockers.push({
        id: node.id || node.tagName.toLowerCase(),
        top: info.rect.top,
        bottom: info.rect.bottom,
        // An ancestor painted above its own child is not a separate overlay; it
        // is the same widget, and clicking it activates the child. Recorded as
        // unpinned rather than as a wall, so it cannot produce a false refusal.
        pinned: (cs.position === 'sticky' || cs.position === 'fixed')
          && !node.contains(el),
      });
      break;
    }
  }

  const state = {
    blockers: blockers.map(b => b.id),
    scrollY: Math.round(scrollY),
    maxScroll: Math.round(maxScroll),
  };

  if (blockers.length === 0) return Object.assign({occluded: false}, state);

  const pinned = blockers.filter(b => b.pinned);
  if (pinned.length === 0) {
    return Object.assign({
      occluded: true,
      scrollable: false,
      reason: 'covered by an in-flow element, which scrolling cannot clear',
    }, state);
  }

  // Pick a viewport position that clears every pinned occluder. Vertical only:
  // horizontal scrolling within a page is rare enough that handling it would
  // mostly add ways to be wrong.
  let desired = 0;
  for (const b of pinned) {
    if (b.bottom <= elRect.top + 1 || b.top >= elRect.bottom - 1) continue;
    if (b.bottom > elRect.top) desired = Math.max(desired, b.bottom + margin);
  }

  // Scrolling the window down moves content up, so putting the element at
  // `desired` when it is at `elRect.top` means scrolling by the difference.
  let delta = Math.round(elRect.top - desired);
  // Keep the element inside the viewport. After scrolling by `delta` its new
  // viewport top is `elRect.top - delta` - the scroll delta and the viewport
  // coordinate move in opposite directions. Getting this sign wrong clamps away
  // the scroll that would have worked, which is exactly the bug the live test
  // caught: scrollY moved 10px when 51 was needed.
  if (elRect.top - delta < 0) delta = Math.round(elRect.top);
  if (elRect.top - delta + elRect.height > viewH) {
    delta = Math.round(elRect.top + elRect.height - viewH);
  }

  if (delta === 0) {
    return Object.assign({
      occluded: true,
      scrollable: false,
      reason: 'the element cannot be positioned clear of the overlay in this viewport',
    }, state);
  }

  const target = Math.min(maxScroll, Math.max(0, scrollY + delta));
  const applied = target - scrollY;
  if (applied === 0) {
    // Clamped by the document's limits: occluded, and the page will not move far
    // enough. This is the measured failure case.
    return Object.assign({
      occluded: true,
      scrollable: false,
      delta: delta,
      reason: (scrollY + delta < 0
        ? 'already at the top of the page'
        : 'already at the bottom of the page') +
        '; no scroll left to clear the overlay',
    }, state);
  }

  window.scrollTo(0, target);

  // Re-probe after scrolling rather than trusting the arithmetic. The first
  // implementation returned "clear" here on the strength of the delta it had
  // computed, and reported success on a page where the header was still on top
  // of the element. A correct prediction is not a measurement.
  const moved = el.getBoundingClientRect();
  const stillCovered = pinned.some(b =>
    b.pinned && b.bottom > moved.top + 1 && b.top < moved.bottom - 1
  );

  return Object.assign({
    occluded: stillCovered,
    // Still covered after a scroll is not automatically hopeless: a second leg
    // may finish the job. Reporting it as unfixable would abandon an element
    // that one more small scroll would clear. The attempt budget bounds this.
    scrollable: stillCovered && applied !== 0,
    scrolled: Math.round(applied),
    elementTop: Math.round(moved.top),
    desiredTop: Math.round(desired),
    // No `blockers` key here: `state` is assigned last and already carries the
    // pre-scroll list, so an explicit key here would be silently overridden.
    // (It was, for a while - a mutation deleting it changed nothing and looked
    // like an untested property rather than the dead code it was.)
    reason: stillCovered
      ? 'scrolled, but the overlay still covers the element'
      : undefined,
  }, state);
}
"""


def uncover(page, selector: str, *, attempts: int = 2, margin: int = _CLEAR_MARGIN_PX) -> dict:
    """Scroll the minimum amount needed to clear `selector` of pinned overlays.

    Moves the page and reports; never clicks, types, or fills. A caller that
    cannot uncover the element is told why and which elements were in the way, so
    it can report that rather than acting on whatever happens to be on top.

    ``uncovered`` is True only when a measurement taken *after* any scrolling
    found nothing covering the element.

    `page` is anything with ``evaluate(expression, arg)`` - a Playwright Page or
    Frame. browser.py passes whichever target a selector resolved to, so an
    element inside an iframe is uncovered in that frame's own origin context. The
    in-page script reads only ``document``, ``window`` and ``getComputedStyle``,
    all of which resolve against whichever document the frame runs in.
    """
    outcome: dict = {
        "uncovered": False,
        "attempts": 0,
        "scrolled": 0,
        "cleared": [],
    }
    for attempt in range(attempts):
        outcome["attempts"] = attempt + 1
        result = page.evaluate(_UNCOVER_JS, [selector, margin])

        if isinstance(result, dict) and result.get("error"):
            return {**outcome, "uncovered": False, "error": result["error"]}

        if not result.get("occluded"):
            # Everything this pass saw, including the pre-scroll observation it
            # carried through. A one-leg recovery reports its occluder here and
            # nowhere else, so reading only `outcome` would lose it.
            for name in result.get("blockers", []):
                if name not in outcome["cleared"]:
                    outcome["cleared"].append(name)
            # Distance is the sum of every leg, including this one: a caller
            # checking whether the page moved at all needs the total, not the
            # final leg.
            return {
                **outcome,
                "uncovered": True,
                "scrolled": outcome["scrolled"] + (result.get("scrolled") or 0),
                # Nothing covers it now. Kept distinct from `cleared` so a
                # caller can tell "was never covered" from "was, and no longer
                # is" without re-reading the geometry.
                "blockers": [],
            }

        if not result.get("scrollable"):
            # Scrolling provably cannot help. Report on the first observation:
            # the geometry is fixed, so further attempts return the same answer,
            # and a late report reads as flakiness rather than as a layout that
            # makes the element unreachable.
            return {
                **outcome,
                "uncovered": False,
                "blockers": result.get("blockers", []),
                "reason": result.get("reason") or "the overlay cannot be scrolled clear",
                "scrollY": result.get("scrollY"),
                "maxScroll": result.get("maxScroll"),
            }

        # Still occluded, but scrolling moved us: remember what was in the way
        # and let the next pass try again. The attempt budget bounds this.
        seen = result.get("blockers", [])
        for name in seen:
            if name not in outcome["cleared"]:
                outcome["cleared"].append(name)
        outcome["scrolled"] += result.get("scrolled") or 0
    return outcome
