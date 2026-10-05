"""Contact sheet for the symbol marks: every mark at every size that matters."""

from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

MARKS = [
    ("mk-gate", "open gate", "the v inside a square with one corner left open"),
    ("mk-corners", "corner brackets", "a viewfinder framing the v"),
    ("mk-brackets", "brackets", "square brackets holding the v"),
    ("mk-aperture", "open ring", "v in a ring with a deliberate gap"),
    ("mk-underbar", "under a bar", "the v hanging under a full-width bar"),
]
SIZES = [256, 64, 32, 24, 16]


def main() -> None:
    rows = []
    for stem, name, desc in MARKS:
        svg = (HERE / f"{stem}.svg").read_text(encoding="utf-8")
        scale = "".join(
            f'<div class="cell"><div class="art" style="width:{s}px">{svg}</div>'
            f"<span>{s}</span></div>"
            for s in SIZES
        )
        rows.append(
            f'<h2>{name}<small>{desc} &mdash; <code>{stem}.svg</code></small></h2>'
            f'<div class="row">{scale}</div>'
        )

    tile = (HERE / "mk-tile.svg").read_text(encoding="utf-8")
    tile_row = "".join(
        f'<div class="cell grey"><div class="art" style="width:{s}px">{tile}</div>'
        f"<span>{s}</span></div>"
        for s in (256, 64, 32)
    )

    # single-ink proof: the dye-sublimation bottle has no white ink, so one of
    # these has to survive being printed in a single ink.
    mono = (HERE / "mk-gate-mono.svg").read_text(encoding="utf-8")
    mono_row = "".join(
        f'<div class="cell light"><div class="art" style="width:{s}px">{mono}</div>'
        f"<span>{s}</span></div>"
        for s in (256, 64, 32, 16)
    )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>orvima marks</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0D1117; color:#E6EDF3; padding:36px 44px 72px;
         font:14px/1.5 ui-sans-serif,system-ui,"Segoe UI",sans-serif; }}
  h1 {{ font-size:20px; margin:0 0 6px; }}
  p.sub {{ margin:0 0 34px; color:#8B949E; max-width:70ch; }}
  h2 {{ font-size:14px; margin:34px 0 12px; font-weight:600; color:#F5A524;
        display:flex; gap:12px; align-items:baseline; flex-wrap:wrap; }}
  h2 small {{ color:#8B949E; font-weight:400; }}
  code {{ font-size:11px; }}
  .row {{ display:flex; gap:18px; align-items:flex-end; flex-wrap:wrap; }}
  .cell {{ background:#161B22; border:1px solid #30363D; border-radius:10px;
           padding:12px 14px; display:flex; flex-direction:column; align-items:center; gap:6px; }}
  .cell.grey {{ background:#8B949E; }}
  .cell.light {{ background:#fff; }}
  .art svg {{ width:100%; height:auto; display:block; }}
  span {{ font-size:11px; color:#8B949E; font-variant-numeric:tabular-nums; }}
  .cell.light span {{ color:#57606A; }}
</style></head><body>
<h1>orvima &mdash; symbol marks</h1>
<p class="sub">Every mark is the letter <code>v</code> lifted from Arial Black and
placed on a 100-unit grid, so the icon and the wordmark can never drift apart.
Shown at 256, 64, 32, 24 and 16&nbsp;px. At 16&nbsp;px the mark has to stay
readable, since that is favicon size.</p>
{"".join(rows)}
<h2>app tile<small>the practical variant for an icon file; knockout is real transparency, so it needs a background</small></h2>
<div class="row">{tile_row}</div>
<h2>single ink<small>black on white. The sublimation bottle has no white ink, so a mark must survive one ink.</small></h2>
<div class="row">{mono_row}</div>
</body></html>
"""
    out = HERE / "mark-sheet.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()