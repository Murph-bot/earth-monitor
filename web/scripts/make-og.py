"""Render web/public/og.png (1200x630) to the brief's OG spec.

Usage (from backend/, which has Pillow):
  uv run python ../web/scripts/make-og.py [path/to/Inter.ttf]
The hex map is a stylised Thessaly in the s0-s5 scale, not data.
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, SAFE = 1200, 630, 60
BG, TEXT, MUTED = "#09090b", "#f4f4f5", "#a1a1aa"
SCALE = ["#9a5c16", "#b7791f", "#d6c25a", "#8fbf5a", "#3f9e6e", "#14837d"]
FONT = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"
)
OUT = Path(__file__).parents[1] / "public" / "og.png"


def font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        axes = f.get_variation_axes()
        f.set_variation_by_axes(
            [
                min(max(a["minimum"], 14), a["maximum"]) if a["name"] == b"Optical size" else weight
                for a in axes
            ]
        )
    except OSError:
        pass  # static font
    return f


def lerp(a: str, b: str, t: float) -> tuple[int, int, int]:
    pa = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return tuple(round(x + (y - x) * t) for x, y in zip(pa, pb, strict=True))  # type: ignore[return-value]


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# left 55%: wordmark, scale underline, Greek name, tagline
x = SAFE
word = font(120, 800)
d.text((x, 130), "Kampos", font=word, fill=TEXT)
wb = d.textbbox((x, 130), "Kampos", font=word)
ul_y = wb[3] + 14
seg = (wb[2] - x) / 5
for px in range(x, wb[2]):
    t = (px - x) / seg
    i = min(int(t), 4)
    d.line([(px, ul_y), (px, ul_y + 12)], fill=lerp(SCALE[i], SCALE[i + 1], t - i))
d.text((x, ul_y + 36), "Κάμπος", font=font(40, 500), fill=MUTED)
tag = font(44, 600)
for n, line in enumerate(["Weekly greenness & rain", "for any field in Thessaly"]):
    d.text((x, ul_y + 120 + n * 58), line, font=tag, fill=TEXT)

# right 45%: hex map of Thessaly in the scale
rng = random.Random(7)
cx0, cy0, rx, ry = 900, H / 2, 240, 215
size = 16
for row in range(-20, 21):
    for col in range(-20, 21):
        px = cx0 + (col + (0.5 if row % 2 else 0)) * size * math.sqrt(3)
        py = cy0 + row * size * 1.5
        dist = math.hypot((px - cx0) / rx, (py - cy0) / ry)
        if dist > 1 + rng.random() * 0.12:
            continue
        v = min(5, max(0, int(dist * 3.4 + rng.random() * 2.2 - 0.4)))
        pts = [
            (
                px + size * 0.93 * math.cos(math.pi / 6 + k * math.pi / 3),
                py + size * 0.93 * math.sin(math.pi / 6 + k * math.pi / 3),
            )
            for k in range(6)
        ]
        d.polygon(pts, fill=SCALE[5 - v])

img.save(OUT, optimize=True)
print(f"wrote {OUT}")
