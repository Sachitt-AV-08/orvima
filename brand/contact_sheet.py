"""Build a contact sheet comparing the candidate wordmarks and marks."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from set_type import FONTS, MARK, WORD, load, mark, wordmark  # noqa: E402

BRAND = pathlib.Path(__file__).resolve().parent
OUT = BRAND / "contact-sheet.html"

FONT_LABEL = {
    "arialbd": "Arial Bold",
    "segoeuib": "Segoe UI Bold",
    "framd": "Franklin Gothic Medium",
    "ariblk": "Arial Black",
}
RATIOS = (0.055, 0.075, 0.095)


def main() -> None:
    rows = []
    for name in FONTS:
        try:
            face = load(name)
        except SystemExit:
            continue
        cells = []
        for ratio in RATIOS:
            svg, *_ = wordmark(face, ratio, "#E6EDF3")
            cells.append(
                f'<div class="cell"><div class="art">{svg}</div>'
                f'<span>{int(ratio * 1000)}</span></div>'
            )
        rows.append(
            f'<h2>{FONT_LABEL.get(name, name)}'
            f'<small>mark: {MARK!r} from the same face</small></h2>'
            f'<div class="row">{"".join(cells)}</div>'
        )

    marks = []
    for name in FONTS:
        try:
            face = load(name)
        except SystemExit:
            continue
        svg, _, _ = mark(face, "#F5A524")
        marks.append(
            f'<div class="cell"><div class="art dark">{svg}</div>'
            f'<span>{FONT_LABEL.get(name, name)}</span></div>'
        )

    # light-background proof, since ink colour must survive on white too
    light = []
    for name in ("segoeuib", "framd"):
        face = load(name)
        svg, *_ = wordmark(face, 0.075, "#0D1117")
        light.append(f'<div class="cell light"><div class="art">{svg}</div></div>')

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>orvima wordmark candidates</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0D1117; color:#E6EDF3; padding:36px 44px 72px;
         font:14px/1.5 ui-sans-serif,system-ui,"Segoe UI",sans-serif; }}
  h1 {{ font-size:20px; margin:0 0 6px; }}
  p.sub {{ margin:0 0 34px; color:#8B949E; }}
  h2 {{ font-size:14px; margin:34px 0 12px; font-weight:600; color:#F5A524;
        display:flex; gap:12px; align-items:baseline; }}
  h2 small {{ color:#8B949E; font-weight:400; }}
  .row {{ display:flex; gap:20px; align-items:flex-end; flex-wrap:wrap; }}
  .cell {{ display:flex; flex-direction:column; align-items:center; gap:6px;
           background:#161B22; border:1px solid #30363D; border-radius:10px;
           padding:14px 18px; }}
  .cell.light {{ background:#fff; }}
  .art {{ width:340px; max-width:70vw; }}
  .art.dark {{ width:150px; }}
  .art svg {{ width:100%; height:auto; display:block; }}
  span {{ font-size:11px; color:#8B949E; font-variant-numeric:tabular-nums; }}
  .sizes {{ display:flex; gap:16px; align-items:flex-end; margin-top:14px; }}
  .sizes .cell {{ padding:10px 12px; }}
</style></head><body>
<h1>orvima &mdash; wordmark candidates</h1>
<p class="sub">Set from real font outlines. Letters are spaced on even ink gaps,
not advance widths. Numbers are the gap as a fraction of x-height: lower is tighter.
Word &ldquo;{WORD}&rdquo;.</p>
{"".join(rows)}
<h2>Standalone mark <small>the letter &ldquo;{MARK}&rdquo;, identical face, so mark and word always agree</small></h2>
<div class="row">{"".join(marks)}</div>
<h2>On white <small>ink colour must hold up on light backgrounds too</small></h2>
<div class="row">{"".join(light)}</div>
</body></html>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()