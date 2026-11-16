#!/usr/bin/env python3
"""Secure Office Suite: icons of the four applications.

Each application (SecureOffice Writer, Sheet, Presentation, PDF) gets its own
icon: a tile in the application's accent colour with a white page showing
what the application makes, and the Secure Office feather on top so the four
read as one family.

The feather is the artwork supplied for the suite (red, navy and cyan,
tools/sos-apps/feather/new-feather.png), drawn as is: same colours, shape,
proportions and direction. feather/prepare_feather.py cuts it out of its
white background into feather/feather.png, which this script uses. It sits
on a white edge, the way it was drawn on white, so it reads on every accent.

Writes, for every application <id>:
  win-linux/res/icons/apps/<id>.svg                    (Qt window and title-bar icon)
  win-linux/res/icons/apps/<id>.ico                    (Windows shortcuts, taskbar,
                                                        Default Programs, file types)
  package/common/linux/icons-apps/<id>/<n>x<n>.png     (Linux hicolor icons)
  package/common/linux/icons-apps/<id>/scalable.svg

Every PNG and every image inside the .ico is drawn at its own size (tile from
vector, feather resampled from the 1024 px cut-out), not scaled from one
bitmap, so 16 px to 256 px (100 % to 400 % DPI) stay sharp.

Needs cairosvg and Pillow: pip install cairosvg pillow
"""
import base64
import io
import os

import cairosvg
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEATHER = os.path.join(HERE, 'feather', 'feather.png')

# Accents of the Office-style UI (start page and editor tokens.less)
APPS = {
    'writer':       {'accent': '#2D5AA6'},
    'sheet':        {'accent': '#1F7A4D'},
    'presentation': {'accent': '#B9482A'},
    'pdf':          {'accent': '#B7262E'},
}
PNG_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

# Layout in a 256 x 256 box
TILE = (6, 54, 196, 196, 34)           # x, y, w, h, corner radius
PAGE = (28, 106, 118, 116, 12)       # white page with the application glyph
FEATHER_BOX = (118, 2, 138)           # x, y, height of the feather (its width follows)
HALO = 7                              # white edge around the feather, in 256 units


def glyph(app, c):
    """The application's mark, drawn for the page at 54,98 128x122 and
    moved onto PAGE by icon_svg()."""
    s = 'stroke="%s" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"' % c
    if app == 'writer':
        return ''.join('<line x1="76" y1="%d" x2="%d" y2="%d" %s/>' % (y, x2, y, s)
                       for y, x2 in ((124, 164), (148, 164), (172, 164), (196, 128)))
    if app == 'sheet':
        return ('<rect x="74" y="118" width="92" height="82" rx="4" %s/>' % s +
                '<line x1="74" y1="145" x2="166" y2="145" %s/>' % s +
                '<line x1="74" y1="172" x2="166" y2="172" %s/>' % s +
                '<line x1="106" y1="118" x2="106" y2="200" %s/>' % s)
    if app == 'presentation':
        return ('<path d="M118,160 V122 A38,38 0 1 1 80,160 Z" fill="%s"/>' % c +
                '<path d="M108,150 H72 A36,36 0 0 1 108,114 Z" fill="%s" opacity="0.55"/>' % c)
    # PDF: the letters drawn as strokes
    s = s.replace('stroke-width="12"', 'stroke-width="10"')
    return ('<path d="M68,196 V128 H82 A15,15 0 0 1 82,158 H68" %s/>' % s +
            '<path d="M108,196 V128 H114 A24,34 0 0 1 114,196 Z" %s/>' % s +
            '<path d="M168,128 H150 V196 M150,160 H164" %s/>' % s)


def base_svg(app):
    """Tile, page and glyph: everything but the feather."""
    a = APPS[app]
    tx, ty, tw, th, tr = TILE
    px, py, pw, ph, pr = PAGE
    k = pw / 128.0
    return (
        '<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="{tr}" fill="{accent}"/>'
        '<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="{pr}" fill="#FFFFFF"/>'
        '<g transform="translate({gx:.3f} {gy:.3f}) scale({k:.4f})">{glyph}</g>'
    ).format(tx=tx, ty=ty, tw=tw, th=th, tr=tr, px=px, py=py, pw=pw, ph=ph, pr=pr,
             accent=a['accent'], k=k, gx=px - 54 * k, gy=py - 98 * k, glyph=glyph(app, a['accent']))


def svg_doc(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            'viewBox="0 0 256 256" width="256" height="256">' + body + '</svg>')


_feather = None


def feather_with_edge(scale):
    """The feather and its white edge for a 256-unit box drawn at 256*scale px."""
    global _feather
    if _feather is None:
        _feather = Image.open(FEATHER).convert('RGBA')
    fx, fy, fh = FEATHER_BOX
    src = _feather
    h = max(1, round(fh * scale))
    w = max(1, round(src.width * fh / src.height * scale))
    m = max(2, int(HALO * scale * 2) + 2)
    art = src.resize((w, h), Image.LANCZOS)
    canvas = Image.new('RGBA', (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    canvas.alpha_composite(art, (m, m))
    a = canvas.getchannel('A')
    r = HALO * scale
    # a round dilation: blur the outline, keep anything the blur reached
    edge = a.filter(ImageFilter.GaussianBlur(max(0.5, r / 2)))
    edge = edge.point(lambda v: 255 if v > 6 else int(v * 255 / 6))
    edge = edge.filter(ImageFilter.GaussianBlur(min(0.6, r / 4)))
    white = Image.new('RGBA', canvas.size, (255, 255, 255, 0))
    white.putalpha(edge)
    white.alpha_composite(canvas)
    return white, (fx * scale - m, fy * scale - m)


def icon_png(app, size):
    scale = size / 256.0
    base = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg_doc(base_svg(app)).encode(),
                                                  output_width=size, output_height=size))).convert('RGBA')
    f, (x, y) = feather_with_edge(scale)
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    layer.alpha_composite(f, (round(x), round(y))) if x >= 0 and y >= 0 else None
    if x < 0 or y < 0:
        # paste with clipping
        big = Image.new('RGBA', (size + f.width, size + f.height), (0, 0, 0, 0))
        big.alpha_composite(f, (round(x) + f.width, round(y) + f.height))
        layer = big.crop((f.width, f.height, f.width + size, f.height + size))
    base.alpha_composite(layer)
    return base


def icon_svg(app):
    """Vector tile and page, the feather (with its white edge) as an embedded
    512 px PNG, so Qt draws it sharp at 200 % in the title bar."""
    f, (x, y) = feather_with_edge(2.0)
    buf = io.BytesIO()
    f.save(buf, 'PNG', optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    img = ('<image x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
           'xlink:href="data:image/png;base64,{d}"/>').format(x=x / 2, y=y / 2, w=f.width / 2,
                                                             h=f.height / 2, d=data)
    return svg_doc(base_svg(app) + img) + '\n'


def write_ico(app, path):
    """A multi-size .ico, each size drawn on its own (Pillow would otherwise
    downscale the 256 image for every entry)."""
    imgs = {n: icon_png(app, n) for n in ICO_SIZES}
    big = imgs[256]
    big.save(path, format='ICO', sizes=[(n, n) for n in ICO_SIZES],
             append_images=[imgs[n] for n in ICO_SIZES if n != 256])


def main():
    for app in APPS:
        svg = icon_svg(app)
        win = os.path.join(ROOT, 'win-linux', 'res', 'icons', 'apps')
        lin = os.path.join(ROOT, 'package', 'common', 'linux', 'icons-apps', app)
        os.makedirs(win, exist_ok=True)
        os.makedirs(lin, exist_ok=True)
        with open(os.path.join(win, app + '.svg'), 'w', encoding='utf-8') as f:
            f.write(svg)
        with open(os.path.join(lin, 'scalable.svg'), 'w', encoding='utf-8') as f:
            f.write(svg)
        for n in PNG_SIZES:
            icon_png(app, n).save(os.path.join(lin, '%dx%d.png' % (n, n)), optimize=True)
        write_ico(app, os.path.join(win, app + '.ico'))
        print('wrote', app)


if __name__ == '__main__':
    main()
