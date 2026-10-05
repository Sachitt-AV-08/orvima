"""Cut print-ready files for the tee and the bottle.

Both are single-colour, no gradients, no second ink, no transparency tricks,
so they survive DTF (tee) and dye sublimation (bottle).

Sizes come from GetPrintX's published print areas:
  tee  Unisex Classic Round Neck, chest placement
  bottle full wrap 8.7 x 6.9 in
PNG is written at 300 DPI with a real pHYs chunk so the stated resolution is
a fact in the file rather than an assumption.
"""

from __future__ import annotations

import pathlib
import struct
import zlib

from playwright.sync_api import sync_playwright

from set_type import Face, load, wordmark

HERE = pathlib.Path(__file__).resolve().parent
DPI = 300

# Wordmark alone: no symbol. Black tee / white bottle means the ink flips to
# suit the substrate, which is the only variable that changes between the two.
FACE_NAME = "arialbd"
GAP_RATIO = 0.075

INK_ON_BLACK = "#FFFFFF"  # tee: black garment, print carries its own ink
INK_ON_LIGHT = "#000000"  # bottle: light substrate, dark ink

# Widths chosen to sit comfortably inside each print zone.
TEE_WIDTH_IN = 3.5   # chest placement, comfortably under a ~4in chest print
BOTTLE_WIDTH_IN = 6.0  # wrap is 8.7in; 6in keeps clear space at both seams


def add_phys(src: pathlib.Path, dst: pathlib.Path, dpi: int = DPI) -> None:
    """Copy a PNG, inserting a pHYs chunk so the DPI is stated in the file.

    The IDAT streams are copied byte for byte. Re-encoding the pixel data means
    either recompressing decompressed rows or concatenating zlib streams, and
    concatenating them is silently wrong: zlib stops at the first stream's end,
    so the second half of the image decodes as garbage.
    """
    raw = src.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{src.name}: not a PNG")

    ppm = int(round(dpi / 0.0254))
    phys = struct.pack(">IIB", ppm, ppm, 1)

    def chunk(typ: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + typ
            + body
            + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
        )

    out = bytearray(b"\x89PNG\r\n\x1a\n")
    pos = 8
    inserted = False
    while pos < len(raw):
        (ln,) = struct.unpack(">I", raw[pos : pos + 4])
        typ = raw[pos + 4 : pos + 8]
        body = raw[pos + 8 : pos + 8 + ln]
        crc = raw[pos + 8 + ln : pos + 12 + ln]
        if typ == b"pHYs":
            pos += 12 + ln
            continue
        if typ == b"IDAT" and not inserted:
            # pHYs must precede the first IDAT to be honoured.
            out += chunk(b"pHYs", phys)
            inserted = True
        out += struct.pack(">I", ln) + typ + body + crc
        pos += 12 + ln

    if not inserted:
        raise SystemExit(f"{src.name}: no IDAT chunk found")
    dst.write_bytes(bytes(out))


def render(svg: str, w_px: int, h_px: int, tmp: pathlib.Path) -> bytes:
    """Rasterise an SVG to RGBA PNG bytes at an exact pixel size."""
    svg_file = tmp / "art.svg"
    svg_file.write_text(svg, encoding="utf-8")
    html = tmp / "art.html"
    html.write_text(
        f'<body style="margin:0;background:transparent">'
        f'<img src="{svg_file.as_uri()}" style="display:block;width:{w_px}px;height:{h_px}px">'
        f"</body>",
        encoding="utf-8",
    )
    shot = tmp / "art.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(
            viewport={"width": w_px, "height": h_px}, device_scale_factor=1
        )
        page.goto(html.as_uri())
        page.wait_for_timeout(150)
        page.screenshot(path=str(shot), omit_background=True)
        b.close()
    return shot.read_bytes()


def check_size(path: pathlib.Path, w: int, h: int) -> None:
    """Confirm the screenshot is RGBA at exactly the size we asked for."""
    raw = path.read_bytes()
    pos = 8
    while pos < len(raw):
        (ln,) = struct.unpack(">I", raw[pos : pos + 4])
        typ = raw[pos + 4 : pos + 8]
        if typ == b"IHDR":
            sw, sh, depth, ctype = struct.unpack(">IIBB", raw[pos + 8 : pos + 18])
            if (sw, sh) != (w, h):
                raise SystemExit(f"{path.name}: {sw}x{sh}, wanted {w}x{h}")
            if depth != 8 or ctype != 6:
                raise SystemExit(f"{path.name}: depth {depth} ctype {ctype}, wanted 8/6")
            return
        pos += 12 + ln
    raise SystemExit(f"{path.name}: no IHDR")


def emit(tmp: pathlib.Path, face: Face, ink: str, width_in: float, name: str) -> tuple:
    svg, total_units, top, bottom = wordmark(face, GAP_RATIO, ink)
    aspect = total_units / (top - bottom)
    height_in = width_in / aspect
    w_px = int(round(width_in * DPI))
    h_px = int(round(height_in * DPI))

    out_png = HERE / name
    shot = tmp / "art.png"
    render(svg, w_px, h_px, tmp)
    check_size(shot, w_px, h_px)
    add_phys(shot, out_png)

    # an SVG at the same physical size, for vendors who prefer vector
    out_svg = HERE / (name.replace(".png", ".svg"))
    out_svg.write_text(svg, encoding="utf-8")

    return out_png.name, w_px, h_px, width_in, height_in


def main() -> None:
    tmp = pathlib.Path(r"C:\Users\sachi\AppData\Local\Temp\opencode\printfiles")
    tmp.mkdir(parents=True, exist_ok=True)
    face = load(FACE_NAME)

    print(f"face={FACE_NAME} gap={GAP_RATIO} dpi={DPI}\n")
    for ink, width_in, name in (
        (INK_ON_BLACK, TEE_WIDTH_IN, "orvima-tee-chest-white-300dpi.png"),
        (INK_ON_LIGHT, BOTTLE_WIDTH_IN, "orvima-bottle-wrap-black-300dpi.png"),
    ):
        fname, w, h, win, hin = emit(tmp, face, ink, width_in, name)
        print(
            f"{fname}\n  {w}x{h}px  {win:.2f} x {hin:.2f} in  ink={ink}  "
            f"aspect={win / hin:.2f}"
        )


if __name__ == "__main__":
    main()