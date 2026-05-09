#!/usr/bin/env python3
"""Generate placeholder PWA icons (192/512 PNG) for the FRLG type tool.

Re-run only when the icon design changes; outputs are committed in docs/icons/.
The design is intentionally minimal — dark theme background with the electric
type's yellow accent — so it's recognizable on a home screen but easy to
replace later with proper artwork.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "docs" / "icons"

BG = (31, 41, 55)        # #1f2937 — matches app topbar
ACCENT = (247, 208, 44)  # #F7D02C — ELETTRO type yellow
SUB = (236, 72, 153)     # #ec4899 — credit heart pink
TEXT = "FRLG"

# Try a chunky system font; fall back gracefully.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Avenir.ttc",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_icon(size, path):
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    # Slight rounded inner panel for a "card" feel without going full radius.
    pad = size // 12
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=size // 8,
        fill=(45, 56, 71),
    )

    # FRLG text, centered.
    font = load_font(int(size * 0.36))
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1] - size * 0.06
    draw.text((tx, ty), TEXT, fill=ACCENT, font=font)

    # Drawn heart (vector, not font glyph) as a nod to the dedication.
    hsize = size * 0.1
    cx = size / 2
    cy = size * 0.74
    # Two overlapping circles for the lobes + a triangle for the bottom.
    r = hsize / 2
    draw.ellipse((cx - r * 1.4, cy - r, cx + 0.2 * r, cy + r), fill=SUB)
    draw.ellipse((cx - 0.2 * r, cy - r, cx + r * 1.4, cy + r), fill=SUB)
    draw.polygon(
        [
            (cx - r * 1.5, cy + r * 0.2),
            (cx + r * 1.5, cy + r * 0.2),
            (cx, cy + r * 1.6),
        ],
        fill=SUB,
    )

    img.save(path, "PNG", optimize=True)
    print(f"  wrote {path.relative_to(ROOT)} ({size}x{size})")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        make_icon(size, OUT_DIR / f"icon-{size}.png")
    # Apple home-screen icon: iOS prefers 180x180 specifically.
    make_icon(180, OUT_DIR / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
