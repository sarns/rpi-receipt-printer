"""Black-and-white weather icons drawn with Pillow, sized for a thermal printer."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

SS = 4  # supersampling factor for smooth edges


def category(code: int) -> str:
    """Map a WMO weather code to an icon name."""
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"


def _sun(d, cx, cy, r, w):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=w)
    for i in range(8):
        a = i * math.pi / 4
        d.line([cx + math.cos(a) * r * 1.4, cy + math.sin(a) * r * 1.4,
                cx + math.cos(a) * r * 1.9, cy + math.sin(a) * r * 1.9], fill=0, width=w)


def _cloud(d, x, y, s, w, fill_white=True):
    """Cloud whose bounding box is roughly (x, y) .. (x + s, y + 0.6 s)."""
    f = 255 if fill_white else None
    d.ellipse([x + .05 * s, y + .22 * s, x + .40 * s, y + .57 * s], fill=f, outline=0, width=w)
    d.ellipse([x + .22 * s, y + .02 * s, x + .62 * s, y + .45 * s], fill=f, outline=0, width=w)
    d.ellipse([x + .50 * s, y + .17 * s, x + .88 * s, y + .57 * s], fill=f, outline=0, width=w)
    d.rectangle([x + .22 * s, y + .30 * s, x + .70 * s, y + .57 * s], fill=f)
    # redraw the flat bottom and hide inner outlines
    d.line([x + .22 * s, y + .57 * s, x + .70 * s, y + .57 * s], fill=0, width=w)


def icon(name: str, size: int = 96) -> Image.Image:
    S = size * SS
    img = Image.new("L", (S, S), 255)
    d = ImageDraw.Draw(img)
    w = max(2, S // 28)
    if name == "sun":
        _sun(d, S // 2, S // 2, int(S * .2), w)
    elif name == "partly":
        _sun(d, int(S * .36), int(S * .36), int(S * .15), w)
        _cloud(d, S * .22, S * .36, S * .72, w)
    elif name == "fog":
        _cloud(d, S * .1, S * .08, S * .8, w)
        for i, y in enumerate((.68, .80, .92)):
            off = .08 if i % 2 else 0
            d.line([S * (.15 + off), S * y, S * (.85 - off), S * y], fill=0, width=w)
    else:
        _cloud(d, S * .1, S * .1, S * .8, w)
        if name == "rain":
            for x in (.3, .48, .66):
                d.line([S * x, S * .68, S * (x - .06), S * .88], fill=0, width=w)
        elif name == "snow":
            for x, y in ((.3, .74), (.5, .88), (.7, .74)):
                r = S * .05
                d.line([S * x - r, S * y, S * x + r, S * y], fill=0, width=w)
                d.line([S * x, S * y - r, S * x, S * y + r], fill=0, width=w)
        elif name == "storm":
            d.polygon([(S * .52, S * .6), (S * .38, S * .8), (S * .5, S * .8),
                       (S * .42, S * .96), (S * .64, S * .72), (S * .52, S * .72),
                       (S * .6, S * .6)], fill=0)
    img = img.resize((size, size), Image.LANCZOS)
    return img.point(lambda v: 255 if v > 150 else 0).convert("1")


if __name__ == "__main__":
    names = ["sun", "partly", "cloud", "fog", "rain", "snow", "storm"]
    sheet = Image.new("1", (96 * len(names), 96), 1)
    for i, n in enumerate(names):
        sheet.paste(icon(n), (i * 96, 0))
    sheet.save("icons_preview.png")
