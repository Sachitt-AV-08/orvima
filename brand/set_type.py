"""Set the orvima wordmark from real font outlines.

Uses fontTools to extract glyph paths, then composes SVG with explicit ink-gap
spacing (not advance widths, which leave uneven colour). The standalone mark is
the same font's "v", so mark and wordmark are guaranteed consistent.

Outputs real SVG paths. No rasters, no fonts embedded, no network.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent

FONTS = {
    "arialbd": Path(r"C:\Windows\Fonts\arialbd.ttf"),
    "segoeuib": Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    "framd": Path(r"C:\Windows\Fonts\framd.ttf"),
    "ariblk": Path(r"C:\Windows\Fonts\ariblk.ttf"),
}

WORD = "orvima"
MARK = "v"

# Load a full printable ASCII set, not just the letters in WORD. The back-print
# lockups need capitals and spaces, and a missing glyph should fail loudly here
# rather than render as a hole on a garment.
CHARS = set(
    WORD
    + MARK
    + " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    + "abcdefghijklmnopqrstuvwxyz"
    + "0123456789.,:;-_/'&+"
)


@dataclass
class Face:
    name: str
    upem: int
    glyphs: dict
    advances: dict
    bounds: dict
    paths: dict
    cap: float
    xh: float

    def path(self, ch: str) -> str:
        return self.paths[ch]

    def adv(self, ch: str) -> float:
        return self.advances[ch]

    def ink(self, ch: str):
        return self.bounds[ch]


def load(name: str) -> Face:
    p = FONTS[name]
    if not p.exists():
        raise SystemExit(f"font missing: {p}")
    tt = TTFont(str(p))
    cmap = tt.getBestCmap()
    gs = tt.getGlyphSet()
    upem = tt["head"].unitsPerEm
    os2 = tt["OS/2"]

    advances, bounds, paths = {}, {}, {}
    for ch in CHARS:
        gn = cmap.get(ord(ch))
        if gn is None:
            raise SystemExit(f"{name} lacks {ch!r}")
        bp = BoundsPen(gs)
        gs[gn].draw(bp)
        sp = SVGPathPen(gs)
        gs[gn].draw(sp)
        advances[ch] = tt["hmtx"][gn][0]
        bounds[ch] = bp.bounds
        paths[ch] = sp.getCommands()
        # A glyph with no bounds is not necessarily missing: whitespace is
        # legitimately blank. Only reject a blank glyph that has no advance,
        # which would mean the cmap entry resolved to nothing at all.
        if bp.bounds is None and advances[ch] == 0:
            raise SystemExit(f"{name}: {ch!r} has no outline and no advance")

    face = Face(
        name=name,
        upem=upem,
        glyphs={c: cmap[ord(c)] for c in set(WORD + MARK)},
        advances=advances,
        bounds=bounds,
        paths=paths,
        cap=getattr(os2, "sCapHeight", upem * 0.72),
        xh=getattr(os2, "sxHeight", upem * 0.52),
    )
    tt.close()
    return face


def place(face: Face, word: str, gap: float):
    """Place glyphs so consecutive INK gaps are exactly `gap` font units."""
    out = []
    cursor = 0.0
    for ch in word:
        x0, y0, x1, y1 = face.ink(ch)
        pen = cursor - x0
        out.append((ch, pen))
        cursor = pen + x1 + gap
    total = cursor - gap
    return out, total


def _wrap(body: list[str], colour: str, box: tuple[float, float, float, float], unit: float, label: str) -> str:
    """Emit an SVG whose paths stay in raw font units under one flip+scale.

    Glyph outlines are y-up in font units; SVG is y-down. Applying
    scale(unit, -unit) to a single group keeps both axes in font units inside
    the group, so there is no per-axis arithmetic to get wrong.
    """
    x, y, w, h = box
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.4f} {y:.4f} {w:.4f} {h:.4f}" '
        f'width="{w:.3f}" height="{h:.3f}" role="img" aria-label="{label}">\n'
        f'  <title>{label}</title>\n'
        f'  <g transform="scale({unit:.6f} {-unit:.6f})" fill="{colour}" fill-rule="nonzero">\n'
        + "\n".join(body)
        + "\n  </g>\n</svg>\n"
    )


def wordmark(face: Face, gap_ratio: float, colour: str) -> tuple[str, float, float, float]:
    """gap_ratio is a fraction of x-height, so spacing scales with the face."""
    gap = face.xh * gap_ratio
    placed, total = place(face, WORD, gap)
    unit = 100.0 / face.xh
    pad = face.xh * 0.12

    body = []
    min_x, max_x = None, None
    top, bottom = None, None
    for ch, pen in placed:
        x0, y0, x1, y1 = face.ink(ch)
        body.append(f'  <path d="{face.path(ch)}" transform="translate({pen:.4f} 0)"/>')
        lo, hi = pen + x0, pen + x1
        min_x = lo if min_x is None else min(min_x, lo)
        max_x = hi if max_x is None else max(max_x, hi)
        top = y1 if top is None else max(top, y1)
        bottom = y0 if bottom is None else min(bottom, y0)

    # viewBox lives in the post-transform space, where y has been negated.
    bx = (min_x - pad) * unit
    by = -(top + pad) * unit
    bw = (max_x - min_x + 2 * pad) * unit
    bh = (top - bottom + 2 * pad) * unit
    svg = _wrap(body, colour, (bx, by, bw, bh), unit, "orvima")
    return svg, total, top, bottom


def mark(face: Face, colour: str) -> tuple[str, float, float]:
    ch = MARK
    x0, y0, x1, y1 = face.ink(ch)
    unit = 100.0 / face.xh
    pad = face.xh * 0.06
    body = [f'  <path d="{face.path(ch)}"/>']
    bx = (x0 - pad) * unit
    by = -(y1 + pad) * unit
    bw = (x1 - x0 + 2 * pad) * unit
    bh = (y1 - y0 + 2 * pad) * unit
    svg = _wrap(body, colour, (bx, by, bw, bh), unit, "orvima")
    return svg, (x1 - x0) * unit, (y1 - y0) * unit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    report = []
    for name in FONTS:
        try:
            face = load(name)
        except SystemExit as exc:
            report.append(f"{name}: {exc}")
            continue
        for ratio in (0.055, 0.075, 0.095):
            svg, total, top, bottom = wordmark(face, ratio, "#000000")
            tag = f"{name}-{int(ratio * 1000):03d}"
            (out / f"wm-{tag}.svg").write_text(svg, encoding="utf-8")
            g = top - bottom
            report.append(
                f"{tag}: ink {total / face.upem:.3f}em  cap {g / face.upem:.3f}em  "
                f"gap {face.xh * ratio:.0f}u  ratio {total / g:.2f}"
            )
        msvg, mw, mh = mark(face, "#000000")
        (out / f"mark-{name}.svg").write_text(msvg, encoding="utf-8")
        report.append(f"mark-{name}: {mw:.1f}x{mh:.1f} units, w/h {mw / mh:.2f}")

    print("\n".join(report))
    print(f"\nwrote to {out}")


if __name__ == "__main__":
    main()