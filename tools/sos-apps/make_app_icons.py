#!/usr/bin/env python3
"""Secure Office Suite: icons of the four applications.

Each application (EuroOffice Writer, Sheet, Presentation, PDF) gets its own
icon: a tile in the application's accent colour with a white page showing
what the application makes, and the suite's plume on top so the four read
as one family. The plume is taken from the suite icon
(win-linux/res/icons/app-icon-eo.svg).

Writes, for every application <id>:
  win-linux/res/icons/apps/<id>.svg                    (Qt window and title-bar icon)
  win-linux/res/icons/apps/<id>.ico                    (Windows shortcuts, taskbar)
  package/common/linux/icons-apps/<id>/<n>x<n>.png     (Linux hicolor icons)
  package/common/linux/icons-apps/<id>/scalable.svg

Needs cairosvg and Pillow: pip install cairosvg pillow
"""
import io
import os
import re
import sys

import cairosvg
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SUITE_ICON = os.path.join(ROOT, 'win-linux', 'res', 'icons', 'app-icon-eo.svg')

# Accents of the Office-style UI (start page and editor tokens.less)
APPS = {
    'writer':       {'accent': '#2D5AA6', 'dark': '#1F4280'},
    'sheet':        {'accent': '#1F7A4D', 'dark': '#155937'},
    'presentation': {'accent': '#B9482A', 'dark': '#8C341D'},
    'pdf':          {'accent': '#B7262E', 'dark': '#8A1A21'},
}
PNG_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def plume():
    """The quill polygons of the suite icon (its last elements)."""
    svg = open(SUITE_ICON, encoding='utf-8').read()
    shapes = re.findall(r'<polygon [^>]*/>', svg)
    if len(shapes) < 2:
        sys.exit('plume not found in ' + SUITE_ICON)
    out = []
    for i, s in enumerate(shapes):
        # gradients of the suite file are flat colours: red, then navy
        s = re.sub(r'fill="url\(#[^)]*\)"', 'fill="%s"' % ('#D7262E' if i == 0 else '#1B2A86'), s)
        out.append(s)
    # the nib and anything drawn after the polygons
    tail = svg[svg.rfind('/>', 0, svg.rfind('<polygon')) + 2:]
    nib = re.findall(r'<(?:path|rect|polygon)[^>]*fill="#C[0-9A-Fa-f]{5}"[^>]*/>', tail)
    return ''.join(out + nib)


def glyph(app, c):
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


def icon_svg(app):
    a = APPS[app]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">'
        '<rect x="16" y="44" width="200" height="200" rx="36" fill="{accent}"/>'
        '<rect x="54" y="98" width="128" height="122" rx="12" fill="#FFFFFF"/>'
        '{glyph}'
        # a white edge keeps the plume readable on every accent
        '<g transform="translate(116 -4) scale(0.74)">'
        '<g fill="#FFFFFF" stroke="#FFFFFF" stroke-width="14" stroke-linejoin="round">{halo}</g>{plume}</g>'
        '</svg>').format(accent=a['accent'], glyph=glyph(app, a['accent']), plume=plume(),
                   halo=re.sub(r'fill="[^"]*"', '', plume()))


def png(svg, size):
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=size,
                                                   output_height=size))).convert('RGBA')


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
            png(svg, n).save(os.path.join(lin, '%dx%d.png' % (n, n)), optimize=True)
        big = png(svg, 256)
        big.save(os.path.join(win, app + '.ico'), sizes=[(n, n) for n in ICO_SIZES])
        print('wrote', app)


if __name__ == '__main__':
    main()
