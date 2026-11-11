"""Apply the Secure Office Suite installer icon pack to desktop-apps and web-apps."""
import base64, io, json, os, re, shutil, sys
from PIL import Image

PACK, ROOT, TMP = sys.argv[1], sys.argv[2], sys.argv[3]
DA, WA = f"{ROOT}/desktop-apps", f"{ROOT}/web-apps"
png = lambda n: f"{PACK}/png/secure-office-suite-{n}.png"
MASTER = Image.open(png(1024)).convert("RGBA")
JOBS = []

def b64(n):
    return base64.b64encode(open(png(n), "rb").read()).decode()

def image_el(x, y, size, n):
    return (f'<image x="{x}" y="{y}" width="{size}" height="{size}" '
            f'preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{b64(n)}"/>')

XLINK = 'xmlns:xlink="http://www.w3.org/1999/xlink"'

def icon_svg(path, n):
    s = open(path).read()
    head = s[:s.index(">") + 1]
    if "xmlns:xlink" not in head:
        head = head.replace("<svg ", f"<svg {XLINK} ", 1)
    open(path, "w").write(head + image_el(0, 0, 256, n) + "</svg>\n")

def wordmark_svg(path, n):
    """The mark is the first inner <g> of the transformed group (256 x 256
    units); the wordmark paths follow it in the same group."""
    s = open(path).read()
    m = re.search(r'<g transform="translate\(([\d.]+) ([\d.]+)\) scale\(([\d.]+)\)">(<g>)', s)
    assert m, path
    start = m.start(4)
    depth = 0
    for t in re.finditer(r"<g\b[^>]*?(/?)>|</g>", s[start:]):
        if t.group(0) == "</g>":
            depth -= 1
        elif not t.group(1):
            depth += 1
        if depth == 0:
            end = start + t.end(); break
    s = s[:start] + image_el(0, 0, 256, n) + s[end:]
    open(path, "w").write(s)

def fit_icon(w, h):
    """The artwork cropped to its visible pixels and scaled to fit w x h."""
    art = MASTER.crop(MASTER.getbbox())
    k = min(w / art.width, h / art.height)
    return art.resize((max(1, round(art.width * k)), max(1, round(art.height * k))), Image.LANCZOS)

def clusters(mask_rows):
    out, start = [], None
    for i, v in enumerate(mask_rows + [False]):
        if v and start is None: start = i
        if not v and start is not None: out.append((start, i)); start = None
    return out

def replace_icon_in_raster(path, top_cluster=True):
    im = Image.open(path).convert("RGB")
    bg = im.getpixel((0, 0))
    W, H = im.size
    px = im.load()
    diff = lambda p: sum(abs(a - b) for a, b in zip(p, bg)) > 24
    rows = [any(diff(px[x, y]) for x in range(W)) for y in range(H)]
    cl = clusters(rows)
    # merge clusters separated by small gaps (icon parts)
    merged = []
    for c in cl:
        if merged and c[0] - merged[-1][1] <= max(2, H // 120):
            merged[-1] = (merged[-1][0], c[1])
        else:
            merged.append(c)
    y0, y1 = merged[0] if top_cluster else (merged[0][0], merged[-1][1])
    cols = [any(diff(px[x, y]) for y in range(y0, y1)) for x in range(W)]
    xs = [i for i, v in enumerate(cols) if v]
    x0, x1 = xs[0], xs[-1] + 1
    pad = 2
    out = im.convert("RGBA")
    blank = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), bg + (255,))
    out.paste(blank, (x0 - pad, y0 - pad))
    bw, bh = x1 - x0, y1 - y0
    # the new artwork is wider than tall; give it the old icon's height and a
    # little more room so it reads at the same weight
    ic = fit_icon(int(bw * 1.15), int(bh * 1.15))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out.alpha_composite(ic, (round(cx - ic.width / 2), round(cy - ic.height / 2)))
    out.convert("RGB").save(path, optimize=True)

# ---------------- desktop-apps ----------------
ICONS = f"{DA}/win-linux/res/icons"
for f in ("app-icon-eo.svg", "app-icon-eo-dark.svg"):
    icon_svg(f"{ICONS}/{f}", 128)
for f in ("idx-logo-light-eo.svg", "idx-logo-dark-eo.svg"):
    icon_svg(f"{DA}/common/loginpage/res/img/{f}", 256)
for v in ("light", "dark"):
    p = f"{ICONS}/logo-{v}-eo.svg"
    wordmark_svg(p, 64)
    for sc, (w, h) in {"": (83, 20), "@1.25x": (104, 25), "@1.5x": (125, 30), "@1.75x": (145, 35)}.items():
        JOBS.append((p, w, h, f"{ICONS}/logo-{v}-eo{sc}.png"))
wordmark_svg(f"{ICONS}/splash-eo.svg", 256)
shutil.copy(png(64), f"{ICONS}/app-icon_64.png")

ico = f"{PACK}/windows/secure-office-suite.ico"
for dest in (f"{ICONS}/desktopeditors-eo.ico", f"{ICONS}/desktopeditors.ico",
             f"{DA}/win-linux/extras/projicons/res/icons/desktopeditors.ico",
             f"{DA}/win-linux/extras/update-daemon/res/icons/desktopeditors.ico"):
    shutil.copy(ico, dest)

for n in (16, 24, 32, 48, 64, 128, 256):
    shutil.copy(f"{PACK}/linux/hicolor/{n}x{n}/apps/secure-office-suite.png",
                f"{DA}/package/common/linux/icons-eo/{n}x{n}.png")

INNO = f"{DA}/package/inno/res"
for f in sorted(os.listdir(INNO)):
    if f.startswith("WizImage-"):
        replace_icon_in_raster(f"{INNO}/{f}", top_cluster=True)
    elif f.startswith("WizSmallImage-"):
        replace_icon_in_raster(f"{INNO}/{f}", top_cluster=False)

# ---------------- web-apps ----------------
IMG = f"{WA}/theme/secure-office-suite/assets/img"
for rel, n in (("about/logo.svg", 256), ("embed/logo.svg", 128), ("header/dark-logo_s.svg", 128),
               ("header/eo_logo_dark.svg", 128), ("header/eo_logo_light.svg", 128),
               ("header/header-logo_s.svg", 128)):
    wordmark_svg(f"{IMG}/{rel}", n)

os.makedirs(TMP, exist_ok=True)
json.dump(JOBS, open(f"{TMP}/jobs.json", "w"))
print("svg/ico/png done; render jobs:", len(JOBS))
