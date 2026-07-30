#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate the SVG "cards" for a GitHub profile README (neofetch-style).

Outputs, for each theme (dark / light):
    info-card-<theme>.svg   whoami: ASCII portrait + neofetch panel
    projects-<theme>.svg    ls ./projects: grid of project cards
    stats-<theme>.svg       contribution graph + streaks
    connect-<theme>.svg     ./connect.sh prompt + footer
    link-<i>-<theme>.svg    one clickable chip per link
and rewrites README.md so it points at them with a cache-busting ?v= stamp.

Usage:  python3 build.py [profile.json]
Deps:   Pillow (only for the ASCII portrait), stdlib otherwise.
"""

import datetime
import html
import json
import math
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(ROOT, "assets", "icons")
W = 900                      # canvas width for every full-width card
CW = 0.60                    # monospace advance width / font-size
MONO = ("ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")
UA = {"User-Agent": "Mozilla/5.0 (profile-card-builder)"}

# every ramp goes sparse -> dense; `invert` flips it (use invert for photos
# shot against a *bright* background, so the background renders as blank)
RAMPS = {
    "detailed": (" .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao"
                 "*#MW&8%B@$"),
    "classic": " .:-=+*#%@",
    "blocks": " ..::--==++**##@@",
}

THEMES = {
    "dark": {
        "panel": "#0d1117", "panel2": "#010409", "pill": "#161b22",
        "border": "#30363d", "fg": "#e6edf3", "muted": "#8b949e",
        "accent": "#58a6ff", "green": "#3fb950", "art": "#c9d1d9",
        "cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
    "light": {
        "panel": "#ffffff", "panel2": "#f6f8fa", "pill": "#f6f8fa",
        "border": "#d0d7de", "fg": "#1f2328", "muted": "#59636e",
        "accent": "#0969da", "green": "#1a7f37", "art": "#424a53",
        "cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
}

# tech label -> (simple-icons slug, brand colour)
TECH = {
    "python": ("python", "#3776AB"), "typescript": ("typescript", "#3178C6"),
    "javascript": ("javascript", "#F7DF1E"), "react": ("react", "#61DAFB"),
    "react native": ("react", "#61DAFB"), "next.js": ("nextdotjs", "#111111"),
    "nestjs": ("nestjs", "#E0234E"), "fastapi": ("fastapi", "#009688"),
    "django": ("django", "#092E20"), "flask": ("flask", "#111111"),
    "node.js": ("nodedotjs", "#5FA04E"), "docker": ("docker", "#2496ED"),
    "kubernetes": ("kubernetes", "#326CE5"), "postgresql": ("postgresql", "#4169E1"),
    "mysql": ("mysql", "#4479A1"), "mongodb": ("mongodb", "#47A248"),
    "redis": ("redis", "#FF4438"), "sqlite": ("sqlite", "#003B57"),
    "tensorflow": ("tensorflow", "#FF6F00"), "pytorch": ("pytorch", "#EE4C2C"),
    "opencv": ("opencv", "#5C3EE8"), "openai": ("openai", "#412991"),
    "c#": ("csharp", "#512BD4"), ".net": ("dotnet", "#512BD4"),
    "maui": (None, "#512BD4"), "go": ("go", "#00ADD8"),
    "rust": ("rust", "#111111"), "java": (None, "#E76F00"),
    "kotlin": ("kotlin", "#7F52FF"), "swift": ("swift", "#F05138"),
    "flutter": ("flutter", "#02569B"), "vue": ("vuedotjs", "#4FC08D"),
    "svelte": ("svelte", "#FF3E00"), "tailwind": ("tailwindcss", "#06B6D4"),
    "aiogram": ("telegram", "#26A5E4"), "telegram": ("telegram", "#26A5E4"),
    "selenium": ("selenium", "#43B02A"), "playwright": ("playwright", "#2EAD33"),
    "postman": ("postman", "#FF6C37"), "pytest": ("pytest", "#0A9EDC"),
    "sql": (None, "#4479A1"), "git": ("git", "#F05032"),
    "github": ("github", "#4a5058"), "figma": ("figma", "#F24E1E"),
    "github actions": ("githubactions", "#2088FF"),
    "express": ("express", "#4a5058"), "fastify": ("fastify", "#4a5058"),
    "nuxt": ("nuxt", "#00DC82"), "vite": ("vite", "#646CFF"),
    "gsap": ("greensock", "#88CE02"), "three.js": ("threedotjs", "#4a5058"),
    "supabase": ("supabase", "#3FCF8E"), "vercel": ("vercel", "#111111"),
    "aws": (None, "#FF9900"), "celery": ("celery", "#37814A"),
    "graphql": ("graphql", "#E10098"), "prisma": ("prisma", "#2D3748"),
}

LINK_COLORS = {
    "firefoxbrowser": "#FF7139", "instagram": "#E4405F", "leetcode": "#FFA116",
    "gmail": "#EA4335", "github": "#8b949e", "telegram": "#26A5E4",
    "linkedin": "#0A66C2", "x": "#8b949e", "youtube": "#FF0000",
    "discord": "#5865F2", "medium": "#8b949e", "codeforces": "#1F8ACB",
}


# --------------------------------------------------------------------------
# tiny svg helpers
# --------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=True)


def tw(s, size):
    """approximate rendered width of monospace text"""
    return len(s) * CW * size


def text(x, y, s, fill, size=13, weight="400", anchor="start", opacity=None,
         spacing=None):
    op = ' opacity="%s"' % opacity if opacity else ""
    ls = ' letter-spacing="%s"' % spacing if spacing else ""
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
            'font-weight="%s" fill="%s" text-anchor="%s" '
            'xml:space="preserve"%s%s>%s</text>'
            % (x, y, MONO, size, weight, fill, anchor, op, ls, esc(s)))


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1, opacity=None):
    st = ' stroke="%s" stroke-width="%s"' % (stroke, sw) if stroke else ""
    op = ' opacity="%s"' % opacity if opacity else ""
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%s" '
            'fill="%s"%s%s/>' % (x, y, w, h, rx, fill, st, op))


def line(x1, y1, x2, y2, stroke, sw=1, opacity=None):
    op = ' opacity="%s"' % opacity if opacity else ""
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
            'stroke-width="%s"%s/>' % (x1, y1, x2, y2, stroke, sw, op))


def svg_doc(w, h, body, title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-label="%s">'
            '<title>%s</title>%s</svg>'
            % (w, h, w, h, esc(title), esc(title), body))


def prompt(cx, y, handle, cmd, P, size=17):
    """the `you@github ~ $ cmd` pill. returns (svg, total_height)"""
    segs = [("%s@github" % handle, P["fg"], "700"), (" ~ ", P["muted"], "700"),
            ("$ ", P["green"], "700"), (cmd, P["fg"], "700")]
    full = "".join(s[0] for s in segs)
    w = tw(full, size) + 26
    h = size + 16
    x0 = cx - w / 2.0
    tspans = "".join('<tspan fill="%s" font-weight="%s">%s</tspan>'
                     % (c, wt, esc(t)) for t, c, wt in segs)
    body = rect(x0, y, w, h, P["pill"], rx=7)
    body += ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
             'xml:space="preserve">%s</text>'
             % (x0 + 13, y + h - 6, MONO, size, tspans))
    return body, h


def luminance(hex_color):
    c = hex_color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def on_color(bg):
    return "#000000" if luminance(bg) > 0.45 else "#ffffff"


# --------------------------------------------------------------------------
# simple-icons
# --------------------------------------------------------------------------
_icon_cache = {}


def icon_path(slug):
    """return the `d` attribute of a simple-icons glyph (24x24), or None"""
    if not slug:
        return None
    if slug in _icon_cache:
        return _icon_cache[slug]
    local = os.path.join(ICON_DIR, slug + ".svg")
    raw = None
    if os.path.exists(local):
        with open(local, "r", encoding="utf-8") as fh:
            raw = fh.read()
    else:
        url = "https://cdn.jsdelivr.net/npm/simple-icons/icons/%s.svg" % slug
        try:
            req = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
            if not os.path.isdir(ICON_DIR):
                os.makedirs(ICON_DIR)
            with open(local, "w", encoding="utf-8") as fh:
                fh.write(raw)
        except Exception as exc:            # offline / renamed slug
            sys.stderr.write("  ! icon '%s' unavailable (%s)\n" % (slug, exc))
    d = None
    if raw:
        m = re.search(r'\sd="([^"]+)"', raw)
        if m:
            d = m.group(1)
    _icon_cache[slug] = d
    return d


def glyph(slug, x, y, size, fill):
    """place a 24x24 simple-icon at (x, y) scaled to `size`"""
    d = icon_path(slug)
    if not d:
        return ""
    s = size / 24.0
    return ('<g transform="translate(%.2f,%.2f) scale(%.4f)">'
            '<path d="%s" fill="%s"/></g>' % (x, y, s, d, fill))


# --------------------------------------------------------------------------
# ASCII portrait
# --------------------------------------------------------------------------
def ascii_art(path, a):
    """a = the `art` block of profile.json"""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError:
        sys.stderr.write("  ! Pillow not installed - skipping portrait\n")
        return []
    if not path or not os.path.exists(os.path.join(ROOT, path)):
        sys.stderr.write("  ! avatar '%s' not found - skipping portrait\n" % path)
        return []
    cols = int(a.get("cols", 98))
    img = Image.open(os.path.join(ROOT, path)).convert("L")
    if a.get("crop"):
        img = img.crop(tuple(a["crop"]))
    if a.get("median"):
        img = img.filter(ImageFilter.MedianFilter(int(a["median"])))
    img = ImageOps.autocontrast(img, cutoff=a.get("cutoff", 2))
    img = ImageEnhance.Contrast(img).enhance(float(a.get("contrast", 1.4)))
    cut = int(a.get("cut", 255))
    if cut < 255:
        # push everything brighter than `cut` to pure white, so a bright
        # background collapses into blank space instead of noise
        img = img.point(lambda v: 255 if v >= cut else int(v * 254.0 / cut))
    iw, ih = img.size
    rows = int(round(cols * (float(ih) / iw) * 0.55))
    if a.get("rows"):
        rows = min(rows, int(a["rows"]))
    img = img.resize((cols, rows), Image.LANCZOS)
    px = img.load()
    ramp = RAMPS.get(a.get("ramp", "classic"), RAMPS["classic"])
    if a.get("invert"):
        ramp = ramp[::-1]
    n = len(ramp) - 1
    out = []
    for r in range(rows):
        out.append("".join(ramp[int(px[c, r] * n / 255)] for c in range(cols)))
    return _trim(out)


def _trim(rows):
    """drop all-blank border rows/columns so the portrait fills its panel"""
    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()
    inked = [r for r in rows if r.strip()]
    if not inked:
        return rows
    left = min(len(r) - len(r.lstrip()) for r in inked)
    right = min(len(r) - len(r.rstrip()) for r in inked)
    end = len(rows[0]) - right
    return [r[left:end] for r in rows]


# --------------------------------------------------------------------------
# contributions (public, no token)
# --------------------------------------------------------------------------
def _attr(tag, name):
    m = re.search(r'\s%s="([^"]*)"' % name, tag)
    return m.group(1) if m else None


def fetch_contributions(user):
    """[(date, count, level), ...] for the trailing year"""
    days = {}
    try:
        req = urllib.request.Request(
            "https://github.com/users/%s/contributions" % user,
            headers=dict(UA, **{"X-Requested-With": "XMLHttpRequest"}))
        page = urllib.request.urlopen(req, timeout=25).read().decode("utf-8")
        ids = {}
        for tag in re.findall(r"<td\b[^>]*>", page):
            date = _attr(tag, "data-date")
            if not date:
                continue
            lvl = int(_attr(tag, "data-level") or 0)
            days[date] = [0, lvl]
            tid = _attr(tag, "id")
            if tid:
                ids[tid] = date
        for tid, inner in re.findall(
                r'<tool-tip\b[^>]*\sfor="([^"]+)"[^>]*>(.*?)</tool-tip>',
                page, re.S):
            date = ids.get(tid)
            if not date:
                continue
            m = re.search(r"(\d+)\s+contribution", inner)
            days[date][0] = int(m.group(1)) if m else 0
    except Exception as exc:
        sys.stderr.write("  ! github scrape failed (%s), trying fallback\n" % exc)
    if not days:
        try:
            req = urllib.request.Request(
                "https://github-contributions-api.jogruber.de/v4/%s?y=last" % user,
                headers=UA)
            data = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
            for d in data.get("contributions", []):
                days[d["date"]] = [d.get("count", 0), d.get("level", 0)]
        except Exception as exc:
            sys.stderr.write("  ! fallback failed (%s) - empty graph\n" % exc)
    return sorted((d, v[0], v[1]) for d, v in days.items())


def streaks(days):
    today = datetime.date.today().isoformat()
    cur = longest = run = 0
    best = 0
    total = 0
    for date, count, _lvl in days:
        total += count
        best = max(best, count)
        if count > 0:
            run += 1
            longest = max(longest, run)
        else:
            if date < today:            # today being empty must not break it
                run = 0
    # current streak: walk backwards, tolerating an empty "today"
    seq = [d for d in days if d[0] <= today]
    i = len(seq) - 1
    if i >= 0 and seq[i][1] == 0:
        i -= 1
    while i >= 0 and seq[i][1] > 0:
        cur += 1
        i -= 1
    return {"current": cur, "longest": longest, "best": best, "total": total}


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------
def card_info(cfg, P, art):
    pad = 20
    body, ph = prompt(W / 2.0, 8, cfg["handle"], "whoami", P)
    top = 8 + ph + 18

    afs, alh = 6.0, 6.05
    art_w = (len(art[0]) * CW * afs) if art else 0
    art_h = len(art) * alh
    left_w = art_w + 2 * pad

    rows = cfg["neofetch"]
    row_h = 30
    win_x = left_w + 8
    win_w = W - win_x - pad
    win_h = 84 + len(rows) * row_h + 56
    card_h = max(art_h + 2 * pad, win_h + 2 * pad)
    total_h = int(top + card_h + 8)

    body += rect(1, top, W - 2, card_h, P["panel"], rx=12,
                 stroke=P["border"], sw=1)

    # --- left: ascii portrait
    ax = pad + (left_w - 2 * pad - art_w) / 2.0
    ay = top + (card_h - art_h) / 2.0 + afs
    for i, row in enumerate(art):
        body += ('<text x="%.1f" y="%.2f" font-family="%s" font-size="%s" '
                 'fill="%s" opacity="0.92" textLength="%.2f" '
                 'lengthAdjust="spacingAndGlyphs" xml:space="preserve">%s</text>'
                 % (ax, ay + i * alh, MONO, afs, P["art"], art_w, esc(row)))
    if art:
        body += line(left_w, top + 16, left_w, top + card_h - 16,
                     P["border"], 1, opacity="0.7")

    # --- right: neofetch window
    wy = top + (card_h - win_h) / 2.0
    body += rect(win_x, wy, win_w, win_h, P["panel2"], rx=10,
                 stroke=P["border"], sw=1)
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        body += ('<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/>'
                 % (win_x + 22 + i * 20, wy + 24, col))
    body += text(win_x + win_w - 18, wy + 29, "~ neofetch", P["muted"], 13,
                 anchor="end")

    hx, hy = win_x + 26, wy + 62
    body += text(hx, hy, cfg["handle"], P["accent"], 16, "700")
    body += text(hx + tw(cfg["handle"], 16), hy, "@github", P["green"], 16, "700")
    body += rect(hx + tw(cfg["handle"] + "@github ", 16), hy - 12, 9, 14,
                 P["green"], rx=1)
    body += line(hx, hy + 16, win_x + win_w - 26, hy + 16, P["border"], 1)

    kw = max(len(k) for k, _ in rows) + 2
    ry = hy + 46
    for i, (k, v) in enumerate(rows):
        y = ry + i * row_h
        body += text(hx, y, (k + ":").ljust(kw), P["accent"], 14, "700")
        body += text(hx + tw(" " * kw, 14), y, v, P["fg"], 14)

    sy = ry + len(rows) * row_h - 4
    swatch = ["#484f58", "#ff7b72", "#3fb950", "#d29922",
              "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"]
    for r in range(2):
        for c, col in enumerate(swatch):
            body += rect(hx + c * 25, sy + r * 25, 20, 20, col, rx=3,
                         opacity="1" if r == 0 else "0.6")
    return svg_doc(W, total_h, body, "whoami")


def chip(x, y, label, P):
    """brand-coloured tech chip; returns (svg, width)"""
    slug, colr = TECH.get(label.lower(), (None, "#6e7681"))
    fs, h = 11.5, 24
    ic = 13 if slug and icon_path(slug) else 0
    pad_l = 9
    wdt = pad_l + (ic + 6 if ic else 0) + tw(label, fs) + 10
    fg = on_color(colr)
    out = rect(x, y, wdt, h, colr, rx=5)
    if ic:
        out += glyph(slug, x + pad_l, y + (h - ic) / 2.0, ic, fg)
    out += text(x + pad_l + (ic + 6 if ic else 0), y + h / 2.0 + 4, label, fg,
                fs, "700")
    return out, wdt


def tag_pill(x, y, label, P):
    fs, h = 10.5, 18
    wdt = tw(label, fs) + 16
    out = rect(x, y, wdt, h, P["pill"], rx=9, stroke=P["border"], sw=1)
    out += text(x + 8, y + h / 2.0 + 3.5, label, P["muted"], fs, "600")
    return out, wdt


def card_projects(cfg, P):
    pad = 20
    body, ph = prompt(W / 2.0, 8, cfg["handle"], "ls ./projects", P)
    top = 8 + ph + 18

    projects = cfg["projects"]
    cols, cw = 2, (W - 2 * pad) / 2.0
    nrows = int(math.ceil(len(projects) / float(cols)))
    ch = 132
    card_h = nrows * ch + 2 * 10
    total_h = int(top + card_h + 8)

    body += rect(1, top, W - 2, card_h, P["panel"], rx=12,
                 stroke=P["border"], sw=1)

    for i, pr in enumerate(projects):
        r, c = divmod(i, cols)
        cx = pad + c * cw
        cy = top + 10 + r * ch
        if r:
            body += line(pad, cy, W - pad, cy, P["border"], 1, opacity="0.6")
        x = cx + 8
        for t in pr.get("tags", []):
            g, wdt = tag_pill(x, cy + 14, t, P)
            body += g
            x += wdt + 8
        body += text(x + 2, cy + 28, pr["name"], P["fg"], 15, "700")
        body += text(cx + 8, cy + 56, pr.get("meta", ""), P["muted"], 12)
        x, y = cx + 8, cy + 74
        for t in pr.get("tech", []):
            g, wdt = chip(x, y, t, P)
            if x + wdt > cx + cw - 12:
                x, y = cx + 8, y + 30
                g, wdt = chip(x, y, t, P)
            body += g
            x += wdt + 8
    body += line(pad + cw, top + 10, pad + cw, top + card_h - 10,
                 P["border"], 1, opacity="0.6")
    return svg_doc(W, total_h, body, "projects")


def card_stats(cfg, P, days, st):
    pad = 20
    body, ph = prompt(W / 2.0, 8, cfg["handle"], "./stats.sh", P)
    top = 8 + ph + 18

    cell, gap = 11, 3
    weeks = int(math.ceil(len(days) / 7.0)) if days else 53
    grid_w = weeks * (cell + gap)
    gx = (W - grid_w) / 2.0 + 14
    gy = top + 46
    card_h = 46 + 7 * (cell + gap) + 62
    total_h = int(top + card_h + 8)

    body += rect(1, top, W - 2, card_h, P["panel"], rx=12,
                 stroke=P["border"], sw=1)

    for i, lbl in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        body += text(gx - 8, gy + i * (cell + gap) + cell - 1, lbl, P["muted"],
                     9.5, anchor="end")

    last_month, label_x = None, -999
    if days:
        first = datetime.date(*map(int, days[0][0].split("-")))
        offset = (first.weekday() + 1) % 7          # calendar starts on Sunday
        for idx, (date, count, lvl) in enumerate(days):
            pos = idx + offset
            wk, dow = divmod(pos, 7)
            x = gx + wk * (cell + gap)
            y = gy + dow * (cell + gap)
            body += rect(x, y, cell, cell, P["cells"][min(lvl, 4)], rx=2)
            mon = date[5:7]
            if dow == 0 and mon != last_month:
                last_month = mon
                if x - label_x >= 34:
                    label_x = x
                    name = datetime.date(2000, int(mon), 1).strftime("%b")
                    body += text(x, gy - 8, name, P["muted"], 9.5)

    fy = gy + 7 * (cell + gap) + 30
    segs = [("%dd" % st["current"], P["green"], "700"), (" current streak", P["muted"], "400"),
            ("  ·  ", P["border"], "400"),
            ("%dd" % st["longest"], P["fg"], "700"), (" longest", P["muted"], "400"),
            ("  ·  ", P["border"], "400"),
            ("%d" % st["best"], P["fg"], "700"), (" best day", P["muted"], "400"),
            ("  ·  ", P["border"], "400"),
            ("%d" % st["total"], P["fg"], "700"), (" this year", P["muted"], "400")]
    full = "".join(s[0] for s in segs)
    tspans = "".join('<tspan fill="%s" font-weight="%s">%s</tspan>'
                     % (c, wt, esc(t)) for t, c, wt in segs)
    body += ('<text x="%.1f" y="%.1f" font-family="%s" font-size="13" '
             'xml:space="preserve">%s</text>'
             % ((W - tw(full, 13)) / 2.0, fy, MONO, tspans))

    lx = W - pad - 24 - 5 * 14 - 34
    body += text(lx, fy + 22, "Less", P["muted"], 10)
    for i in range(5):
        body += rect(lx + 30 + i * 14, fy + 13, 11, 11, P["cells"][i], rx=2)
    body += text(lx + 30 + 5 * 14 + 4, fy + 22, "More", P["muted"], 10)
    return svg_doc(W, total_h, body, "contributions")


def card_connect(cfg, P):
    body, ph = prompt(W / 2.0, 8, cfg["handle"], "./connect.sh", P)
    foot = cfg.get("footer", "")
    h = 8 + ph + 26
    if foot:
        fw = tw(foot, 11) + 24
        body += rect((W - fw) / 2.0, h, fw, 24, P["pill"], rx=6)
        body += text(W / 2.0, h + 16, foot, P["muted"], 11, anchor="middle")
        h += 32
    return svg_doc(W, int(h), body, "connect")


def card_link(link, P):
    fs, h = 12, 34
    label = link["label"].upper()
    slug = link.get("icon")
    colr = LINK_COLORS.get(slug, P["accent"])
    ic = 17 if slug and icon_path(slug) else 0
    sp = 1.6
    lw = tw(label, fs) + sp * len(label)
    wdt = 10 + (ic + 9 if ic else 0) + lw + 10
    body = ""
    if ic:
        body += glyph(slug, 10, (h - ic) / 2.0, ic, colr)
    body += ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
             'font-weight="700" fill="%s" letter-spacing="%s" '
             'xml:space="preserve">%s</text>'
             % (10 + (ic + 9 if ic else 0), h / 2.0 + 4.5, MONO, fs, P["fg"],
                sp, esc(label)))
    return svg_doc(int(wdt), h, body, link["label"])


# --------------------------------------------------------------------------
# readme
# --------------------------------------------------------------------------
def picture(name, stamp, alt, width=None):
    wa = ' width="%d"' % width if width else ""
    return ('<picture>\n'
            '  <source media="(prefers-color-scheme: dark)" '
            'srcset="./%s-dark.svg?v=%s">\n'
            '  <img alt="%s" src="./%s-light.svg?v=%s"%s>\n'
            '</picture>' % (name, stamp, alt, name, stamp, wa))


def write_readme(cfg, stamp, n_links):
    links = "\n".join(
        '  <a href="%s">%s</a>' % (
            l["url"], picture("link-%d" % i, stamp, l["label"]))
        for i, l in enumerate(cfg["links"]))
    md = """<div align="center">

%s

%s

%s

<p>
%s
</p>

%s

</div>
""" % (picture("info-card", stamp, "whoami", 900),
       picture("projects", stamp, "projects", 900),
       picture("stats", stamp, "contributions", 900),
       links,
       picture("connect", stamp, "connect", 900))
    extra = cfg.get("readme_extra", "").strip()
    if extra:
        md += "\n" + extra + "\n"
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(md)


# --------------------------------------------------------------------------
def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "profile.json")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    print("· rendering ASCII portrait")
    art = ascii_art(cfg.get("avatar"), cfg.get("art", {}))

    print("· fetching contributions for %s" % cfg["username"])
    days = fetch_contributions(cfg["username"])
    st = streaks(days)
    print("  %d days, current=%d longest=%d best=%d total=%d"
          % (len(days), st["current"], st["longest"], st["best"], st["total"]))

    for theme, P in THEMES.items():
        out = {
            "info-card": card_info(cfg, P, art),
            "projects": card_projects(cfg, P),
            "stats": card_stats(cfg, P, days, st),
            "connect": card_connect(cfg, P),
        }
        for i, l in enumerate(cfg["links"]):
            out["link-%d" % i] = card_link(l, P)
        for name, doc in out.items():
            path = os.path.join(ROOT, "%s-%s.svg" % (name, theme))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(doc)
        print("· wrote %d %s svg files" % (len(out), theme))

    # drop chips left over from a longer `links` list in a previous run
    for stale in os.listdir(ROOT):
        m = re.match(r"link-(\d+)-(dark|light)\.svg$", stale)
        if m and int(m.group(1)) >= len(cfg["links"]):
            os.remove(os.path.join(ROOT, stale))
            print("· removed stale %s" % stale)

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M")
    write_readme(cfg, stamp, len(cfg["links"]))
    print("· README.md updated (cache stamp %s)" % stamp)


if __name__ == "__main__":
    main()
