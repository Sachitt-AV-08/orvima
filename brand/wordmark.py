"""Draw the orvima wordmark as exact vector geometry.

Every letter is a stroked path on a 100-unit x-height grid, so one stroke weight
governs the whole word. The idea is the shared stroke: the right arm of the "v"
rises and continues as the stem of the "i", so those two letters are one
mechanism rather than two glyphs.

Geometry only. No fonts, no rasters, no network.
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

X_HEIGHT = 100.0
STROKE = 22.0
HALF = STROKE / 2.0
R_OUTER = X_HEIGHT / 2.0          # 50
R_RING = R_OUTER - HALF           # 39, path radius so outer edge lands on 0..100
SHOULDER = 28.0                   # r, m shoulder
SHOULDER_X = SHOULDER
GAP = 30.0                        # target ink gap between letters
BASELINE = X_HEIGHT


@dataclass
class Glyph:
    name: str
    parts: list[str] = field(default_factory=list)   # path `d` strings
    circles: list[tuple[float, float, float]] = field(default_factory=list)
    # ink extents in local units, measured from the path geometry
    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = BASELINE

    def width(self) -> float:
        return self.right - self.left


def _glyph(name: str, parts: list[str], circles=(), *, left, right, top=0.0, bottom=BASELINE) -> Glyph:
    return Glyph(name, list(parts), list(circles), left, right, top, bottom)


# o: a true circle, outer edge exactly 0..100 in both axes
O = _glyph("o", [], [(50.0, 50.0, R_RING)], left=0.0, right=100.0)

# r: stem, quarter-circle shoulder, short horizontal arm
R = _glyph(
    "r",
    ["M11 100 L11 28 A28 28 0 0 1 39 11 L61 11"],
    left=0.0,
    right=72.0,
)

# m: stem, two shoulders, right stem to baseline
M = _glyph(
    "m",
    ["M11 100 L11 28 A28 28 0 0 1 67 28 A28 28 0 0 1 123 28 L123 100"],
    left=0.0,
    right=134.0,
)

# a: single-storey geometric a, ring plus a straight right stem
A = _glyph("a", ["M100 0 L100 100"], [(50.0, 50.0, R_RING)], left=0.0, right=111.0)

# vi: one continuous polyline. The right arm of the v rises and turns vertical,
# becoming the stem of the i. The dot sits above it.
VI = _glyph(
    "vi",
    ["M11 0 L39 100 L60 45 L60 0"],
    [(60.0, -16.0, 11.0)],
    left=0.0,
    right=71.0,
    top=-27.0,
)

WORD = [O, R, M, A, VI]


@dataclass
class Placed:
    glyph: Glyph
    x: float


def layout(word: list[Glyph], gap: float = GAP) -> tuple[list[Placed], float]:
    """Place glyphs so consecutive ink gaps are equal, not advance widths."""
    placed: list[Placed] = []
    cursor = 0.0
    for g in word:
        placed.append(Placed(g, cursor - g.left))
        cursor += g.width() + gap
    total = cursor - gap
    return placed, total


def _svg(placed: list[Placed], total: float, height: float, *, colour: str, desc: str) -> str:
    pad = STROKE
    top = min(p.glyph.top for p in placed)
    vb_w = total + 2 * pad
    vb_h = height + 2 * pad
    body = []
    for p in placed:
        tr = f'transform="translate({p.x:.3f} 0)"'
        for d in p.glyph.parts:
            body.append(f'  <path d="{d}" transform="{tr}"/>')
        for cx, cy, r in p.glyph.circles:
            body.append(f'  <circle cx="{cx + p.x:.3f}" cy="{cy:.3f}" r="{r}"/>')
    joined = "\n".join(body)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad:.3f} {top - pad:.3f} {vb_w:.3f} {vb_h:.3f}" width="{vb_w:.3f}" height="{vb_h:.3f}" role="img" aria-label="{desc}">
  <title>{desc}</title>
  <g fill="none" stroke="{colour}" stroke-width="{STROKE}" stroke-linecap="butt" stroke-linejoin="round">
{joined}
  </g>
</svg>
"""


def wordmark_svg(colour: str = "#000000") -> str:
    placed, total = layout(WORD)
    return _svg(placed, total, X_HEIGHT + 27.0, colour=colour, desc="orvima")


def mark_svg(colour: str = "#000000") -> str:
    """The vi mechanism alone. This is what survives 16 pixels."""
    return _svg(*_one(VI), colour=colour, desc="orvima mark")


def _one(g: Glyph) -> tuple[list[Placed], float, float]:
    p = [Placed(g, 0.0)]
    return p, g.width(), (g.bottom - g.top)


def report() -> str:
    lines = []
    placed, total = layout(WORD)
    lines.append(f"stroke={STROKE}  x-height={X_HEIGHT}  target gap={GAP}")
    prev = None
    for p in placed:
        ink_l = p.x + p.glyph.left
        ink_r = p.x + p.glyph.right
        gap = None if prev is None else ink_l - prev
        lines.append(
            f"  {p.glyph.name:<3} x={p.x:8.3f}  ink=[{ink_l:8.3f},{ink_r:8.3f}]  w={p.glyph.width():7.3f}  gap={'-' if gap is None else f'{gap:.3f}'}"
        )
        prev = ink_r
    lines.append(f"  total width = {total:.3f}")
    lines.append(f"  vi dot top = {VI.top + 27:.3f} above x-height top")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()
    out = Path(args.out)
    (out / "orvima-wordmark.svg").write_text(wordmark_svg(), encoding="utf-8")
    (out / "orvima-mark.svg").write_text(mark_svg(), encoding="utf-8")
    print(report())
    print(f"\nwrote {out / 'orvima-wordmark.svg'}")
    print(f"wrote {out / 'orvima-mark.svg'}")


if __name__ == "__main__":
    main()