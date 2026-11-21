#!/usr/bin/env python3
"""Generate Steam library artwork for a non-Steam shortcut (cover, wide header, hero, logo, icon).

  steam-art.py "<Steam app name>" [--appid N] [--label TEXT] [--subtitle TEXT]
               [--colors "#light,#base,#dark"] [--glyph play|none] [--icon file.png|file.jpg]

Finds the shortcut's appid in shortcuts.vdf by its name (or takes --appid) and renders PNGs with rsvg-convert into
userdata/<id>/config/grid/. Safe while Steam runs; Steam shows new art after it restarts.
The art is a gradient with the app's name and either the given icon or a simple play glyph.
"""
import argparse, base64, os, struct, subprocess, tempfile

STEAM = os.path.expanduser("~/.local/share/Steam")


def grid_dirs():
    base = os.path.join(STEAM, "userdata")
    return [os.path.join(base, uid, "config") for uid in sorted(os.listdir(base))
            if os.path.exists(os.path.join(base, uid, "config", "shortcuts.vdf"))]


def find_appid(name):
    for cfg in grid_dirs():
        d = open(os.path.join(cfg, "shortcuts.vdf"), "rb").read()
        i = d.lower().find(b"\x01appname\x00" + name.lower().encode() + b"\x00")
        if i < 0:
            continue
        j = d.lower().rfind(b"\x02appid\x00", 0, i)
        return struct.unpack("<I", d[j + 7:j + 11])[0], os.path.join(cfg, "grid")
    raise SystemExit(f"no shortcut named {name!r}")


def find_grid(appid):
    needle = b"\x02appid\x00" + struct.pack("<I", appid)
    for cfg in grid_dirs():
        if needle in open(os.path.join(cfg, "shortcuts.vdf"), "rb").read():
            return os.path.join(cfg, "grid")
    raise SystemExit(f"no shortcut with appid {appid}")


def image_mime(path):
    head = open(path, "rb").read(12)
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    raise SystemExit(f"--icon must be a PNG or JPEG file: {path}")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def glyph_svg(kind, cx, cy, r, color):
    if kind == "play":
        return (f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='{color}' stroke-width='{r*0.12}'/>"
                f"<path d='M {cx - r*0.32} {cy - r*0.45} L {cx + r*0.5} {cy} L {cx - r*0.32} {cy + r*0.45} Z' fill='{color}'/>")
    return ""


def render(name, subtitle, colors, glyph, icon, label=None, appid=None):
    if appid is None:
        appid, grid = find_appid(name)
    else:
        grid = find_grid(appid)
    name = esc(label or name)   # text shown on the art
    subtitle = esc(subtitle)
    os.makedirs(grid, exist_ok=True)
    c1, c2, c3 = colors
    font = "font-family='Noto Sans, DejaVu Sans, sans-serif'"
    bg = lambda w, h: f"""<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0' stop-color='{c1}'/><stop offset='0.5' stop-color='{c2}'/><stop offset='1' stop-color='{c3}'/></linearGradient>
<radialGradient id='v' cx='0.5' cy='0.4' r='0.75'><stop offset='0.55' stop-color='#000' stop-opacity='0'/>
<stop offset='1' stop-color='#000' stop-opacity='0.45'/></radialGradient></defs>
<rect width='{w}' height='{h}' fill='url(#g)'/><rect width='{w}' height='{h}' fill='url(#v)'/>"""
    icon_uri = f"data:{image_mime(icon)};base64,{base64.b64encode(open(icon, 'rb').read()).decode()}" if icon else None

    def mark(cx, cy, r):
        if icon_uri:
            return f"<image href='{icon_uri}' x='{cx-r}' y='{cy-r}' width='{2*r}' height='{2*r}'/>"
        return glyph_svg(glyph, cx, cy, r, "#ffffff")

    fs = lambda base: base * min(1.0, 9 / max(len(name), 1))  # shrink long names
    sub = lambda x, y, size, anchor="start": (f"<text x='{x}' y='{y}' text-anchor='{anchor}' {font} font-size='{size}' "
                                              f"fill='#ffffff' fill-opacity='0.85' letter-spacing='{size*0.12}'>{subtitle}</text>") if subtitle else ""
    arts = {
        f"{appid}p.png": (600, 900, lambda w, h: bg(w, h) + mark(w/2, h*0.38, w*0.22)
            + f"<text x='{w/2}' y='{h*0.70}' text-anchor='middle' {font} font-weight='700' font-size='{fs(w*0.15)}' fill='#fff'>{name}</text>"
            + sub(w/2, h*0.77, w*0.05, "middle")),
        f"{appid}.png": (920, 430, lambda w, h: bg(w, h) + mark(w*0.2, h/2, h*0.27)
            + f"<text x='{w*0.36}' y='{h*0.56}' {font} font-weight='700' font-size='{fs(h*0.22)}' fill='#fff'>{name}</text>"
            + sub(w*0.36, h*0.70, h*0.07)),
        f"{appid}_hero.png": (1920, 620, lambda w, h: bg(w, h)
            + f"<g opacity='0.25'>{mark(w*0.8, h/2, h*0.4)}</g>"),
        f"{appid}_logo.png": (900, 200, lambda w, h: mark(h/2, h/2, h*0.42)
            + f"<text x='{h*1.15}' y='{h*0.68}' {font} font-weight='700' font-size='{fs(h*0.55)}' fill='#fff'>{name}</text>"),
        f"{appid}_icon.png": (256, 256, lambda w, h: bg(w, h) + mark(w/2, h/2, w*0.34)),
    }
    for fname, (w, h, body) in arts.items():
        svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>{body(w, h)}</svg>"
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
            f.write(svg)
        try:
            subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", os.path.join(grid, fname), f.name], check=True)
        finally:
            os.unlink(f.name)
        print("art:", os.path.join(grid, fname))
    return appid, grid


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("name"); a.add_argument("--subtitle", default="")
    a.add_argument("--appid", type=int, help="the shortcut's appid (default: look it up by name)")
    a.add_argument("--colors", default="#3d7bff,#0a2a6b,#05070f")
    a.add_argument("--glyph", default="play", choices=["play", "none"]); a.add_argument("--icon")
    a.add_argument("--label", help="text on the artwork (default: the shortcut name)")
    o = a.parse_args()
    render(o.name, o.subtitle, o.colors.split(","), o.glyph, o.icon, o.label, o.appid)
