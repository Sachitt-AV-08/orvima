"""Draw orvima symbol marks as exact vector geometry.

Every mark shares a 100-unit grid and is built from two ingredients:
  - the letter "v" taken from a real font outline, scaled to the mark
  - plain stroked geometry for whatever holds it

Marks must survive a 16px favicon, so strokes are sized in grid units and the
inner glyph is kept small enough that the counter between the arms stays open
at small sizes. Nothing here is hand-fudged per mark; the same helpers set the
scale, the centring and the clear space.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent

GRID = 100.0
STROKE = 11.0
FACE_PATH = Path(r"C:\Windows\Fonts\ariblk.ttf")


class VGlyph:
    """A font glyph normalised for placement on the mark grid."""

    def __init__(self, char: str, path: str, bounds: tuple[int, int, int, int]):
        self.char = char
        self.path = path
        self.x0, self.y0, self.x1, self.y1 = bounds
        self.w = self.x1 - self.x0
        self.h = self.y1 - self.y0

    def place(self, height: float, cx: float, baseline: float) -> str:
        """Transform putting the glyph at `height` tall, centred on cx."""
        u = height / self.h
        left = cx - (self.w * u) / 2.0 - self.x0 * u
        return f"translate({left:.4f} {baseline:.4f}) scale({u:.5f} {-u:.5f})"


def load_glyph(char: str, path: Path = FACE_PATH) -> VGlyph:
    tt = TTFont(str(path))
    gs = tt.getGlyphSet()
    gn = tt.getBestCmap()[ord(char)]
    bp = BoundsPen(gs)
    gs[gn].draw(bp)
    sp = SVGPathPen(gs)
    gs[gn].draw(sp)
    tt.close()
    if bp.bounds is None:
        raise SystemExit(f"{char!r} has no outline")
    return VGlyph(char, sp.getCommands(), bp.bounds)


def _grid_path(v: VGlyph, height: float, cx: float, baseline: float) -> str:
    """Bake a font-unit glyph into mark-grid units as path data.

    Replays the outline through a fontTools transform pen so the y-flip and
    scale are applied by the library's own matrix maths. Parsing the `d` string
    by hand would have to guess whether each coordinate is absolute, and font
    outlines mix both.
    """
    u = height / v.h
    left = cx - (v.w * u) / 2.0 - v.x0 * u
    tt = TTFont(str(FACE_PATH))
    gs = tt.getGlyphSet()
    gn = tt.getBestCmap()[ord(v.char)]
    sp = SVGPathPen(gs)
    tp = TransformPen(sp, (u, 0, 0, -u, left, baseline))
    gs[gn].draw(tp)
    out = sp.getCommands()
    tt.close()
    return out


def _svg(body: str, colour: str, label: str, size: float = GRID) -> str:
    pad = 2.0
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} '
        f'{size + 2 * pad:.0f} {size + 2 * pad:.0f}" width="{size + 2 * pad:.0f}" '
        f'height="{size + 2 * pad:.0f}" role="img" aria-label="{label}">\n'
        f'  <title>{label}</title>\n{body}\n</svg>\n'
    )


def _fill(paths: list[str], colour: str) -> str:
    inner = "\n".join(f'    <path d="{p}"/>' for p in paths)
    return f'  <g fill="{colour}" fill-rule="nonzero">\n{inner}\n  </g>'


def _stroke(paths: list[str], colour: str, width: float = STROKE, cap: str = "butt") -> str:
    inner = "\n".join(f'    <path d="{p}"/>' for p in paths)
    return (
        f'  <g fill="none" stroke="{colour}" stroke-width="{width}" '
        f'stroke-linecap="{cap}" stroke-linejoin="miter">\n{inner}\n  </g>'
    )


def mark_brackets(v: VGlyph, colour: str) -> str:
    """[ v ] square brackets holding the v. A gate and a verdict at once."""
    body = _stroke(
        [
            "M26 22 L14 22 L14 78 L26 78",
            "M74 22 L86 22 L86 78 L74 78",
        ],
        colour,
        width=9.0,
    )
    body += "\n" + _fill([f'{v.path}" transform="{v.place(46.0, 50.0, 66.0)}'], colour).replace(
        '  <g fill', '  <g fill'
    )
    return _svg(body, colour, "orvima mark, bracketed v")


def mark_gate(v: VGlyph, colour: str) -> str:
    """v inside a square with the top-right corner left open: a gate ajar."""
    body = _stroke(
        [
            "M18 40 L18 18 L40 18",
            "M62 18 L82 18 L82 38",
            "M82 62 L82 82 L62 82",
            "M40 82 L18 82 L18 62",
        ],
        colour,
        width=9.0,
    )
    body += "\n" + _fill([f'{v.path}" transform="{v.place(46.0, 50.0, 68.0)}'], colour)
    return _svg(body, colour, "orvima mark, v in an open gate")


def mark_underbar(v: VGlyph, colour: str) -> str:
    """The v hanging under a full-width bar: held, under inspection."""
    body = _stroke(["M14 26 L86 26"], colour, width=10.0)
    body += "\n" + _fill([f'{v.path}" transform="{v.place(48.0, 50.0, 80.0)}'], colour)
    return _svg(body, colour, "orvima mark, v under a bar")


def mark_aperture(v: VGlyph, colour: str) -> str:
    """v inside a ring with a deliberate gap, so the mark is not a closed badge."""
    body = _stroke(
        ["M74.6 22.3 A36 36 0 1 0 74.6 77.7"], colour, width=9.0, cap="round"
    )
    body += "\n" + _fill([f'{v.path}" transform="{v.place(40.0, 50.0, 64.0)}'], colour)
    return _svg(body, colour, "orvima mark, v in an open ring")


def mark_corners(v: VGlyph, colour: str) -> str:
    """Corner brackets only: a viewfinder framing the v."""
    body = _stroke(
        [
            "M16 38 L16 16 L38 16",
            "M62 16 L84 16 L84 38",
            "M84 62 L84 84 L62 84",
            "M38 84 L16 84 L16 62",
        ],
        colour,
        width=9.0,
    )
    body += "\n" + _fill([f'{v.path}" transform="{v.place(44.0, 50.0, 66.0)}'], colour)
    return _svg(body, colour, "orvima mark, v in corner brackets")


def mark_tile(v: VGlyph, colour: str, tile: str) -> str:
    """App tile: filled rounded square with the v knocked out.

    The knockout must be a single path with fill-rule="evenodd" holding both
    subpaths. Two stacked paths both filled with the tile colour just paint the
    v back in and it disappears.
    """
    rect = (
        "M26 8 H74 A18 18 0 0 1 92 26 V74 A18 18 0 0 1 74 92 H26 "
        "A18 18 0 0 1 8 74 V26 A18 18 0 0 1 26 8 Z"
    )
    # The v is pre-transformed into grid units and emitted as extra subpaths of
    # the tile path, so fill-rule="evenodd" resolves the overlap as a hole. This
    # is one path and no <mask>: masks rasterise inconsistently and are widely
    # unsupported in print RIPs, whereas even-odd is core SVG 1.1.
    glyph = _grid_path(v, 44.0, 50.0, 66.0)
    body = f'  <path fill-rule="evenodd" fill="{tile}" d="{rect} {glyph}"/>'
    return _svg(body, colour, "orvima app tile")


MARKS = {
    "brackets": mark_brackets,
    "gate": mark_gate,
    "underbar": mark_underbar,
    "aperture": mark_aperture,
    "corners": mark_corners,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    ap.add_argument("--colour", default="#F5A524")
    ap.add_argument("--tile", default="#0D1117")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    v = load_glyph("v")
    print(f"v outline: w={v.w} h={v.h} (face {FACE_PATH.name})")

    for name, fn in MARKS.items():
        svg = fn(v, args.colour)
        (out / f"mk-{name}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote mk-{name}.svg  {len(svg)}B")

    tile = mark_tile(v, args.colour, args.tile)
    (out / "mk-tile.svg").write_text(tile, encoding="utf-8")
    print(f"wrote mk-tile.svg  {len(tile)}B")

    # one-colour single-ink variant: everything in one ink, no knockout needed
    mono = mark_gate(v, "#000000")
    (out / "mk-gate-mono.svg").write_text(mono, encoding="utf-8")
    print("wrote mk-gate-mono.svg")


if __name__ == "__main__":
    main()