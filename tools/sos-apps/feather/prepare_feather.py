#!/usr/bin/env python3
"""Cut the Secure Office feather out of the artwork Mansoor supplied.

The supplied file (new-feather.png, 1292 x 1217, red / navy / cyan feather on
a white background) is used as is: no recolouring, reshaping or rotation.
This script only removes the white background around the feather and crops
to it, so the application icons can lay it over their tiles.

    python3 -I prepare_feather.py new-feather.png feather.png

Writes an RGBA PNG: the feather's own pixels, alpha 255 inside its outline,
transparent outside. The white shaft line and the white slits between the
barbs are part of the drawing, so they stay white on any background: the
outline is closed over gaps up to CLOSE pixels wide before the background
is removed.
"""
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter

INK = 236          # a pixel whose darkest channel is below this is artwork
MAX_SIDE = 1024    # stored size: 4x the largest icon size it is drawn at
CLOSE = 16         # slits narrower than 2 x CLOSE source pixels stay white


def main(src, dst):
    im = Image.open(src).convert('RGB')
    # darkest channel per pixel; the background is ~253-255 in every channel
    r, g, b = im.split()
    dark = ImageChops.darker(ImageChops.darker(r, g), b)
    ink = dark.point(lambda v: 255 if v < INK else 0)
    # the outline: close the white gaps of the drawing (dilate, then erode),
    # then everything not reachable from the border through white
    for _ in range(CLOSE):
        ink = ink.filter(ImageFilter.MaxFilter(3))
    for _ in range(CLOSE):
        ink = ink.filter(ImageFilter.MinFilter(3))
    w, h = ink.size
    pad = Image.new('L', (w + 2, h + 2), 0)
    pad.paste(ink, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    inside = pad.crop((1, 1, w + 1, h + 1)).point(lambda v: 0 if v == 128 else 255)
    box = inside.getbbox()
    m = 6
    box = (max(0, box[0] - m), max(0, box[1] - m), min(w, box[2] + m), min(h, box[3] + m))
    art = im.crop(box).convert('RGBA')
    alpha = inside.crop(box)
    # soften the outline by one pixel so it does not look cut with scissors
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))
    art.putalpha(alpha)
    k = MAX_SIDE / max(art.size)
    if k < 1:
        art = art.resize((round(art.width * k), round(art.height * k)), Image.LANCZOS)
    art.save(dst, optimize=True)
    print('wrote', dst, art.size)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
