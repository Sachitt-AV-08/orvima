"""Back-print lockups for the tee.

A garment back print is not a wordmark, it is a lockup: a name line, a rule, and
a tagline set smaller and tracked out. Still set from real outlines on the same
even-ink-gap rule as the front, so the two sides read as one design.

Two coordinate spaces are in play and mixing them is the easy mistake:

* font units, y-up, inside the flip+scale group;
* viewBox units, y-down, after that transform.

Everything is laid out in font units with the name baseline at y=0, then the
viewBox is derived from the real content bbox the same way wordmark() does it.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from print_files import DPI, add_phys, check_size, render
from set_type import Face, load

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FACE_NAME = "arialbd"

# Back print area on the GetPrintX tee is 11x13 in (XS-S) to 12x15 in (M-7XL).
# 9 in sits inside every size with margin to spare.
BACK_WIDTH_IN = 9.0

NAME = "A V Sachitt"
TAGLINE = "a browser agent that shows its work"


def line(face: Face, text: str, gap_u: float) -> tuple[list[tuple[str, float]], float, float, float]:
    """Lay out one line at an even ink gap.

    Returns (ops as (path d, pen x), ink width, top, bottom) in font units with
    the baseline at y=0. A space has no outline, so it only advances the pen.
    """
    ops: list[tuple[str, float]] = []
    cursor = 0.0
    lo = hi = None
    top = bottom = None
    for ch in text:
        if ch == " ":
            cursor += face.adv(" ") + gap_u
            continue
        x0, y0, x1, y1 = face.ink(ch)
        pen = cursor - x0
        ops.append((face.path(ch), pen))
        lo = pen + x0 if lo is None else min(lo, pen + x0)
        hi = pen + x1 if hi is None else max(hi, pen + x1)
        top = y1 if top is None else max(top, y1)
        bottom = y0 if bottom is None else min(bottom, y0)
        cursor = pen + x1 + gap_u
    if lo is None:
        return [], 0.0, 0.0, 0.0
    return ops, hi - lo, top, bottom


def lockup(
    face: Face,
    name: str,
    tagline: str,
    *,
    name_gap_ratio: float = 0.075,
    tagline_ratio: float = 0.26,
    tagline_gap_ratio: float = 0.13,
    rule: bool = True,
    colour: str = "currentColor",
) -> tuple[str, float, float]:
    """Compose name, optional rule, and tagline. Returns (svg, w, h) in font units."""
    n_ops, n_w, n_top, n_bot = line(face, name, face.xh * name_gap_ratio)
    cap = n_top - n_bot

    # Vertical rhythm as fractions of cap height, so the block holds together
    # if the name or the face changes.
    to_rule = cap * 0.34
    rule_to_tag = cap * 0.52
    stroke = cap * 0.028
    half = n_w * 0.26

    body: list[str] = []
    left: list[float] = []
    right: list[float] = []
    top_edges: list[float] = [n_top]
    bottom_edges: list[float] = [n_bot]

    # name line: baseline at 0, centred on x=0
    dx = -n_w / 2.0
    for d, pen in n_ops:
        body.append(f'  <path d="{d}" transform="translate({pen + dx:.4f} 0)"/>')
    left.append(dx)
    right.append(dx + n_w)

    if rule:
        # Below the name means NEGATIVE font units: the group flips y, so a
        # positive offset here would stack the rule above the name.
        ry = -to_rule
        body.append(
            f'  <path d="M{-half:.4f} {ry:.4f} L{half:.4f} {ry:.4f}" fill="none" '
            f'stroke="{colour}" stroke-width="{stroke:.4f}"/>'
        )
        top_edges.append(ry + stroke / 2)
        bottom_edges.append(ry - stroke / 2)

    if tagline:
        t_ops, t_w, t_top, t_bot = line(face, tagline, face.xh * tagline_gap_ratio)
        # Size the tagline by cap-height ratio, not by fitting it to a width:
        # fitting to a width lets a long tagline silently shrink the type.
        scale = (cap * tagline_ratio) / (t_top - t_bot)
        base = -(to_rule + rule_to_tag)
        tdx = -(t_w * scale) / 2.0
        for d, pen in t_ops:
            # translate then scale, so the tagline's own baseline stays put.
            body.append(
                f'  <path d="{d}" transform="translate({pen * scale + tdx:.4f} '
                f'{base:.4f}) scale({scale:.5f})"/>'
            )
        left.append(tdx)
        right.append(tdx + t_w * scale)
        top_edges.append(base + t_top * scale)
        bottom_edges.append(base + t_bot * scale)

    min_x, max_x = min(left), max(right)
    top, bottom = max(top_edges), min(bottom_edges)

    # viewBox lives in the post-transform space, where y has been negated.
    unit = 100.0 / face.xh
    pad = face.xh * 0.06
    bx = (min_x - pad) * unit
    by = -(top + pad) * unit
    bw = (max_x - min_x + 2 * pad) * unit
    bh = (top - bottom + 2 * pad) * unit

    label = f"orvima, {name}"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{bx:.4f} {by:.4f} '
        f'{bw:.4f} {bh:.4f}" width="{bw:.3f}" height="{bh:.3f}" role="img" '
        f'aria-label="{label}">\n'
        f"  <title>{label}</title>\n"
        f'  <g transform="scale({unit:.6f} {-unit:.6f})" fill="{colour}" '
        f'fill-rule="nonzero">\n'
        + "\n".join(body)
        + "\n  </g>\n</svg>\n"
    )
    return svg, max_x - min_x, top - bottom


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    ap.add_argument("--name", default=NAME)
    ap.add_argument("--tagline", default=TAGLINE)
    ap.add_argument("--no-rule", action="store_true")
    ap.add_argument("--width-in", type=float, default=BACK_WIDTH_IN)
    ap.add_argument("--prefix", default="orvima-back-lockup")
    ap.add_argument(
        "--ink",
        default="white",
        choices=("white", "black"),
        help="One-ink print: white ink for a dark garment, black for a light one.",
    )
    ap.add_argument("--dry", action="store_true", help="svg only, no raster")
    args = ap.parse_args()

    face = load(FACE_NAME)
    colour = "#FFFFFF" if args.ink == "white" else "#000000"
    svg, w, h = lockup(face, args.name, args.tagline, rule=not args.no_rule, colour=colour)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.prefix}.svg").write_text(svg, encoding="utf-8")

    aspect = w / h
    height_in = args.width_in / aspect
    w_px = int(round(args.width_in * DPI))
    h_px = int(round(height_in * DPI))

    print(f"wrote {out_dir / (args.prefix + '.svg')}")
    print(
        f"name={args.name!r} tagline={args.tagline!r} rule={not args.no_rule}\n"
        f"ink={args.ink}  aspect={aspect:.2f}  {args.width_in:.2f} x {height_in:.2f} in  "
        f"({w_px}x{h_px}px @ {DPI}dpi)"
    )
    if args.dry:
        return

    import tempfile

    tmp = pathlib.Path(tempfile.gettempdir()) / "orvima_backprint"
    tmp.mkdir(exist_ok=True)
    render(svg, w_px, h_px, tmp)
    check_size(tmp / "art.png", w_px, h_px)
    png = out_dir / f"{args.prefix}-300dpi.png"
    add_phys(tmp / "art.png", png)
    print(f"wrote {png}")


if __name__ == "__main__":
    main()
