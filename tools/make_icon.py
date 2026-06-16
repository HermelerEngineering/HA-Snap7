"""Generate the integration brand icons.

Produces a rounded-square icon with a white "S7" on a light-blue (Siemens-ish)
background. Output goes to custom_components/s7_plc/brand/ which Home Assistant
2026.3+ serves locally via the brands proxy API (no brands PR required).

Run: python tools/make_icon.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

# Light blue, in the Siemens "bright petrol" family.
BG_COLOR = (0, 166, 206, 255)
TEXT_COLOR = (255, 255, 255, 255)
TEXT = "S7"

BRAND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "s7_plc",
    "brand",
)

# A bold sans-serif; fall back across common platforms.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    raise SystemExit("No suitable bold TrueType font found.")


def make_icon(size: int, path: str) -> None:
    """Render a single square icon of ``size`` pixels (super-sampled 4x)."""
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(big * 0.18)
    draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=radius, fill=BG_COLOR)

    font = _load_font(int(big * 0.46))
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (big - tw) // 2 - bbox[0]
    ty = (big - th) // 2 - bbox[1]
    draw.text((tx, ty), TEXT, font=font, fill=TEXT_COLOR)

    img = img.resize((size, size), Image.LANCZOS)
    img.save(path)
    print(f"wrote {path} ({size}x{size})")


def main() -> None:
    os.makedirs(BRAND_DIR, exist_ok=True)
    make_icon(256, os.path.join(BRAND_DIR, "icon.png"))
    make_icon(512, os.path.join(BRAND_DIR, "icon@2x.png"))


if __name__ == "__main__":
    main()
