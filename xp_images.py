"""
xp_images.py - pictures for the Flight Ideas app.

  * draw_route_map()   - map of the route with nearby airports, distances, twist spot
  * draw_airport()     - airport diagram drawn to scale from X-Plane's runway data
  * draw_sky()         - picture of the time of day and weather for the flight
  * aircraft_icon()    - the plane's own thumbnail from its X-Plane folder
  * PhotoFetcher       - a photo of the airport from Wikipedia (cached on disk)

Pillow (pip install pillow) is optional: without it PNG images still work, but
JPEG photos (most Wikipedia photos) can't be shown.
"""
from __future__ import annotations

import html
import json
import math
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

import tkinter as tk

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False

UA = "XPlaneFlightIdeas/2.5 (personal flight-sim helper; python urllib)"

SURF_COLOR = {"paved": "#4a4f55", "grass": "#6a9e3f", "dirt": "#9b7447", "gravel": "#b49e7a",
              "lakebed": "#d6c79c", "water": "#3f86c6", "snow": "#e8eef5", "other": "#777777"}


def recheck_pil():
    global HAVE_PIL, Image, ImageTk
    try:
        from PIL import Image as _I, ImageTk as _T
        Image, ImageTk, HAVE_PIL = _I, _T, True
    except Exception:
        HAVE_PIL = False
    return HAVE_PIL


# ==========================================================================
# Loading images
# ==========================================================================
def load_image(path, max_w, max_h):
    """A PhotoImage that fits in max_w x max_h, or None."""
    try:
        path = str(path)
        if HAVE_PIL:
            im = Image.open(path)
            im.thumbnail((max_w, max_h), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        if path.lower().endswith((".png", ".gif")):
            img = tk.PhotoImage(file=path)
            f = max(1, math.ceil(max(img.width() / max_w, img.height() / max_h)))
            return img.subsample(f, f) if f > 1 else img
    except Exception:
        return None
    return None


def aircraft_icon(xp_root, acf_rel, livery=None):
    """Path of the aircraft's thumbnail picture (livery-specific if there is one)."""
    if not acf_rel:
        return None
    acf = Path(xp_root) / acf_rel
    stem, d = acf.stem, acf.parent
    names = [f"{stem}_icon11.png", f"{stem}_icon11_thumb.png", f"{stem}_icon.png"]
    cands = []
    if livery:
        cands += [d / "liveries" / livery / n for n in names]
    cands += [d / n for n in names]
    for c in cands:
        if c.exists():
            return c
    try:
        return next(iter(sorted(d.glob("*_icon11.png"))), None)
    except OSError:
        return None


# ==========================================================================
# Small helpers
# ==========================================================================
def _size(cv):
    cv.update_idletasks()
    w, h = cv.winfo_width(), cv.winfo_height()
    if w < 20:
        w, h = int(cv["width"]), int(cv["height"])
    return w, h


def _nice(x):
    """A round number (1, 2, 5 x 10^n) close to x."""
    if x <= 0:
        return 1
    e = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 5, 10):
        if x <= m * e * 1.5:
            return m * e
    return 10 * e


def _mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def _label(cv, x, y, text, fill="#222", bg="#ffffff", font=("TkDefaultFont", 8), anchor="center", bold=False):
    if bold:
        font = (font[0], font[1], "bold")
    t = cv.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)
    if bg:
        x1, y1, x2, y2 = cv.bbox(t)
        r = cv.create_rectangle(x1 - 2, y1 - 1, x2 + 2, y2 + 1, fill=bg, outline="")
        cv.tag_lower(r, t)
    return t


def _dest_point(lat, lon, brg, dist_nm):
    R = 3440.065
    p1, l1, b, dr = math.radians(lat), math.radians(lon), math.radians(brg), dist_nm / R
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


# ==========================================================================
# Route map
# ==========================================================================
def draw_route_map(cv, stops, all_airports=(), hidden=False, failure=None, wind=None, title="", here=None):
    cv.delete("all")
    W, H = _size(cv)
    cv.create_rectangle(0, 0, W, H, fill="#e9eef1", outline="")
    if not stops:
        return
    pts = [(a["lat"], a["lon"]) for a in stops]
    if hidden and len(stops) > 1:
        from xp_flight_ideas import crs, d
        pts = [pts[0], _dest_point(stops[0]["lat"], stops[0]["lon"], crs(stops[0], stops[1]), d(stops[0], stops[1]))]
    if failure:
        pts.append((failure["lat"], failure["lon"]))
    if here:
        pts.append((here["lat"], here["lon"]))
    lat0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    xs, ys = [p[1] * k for p in pts], [p[0] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx, sy = max(maxx - minx, 0.35), max(maxy - miny, 0.35)
    m = 52
    scale = min((W - 2 * m) / sx, (H - 2 * m) / sy)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    def P(lat, lon):
        return W / 2 + (lon * k - cx) * scale, H / 2 - (lat - cy) * scale

    # lat/lon grid
    lat_span = H / scale
    step = min((s for s in (0.1, 0.25, 0.5, 1, 2, 5, 10) if lat_span / s <= 6), default=10)
    la = math.floor((cy - lat_span) / step) * step
    while la < cy + lat_span:
        _, y = P(la, 0)
        cv.create_line(0, y, W, y, fill="#d5dde2")
        cv.create_text(3, y - 1, text=f"{la:.2f}".rstrip("0").rstrip(".") + "°", anchor="sw",
                       fill="#9aa7b0", font=("TkDefaultFont", 7))
        la += step
    lon_span = W / scale / k
    lo = math.floor((cx / k - lon_span) / step) * step
    while lo < cx / k + lon_span:
        x, _ = P(0, lo)
        cv.create_line(x, 0, x, H, fill="#d5dde2")
        lo += step

    # other airports
    lat_lo, lat_hi = cy - H / 2 / scale, cy + H / 2 / scale
    lon_lo, lon_hi = (cx - W / 2 / scale) / k, (cx + W / 2 / scale) / k
    near = [a for a in all_airports if lat_lo < a["lat"] < lat_hi and lon_lo < a["lon"] < lon_hi]
    if len(near) > 2500:
        near = near[:: len(near) // 2500 + 1]
    ids = {a["id"] for a in stops}
    for a in near:
        if a["id"] in ids and not hidden:
            continue
        x, y = P(a["lat"], a["lon"])
        big = a.get("tower")
        r = 2.2 if big else 1.4
        cv.create_oval(x - r, y - r, x + r, y + r, fill="#7f8f99" if big else "#a9b5bc", outline="")

    # route
    from xp_flight_ideas import d as dist
    if hidden and len(stops) > 1:
        x1, y1 = P(*pts[0])
        x2, y2 = P(*pts[1])
        cv.create_line(x1, y1, x2, y2, fill="#7a4cc2", width=3, dash=(8, 5), arrow="last", arrowshape=(12, 14, 5))
        cv.create_text(x2, y2 - 16, text="?", font=("TkDefaultFont", 18, "bold"), fill="#7a4cc2")
        _label(cv, (x1 + x2) / 2, (y1 + y2) / 2, f"{dist(stops[0], stops[1]):.0f} nm")
        draw = [stops[0]]
    else:
        for a, b in zip(stops, stops[1:]):
            x1, y1 = P(a["lat"], a["lon"])
            x2, y2 = P(b["lat"], b["lon"])
            if abs(x1 - x2) + abs(y1 - y2) < 2:
                continue
            cv.create_line(x1, y1, x2, y2, fill="#1f6fd1", width=3, arrow="last", arrowshape=(11, 13, 5))
            _label(cv, (x1 + x2) / 2, (y1 + y2) / 2, f"{dist(a, b):.0f} nm")
        draw = stops
    seen = set()
    for i, a in enumerate(draw):
        if a["id"] in seen:
            continue
        seen.add(a["id"])
        x, y = P(a["lat"], a["lon"])
        col = "#1a9e4b" if i == 0 else ("#d23c3c" if i == len(draw) - 1 else "#f0a020")
        cv.create_oval(x - 6, y - 6, x + 6, y + 6, fill=col, outline="white", width=2)
        right = x < W - 70
        _label(cv, x + 9 if right else x - 9, y - 9, a["id"], anchor="sw" if right else "se", bold=True, bg="#ffffff")

    if failure:
        x, y = P(failure["lat"], failure["lon"])
        cv.create_line(x - 6, y - 6, x + 6, y + 6, fill="#c00", width=3)
        cv.create_line(x - 6, y + 6, x + 6, y - 6, fill="#c00", width=3)
        _label(cv, x, y + 14, "twist", fill="#c00")

    if here:
        x, y = P(here["lat"], here["lon"])
        hd = math.radians(here.get("hdg", 0) or 0)
        pp = [(0, -11), (8, 9), (0, 4), (-8, 9)]
        poly = []
        for dx, dy in pp:
            poly += [x + dx * math.cos(hd) - dy * math.sin(hd), y + dx * math.sin(hd) + dy * math.cos(hd)]
        cv.create_polygon(poly, fill="#e33", outline="white", width=2)
        _label(cv, x + 12, y + 10, here.get("label", "you"), anchor="nw", bold=True, fill="#e33")

    # scale bar (1 deg lat = 60 nm)
    nm_px = 60 / scale
    L = _nice(nm_px * 110)
    px = L / nm_px
    cv.create_line(10, H - 12, 10 + px, H - 12, width=3, fill="#333")
    cv.create_line(10, H - 17, 10, H - 7, width=2, fill="#333")
    cv.create_line(10 + px, H - 17, 10 + px, H - 7, width=2, fill="#333")
    cv.create_text(10 + px / 2, H - 20, text=f"{L:g} nm", fill="#333", font=("TkDefaultFont", 8))
    # north arrow
    cv.create_line(W - 18, 36, W - 18, 12, arrow="last", width=2, fill="#333")
    cv.create_text(W - 18, 44, text="N", font=("TkDefaultFont", 9, "bold"), fill="#333")
    # wind
    if wind and wind[1] > 2:
        wdir, wspd = wind
        cxw, cyw, r = 30, H - 62, 14
        a = math.radians(wdir)
        x1, y1 = cxw + r * math.sin(a), cyw - r * math.cos(a)
        cv.create_line(x1, y1, 2 * cxw - x1, 2 * cyw - y1, arrow="last", width=2, fill="#1f6fd1")
        _label(cv, cxw + 20, cyw, f"wind {wdir:03d}@{wspd}", anchor="w", fill="#1f6fd1")
    if title:
        _label(cv, 8, 8, title, anchor="nw", bold=True, font=("TkDefaultFont", 9))
    # legend (bottom right)
    lx = W - 140
    for col, txt in (("#1a9e4b", "start"), ("#f0a020", "stop"), ("#d23c3c", "end")):
        cv.create_oval(lx, H - 16, lx + 8, H - 8, fill=col, outline="")
        cv.create_text(lx + 11, H - 12, text=txt, anchor="w", font=("TkDefaultFont", 7), fill="#555")
        lx += 44


# ==========================================================================
# Airport diagram
# ==========================================================================
def draw_airport(cv, apt, wind=None, fav_end=None):
    cv.delete("all")
    W, H = _size(cv)
    cv.create_rectangle(0, 0, W, H, fill="#f3f1ea", outline="")
    if not apt:
        return
    rws = [r for r in apt["rwys"] if "c" in r]
    if not rws:
        cv.create_text(W / 2, H / 2, text="No runway coordinates.\nPress 'Rescan scenery' once to enable diagrams.",
                       justify="center", fill="#666")
        return
    lat0, lon0 = apt["lat"], apt["lon"]
    k = math.cos(math.radians(lat0))
    FT = 60 * 6076.1

    def ft(lat, lon):
        return (lon - lon0) * k * FT, (lat - lat0) * FT
    pts = []
    for r in rws:
        c = r["c"]
        pts += [ft(c[0], c[1])] + ([ft(c[2], c[3])] if len(c) == 4 else [])
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    span = max(maxx - minx, maxy - miny, 800)
    m = 46
    scale = min((W - 2 * m) / max(maxx - minx, span * 0.3), (H - 2 * m - 16) / max(maxy - miny, span * 0.3))
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    def P(x, y):
        return W / 2 + (x - cx) * scale, H / 2 + 8 - (y - cy) * scale

    for r in sorted(rws, key=lambda r: r["s"] != "paved"):
        c = r["c"]
        if len(c) == 2:   # helipad
            x, y = P(*ft(c[0], c[1]))
            rr = max(6, r["len"] * scale / 2)
            cv.create_oval(x - rr, y - rr, x + rr, y + rr, fill="#4a4f55", outline="white")
            cv.create_text(x, y, text="H", fill="white", font=("TkDefaultFont", 9, "bold"))
            continue
        x1, y1 = P(*ft(c[0], c[1]))
        x2, y2 = P(*ft(c[2], c[3]))
        wpx = max(4, r["w"] * scale)
        col = SURF_COLOR.get(r["s"], "#777")
        cv.create_line(x1, y1, x2, y2, width=wpx, fill=col, capstyle="butt")
        if r["s"] == "paved" and wpx >= 6:
            cv.create_line(x1, y1, x2, y2, width=1, fill="white", dash=(6, 6))
        L = math.hypot(x2 - x1, y2 - y1) or 1
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        off = wpx / 2 + 12
        for end, (ex, ey), sgn in ((r["e"][0], (x1, y1), -1), (r["e"][1], (x2, y2), 1)):
            tx, ty = ex + ux * off * sgn, ey + uy * off * sgn
            fav = end == fav_end
            _label(cv, tx, ty, end, fill="#0a7d38" if fav else "#222", bg="#ffffff" if not fav else "#dff5e6",
                   bold=fav)
    # title
    _label(cv, 8, 8, f"{apt['id']}  {apt['name']}  -  elev {apt['elev']:,} ft", anchor="nw", bold=True,
           font=("TkDefaultFont", 9))
    # scale bar in feet
    L = _nice(110 / scale)
    px = L * scale
    cv.create_line(10, H - 12, 10 + px, H - 12, width=3, fill="#333")
    cv.create_text(10 + px / 2, H - 21, text=f"{L:,.0f} ft", fill="#333", font=("TkDefaultFont", 8))
    cv.create_line(W - 18, 50, W - 18, 28, arrow="last", width=2, fill="#333")
    cv.create_text(W - 18, 58, text="N", font=("TkDefaultFont", 9, "bold"), fill="#333")
    if wind and wind[1] > 2:
        wdir, wspd = wind
        cxw, cyw, rr = W - 56, 40, 16
        a = math.radians(wdir)
        x1, y1 = cxw + rr * math.sin(a), cyw - rr * math.cos(a)
        cv.create_line(x1, y1, 2 * cxw - x1, 2 * cyw - y1, arrow="last", width=3, fill="#1f6fd1")
        cv.create_text(cxw, cyw + 26, text=f"wind {wdir:03d}@{wspd}", font=("TkDefaultFont", 8), fill="#1f6fd1")
    # legend of surfaces used
    used = sorted({r["s"] for r in rws if r["s"] != "helipad"})
    lx = W - 10
    for s in reversed(used):
        t = cv.create_text(lx, H - 12, text=s, anchor="e", font=("TkDefaultFont", 7), fill="#555")
        x1 = cv.bbox(t)[0]
        cv.create_rectangle(x1 - 12, H - 16, x1 - 3, H - 8, fill=SURF_COLOR.get(s, "#777"), outline="")
        lx = x1 - 18


# ==========================================================================
# Sky / conditions picture
# ==========================================================================
SKY_COLORS = {  # (top, horizon)
    "night": ("#070d1d", "#1c2e4d"), "dawn": ("#3d5a8a", "#f4a46a"), "day": ("#2f7ed8", "#bcdcf7"),
    "golden": ("#4a6fa5", "#f7b267"),
}


def draw_sky(cv, month, hour, wx, elev=0, lat=40, when_text=""):
    import xp_flight_ideas as core
    cv.delete("all")
    W, H = _size(cv)
    rise, sset = core._solar(month, lat)
    if hour < rise - 0.6 or hour > sset + 0.8:
        phase = "night"
    elif hour < rise + 0.9:
        phase = "dawn"
    elif hour > sset - 1.6:
        phase = "golden"
    else:
        phase = "day"
    layers = wx.layers
    cover = min(1.0, sum(c for t, c, b, th in layers if t != "cirrus"))
    top, hor = SKY_COLORS[phase]
    gray_t, gray_h = ("#1d232b", "#39414b") if phase == "night" else ("#7d8792", "#b8bfc6")
    top, hor = _mix(top, gray_t, cover * 0.75), _mix(hor, gray_h, cover * 0.75)
    ground = int(H * 0.78)
    for i in range(0, ground, 4):
        cv.create_rectangle(0, i, W, i + 4, fill=_mix(top, hor, i / ground), outline="")
    rng = random.Random(hash((wx.sky, month, int(hour))) & 0xFFFF)
    # sun / moon
    if phase != "night" and cover < 0.95:
        f = (hour - rise) / max(1, sset - rise)
        sx = W * (0.1 + 0.8 * f)
        sy = ground - math.sin(math.pi * min(1, max(0, f))) * (ground - 40) - 10
        col = "#ffd54a" if phase == "day" else "#ffb347"
        cv.create_oval(sx - 16, sy - 16, sx + 16, sy + 16, fill=col, outline="")
    elif phase == "night":
        for _ in range(int(60 * (1 - cover))):
            x, y = rng.uniform(0, W), rng.uniform(0, ground * 0.8)
            cv.create_oval(x, y, x + 1.5, y + 1.5, fill="#dfe8ff", outline="")
        if cover < 0.9:
            cv.create_oval(W * 0.78, 24, W * 0.78 + 26, 50, fill="#f1f1da", outline="")
            cv.create_oval(W * 0.78 + 8, 20, W * 0.78 + 34, 46, fill=top, outline="")

    def alt_y(ft):
        return ground - math.sqrt(min(ft, 26000) / 26000) * (ground - 18)
    dark = phase == "night"
    for typ, c, base, thick in layers:
        yb, yt = alt_y(base), alt_y(base + thick)
        if typ == "cirrus":
            for _ in range(int(12 * c) + 2):
                x = rng.uniform(-40, W)
                y = rng.uniform(yt, yb)
                cv.create_line(x, y, x + rng.uniform(50, 120), y - rng.uniform(2, 8), fill="#eef3f8" if not dark else "#5a6475", width=2)
        elif typ == "stratus" or c >= 0.85:
            col = "#9aa3ad" if not dark else "#2d333b"
            cv.create_rectangle(0, max(8, yt), W, yb, fill=col, outline="")
            for x in range(0, W, 18):
                cv.create_oval(x - 6, yb - 7, x + 20, yb + 5 + rng.uniform(0, 5), fill=col, outline="")
        else:
            n = int(c * 11) + 1
            for _ in range(n):
                x = rng.uniform(10, W - 10)
                w = rng.uniform(40, 80)
                hgt = max(14, min(yb - yt, 90) * (1.6 if typ == "cumulonimbus" else 0.6))
                col = "#f7f9fb" if not dark else "#3a424d"
                shade = "#d5dbe1" if not dark else "#2a3038"
                for j in range(4):
                    ox, oy = rng.uniform(-w / 2, w / 2), rng.uniform(-hgt / 2, 0)
                    r = rng.uniform(w * 0.25, w * 0.45)
                    cv.create_oval(x + ox - r, yb + oy - r * 0.8 - hgt * 0.3, x + ox + r, yb + oy + r * 0.3,
                                   fill=col, outline="")
                cv.create_rectangle(x - w * 0.7, yb - 4, x + w * 0.7, yb + 2, fill=shade, outline="")
                if typ == "cumulonimbus":
                    cv.create_polygon(x - w * 1.3, yt + 6, x + w * 1.3, yt + 6, x + w * 0.4, yt + 22, x - w * 0.4, yt + 22,
                                      fill=col, outline="")
    precip = wx.precip
    snow = wx.temp <= 0
    if precip:
        for _ in range(int(160 * precip)):
            x, y = rng.uniform(0, W), rng.uniform(alt_y(layers[0][2]) if layers else 0, ground)
            if snow:
                cv.create_oval(x, y, x + 2.5, y + 2.5, fill="white", outline="")
            else:
                cv.create_line(x, y, x - 3, y + 9, fill="#a9c4e0" if not dark else "#5d7189")
    # ground
    month_col = ("#e9eef4" if (snow and month in (11, 0, 1, 2)) else
                 "#6e9a45" if month in (4, 5, 6, 7, 8) else "#8f8a5a")
    if dark:
        month_col = _mix(month_col, "#000000", 0.7)
    cv.create_rectangle(0, ground, W, H, fill=month_col, outline="")
    cv.create_rectangle(W * 0.1, ground + 12, W * 0.9, ground + 22, fill="#3d4247", outline="")
    for x in range(int(W * 0.12), int(W * 0.88), 22):
        cv.create_line(x, ground + 17, x + 10, ground + 17, fill="white")
    if dark:
        for x in range(int(W * 0.1), int(W * 0.9) + 1, 16):
            cv.create_oval(x - 1.5, ground + 10, x + 1.5, ground + 13, fill="#ffe9a8", outline="")
            cv.create_oval(x - 1.5, ground + 21, x + 1.5, ground + 24, fill="#ffe9a8", outline="")
    # fog / haze
    if wx.vis < 3:
        fogc = "#c9cfd4" if not dark else "#3b4046"
        cv.create_rectangle(0, ground - (3 - wx.vis) * 40, W, H, fill=fogc, outline="", stipple="gray50")
    # windsock
    sx, sy = W - 40, ground
    cv.create_line(sx, sy, sx, sy - 44, width=2, fill="#ddd" if dark else "#555")
    spd = wx.wind_spd
    if spd > 2:
        east = math.sin(math.radians(wx.wind_dir))       # wind FROM the east blows toward the west
        dirx = -1 if east > 0 else 1
        L = 10 + min(spd, 15) * 2
        droop = max(0, 15 - spd) * 1.5
        cv.create_polygon(sx, sy - 44, sx, sy - 34, sx + dirx * L, sy - 37 + droop, sx + dirx * L, sy - 41 + droop,
                          fill="#ff7f27", outline="white")
    else:
        cv.create_polygon(sx, sy - 44, sx, sy - 34, sx + 3, sy - 20, sx + 6, sy - 22, fill="#ff7f27", outline="")
    # caption
    cap = f"{when_text}\n{wx.sky_text}  |  {wx.temp} C  |  {wx.wind_str()}"
    t = cv.create_text(8, 8, text=cap, anchor="nw", fill="white", font=("TkDefaultFont", 9, "bold"), width=W - 24)
    x1, y1, x2, y2 = cv.bbox(t)
    r = cv.create_rectangle(x1 - 4, y1 - 3, x2 + 4, y2 + 3, fill="#000000", outline="", stipple="gray50")
    cv.tag_lower(r, t)


# ==========================================================================
# Airport photos from Wikipedia
# ==========================================================================
ABBR = {"RGNL": "Regional", "MUNI": "Municipal", "INTL": "International", "FLD": "Field", "CO": "County",
        "MEML": "Memorial", "ARPT": "Airport", "APT": "Airport", "NATL": "National", "MTN": "Mountain",
        "CNTY": "County", "SPB": "Seaplane Base", "EXEC": "Executive", "ST": "State", "MT": "Mount",
        "FT": "Fort", "PT": "Point", "LK": "Lake", "INTERNATIONAL": "International"}
GENERIC = {"airport", "regional", "municipal", "international", "field", "county", "memorial", "the", "of",
           "air", "base", "airfield", "airpark", "executive", "state", "city", "national", "and", "de", "la"}
AIRPORT_WORDS = re.compile(r"airport|airfield|field|airpark|airstrip|heliport|seaplane|air base|aerodrome|"
                           r"air station|landing strip|spaceport", re.I)


def expand_name(name):
    words = re.split(r"[\s/\-]+", name)
    return " ".join(ABBR.get(w.upper().strip("."), w) for w in words if w)


class PhotoFetcher:
    def __init__(self, cache_dir: Path):
        self.dir = Path(cache_dir) / "photos"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.idx_file = self.dir / "index.json"
        try:
            self.idx = json.loads(self.idx_file.read_text())
        except Exception:
            self.idx = {}

    def _save(self):
        try:
            self.idx_file.write_text(json.dumps(self.idx, indent=0))
        except OSError:
            pass

    @staticmethod
    def _api(**params):
        params.update(format="json", formatversion="2")
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())

    def find_page(self, apt):
        wiki = (apt.get("wiki") or "").strip()
        if wiki and "wikipedia.org/wiki/" in wiki:
            return urllib.parse.unquote(wiki.split("/wiki/")[-1]).replace("_", " ")
        code = apt["id"].upper()
        codes = {code} | {a.upper() for a in apt.get("alias", [])}
        name = expand_name(apt["name"])
        sig = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", name)} - GENERIC
        queries = []
        if re.fullmatch(r"[A-Z]{4}", code):
            queries.append(f'"{code}" airport')
        queries.append(f"{name} airport {apt.get('state', '')}".strip())
        for q in queries:
            res = self._api(action="query", list="search", srsearch=q, srlimit=6, srprop="snippet")
            for hit in res.get("query", {}).get("search", []):
                title = hit["title"]
                if not AIRPORT_WORDS.search(title):
                    continue
                snippet = html.unescape(re.sub("<[^>]+>", "", hit.get("snippet", ""))).upper()
                twords = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", title)}
                if any(c in snippet or c in title.upper() for c in codes) or (sig and sig & twords):
                    return title
        return None

    def get(self, apt):
        """{'file', 'title', 'url'} or None. Blocking (network) - call from a thread."""
        key = apt["id"]
        if key in self.idx:
            info = self.idx[key]
            if info is None or Path(info["file"]).exists():
                return info
        title = self.find_page(apt)
        info = None
        if title:
            res = self._api(action="query", titles=title, prop="pageimages|info", piprop="thumbnail",
                            pithumbsize=720, inprop="url", redirects=1)
            pages = res.get("query", {}).get("pages", [])
            page = pages[0] if pages else {}
            src = (page.get("thumbnail") or {}).get("source")
            url = page.get("fullurl") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
            if src:
                ext = Path(urllib.parse.urlparse(src).path).suffix.lower() or ".jpg"
                f = self.dir / (re.sub(r"[^A-Za-z0-9_-]", "_", key) + ext)
                req = urllib.request.Request(src, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    f.write_bytes(r.read())
                info = {"file": str(f), "title": page.get("title", title), "url": url}
            else:
                info = {"file": "", "title": page.get("title", title), "url": url}
        self.idx[key] = info
        self._save()
        return info


# ==========================================================================
# Live-weather map
# ==========================================================================
WX_COLORS = {"VFR": "#2e9e4f", "MVFR": "#2f6fd6", "IFR": "#d23c3c", "LIFR": "#b03cb8", "": "#999999"}


def draw_wx_map(cv, obs, results=(), center=None, radius_nm=300, selected=None, home=None):
    """Weather stations coloured by flight category; bad-weather matches drawn bigger."""
    cv.delete("all")
    W, H = _size(cv)
    cv.create_rectangle(0, 0, W, H, fill="#eef1f3", outline="")
    pts = []
    if center:
        dlat = radius_nm / 60
        dlon = radius_nm / (60 * max(0.2, math.cos(math.radians(center["lat"]))))
        pts = [(center["lat"] - dlat, center["lon"] - dlon), (center["lat"] + dlat, center["lon"] + dlon)]
    elif results:
        pts = [(r["obs"]["lat"], r["obs"]["lon"]) for r in results[:60]]
    if not pts:
        cv.create_text(W / 2, H / 2, text="Press 'Refresh weather', then 'Find'.", fill="#777")
        return
    lat0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    xs, ys = [p[1] * k for p in pts], [p[0] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx, sy = max(maxx - minx, 0.5), max(maxy - miny, 0.5)
    m = 24
    scale = min((W - 2 * m) / sx, (H - 2 * m) / sy)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    def P(lat, lon):
        return W / 2 + (lon * k - cx) * scale, H / 2 - (lat - cy) * scale
    lat_lo, lat_hi = cy - H / 2 / scale, cy + H / 2 / scale
    lon_lo, lon_hi = (cx - W / 2 / scale) / k, (cx + W / 2 / scale) / k
    # graticule
    step = _nice((lat_hi - lat_lo) / 5)
    la = math.floor(lat_lo / step) * step
    while la <= lat_hi:
        _, y = P(la, 0)
        cv.create_line(0, y, W, y, fill="#dde3e7")
        la += step
    lo = math.floor(lon_lo / step) * step
    while lo <= lon_hi:
        x, _ = P(0, lo)
        cv.create_line(x, 0, x, H, fill="#dde3e7")
        lo += step
    view = [o for o in obs if lat_lo < o["lat"] < lat_hi and lon_lo < o["lon"] < lon_hi]
    if len(view) > 5000:
        view = view[:: len(view) // 5000 + 1]
    for o in view:
        x, y = P(o["lat"], o["lon"])
        c = WX_COLORS.get(o.get("cat") or "", "#999")
        cv.create_oval(x - 2, y - 2, x + 2, y + 2, fill=c, outline="")
    for r in results:
        o = r["obs"]
        if not (lat_lo < o["lat"] < lat_hi and lon_lo < o["lon"] < lon_hi):
            continue
        x, y = P(r["apt"]["lat"], r["apt"]["lon"])
        rad = 4 + min(8, r["score"])
        c = WX_COLORS.get(o.get("cat") or "", "#999")
        cv.create_oval(x - rad, y - rad, x + rad, y + rad, fill=c, outline="white", width=1.5)
        if "TS" in (o.get("wx") or "") or o.get("cb"):
            cv.create_text(x, y, text="⚡", font=("TkDefaultFont", 8), fill="white")
    if home:
        x, y = P(home["lat"], home["lon"])
        cv.create_polygon(x, y - 9, x - 7, y + 5, x + 7, y + 5, fill="#1a9e4b", outline="white", width=2)
        _label(cv, x + 9, y, home["id"], anchor="w", bold=True)
    if selected:
        x, y = P(selected["apt"]["lat"], selected["apt"]["lon"])
        cv.create_oval(x - 15, y - 15, x + 15, y + 15, outline="#111", width=2)
        _label(cv, x + 17, y - 12, selected["apt"]["id"], anchor="w", bold=True)
        if home:
            hx, hy = P(home["lat"], home["lon"])
            cv.create_line(hx, hy, x, y, fill="#1f6fd1", width=2, dash=(6, 4), arrow="last")
    # legend + scale
    lx = 8
    for cat in ("VFR", "MVFR", "IFR", "LIFR"):
        cv.create_oval(lx, 8, lx + 9, 17, fill=WX_COLORS[cat], outline="")
        t = cv.create_text(lx + 12, 12, text=cat, anchor="w", font=("TkDefaultFont", 8), fill="#333")
        lx = cv.bbox(t)[2] + 10
    cv.create_text(lx, 12, text="big dots = matches", anchor="w", font=("TkDefaultFont", 8), fill="#666")
    nm_px = 60 / scale
    L = _nice(nm_px * 110)
    px = L / nm_px
    cv.create_line(10, H - 12, 10 + px, H - 12, width=3, fill="#333")
    cv.create_text(10 + px / 2, H - 21, text=f"{L:g} nm", fill="#333", font=("TkDefaultFont", 8))


# ==========================================================================
# Terrain profile
# ==========================================================================
def draw_terrain(cv, profile, cruise_ft, msa_ft):
    """Ground height along the route, with the planned cruise and a safe altitude."""
    cv.delete("all")
    W, H = _size(cv)
    cv.create_rectangle(0, 0, W, H, fill="#eaf1f6", outline="")
    if not profile:
        return
    nm_max = max(p[0] for p in profile) or 1
    top = max(max(p[1] for p in profile), cruise_ft, msa_ft) * 1.15 + 500
    bot = min(0, min(p[1] for p in profile) - 200)
    m = 34

    def P(nm, ft):
        return m + (W - m - 10) * nm / nm_max, H - 18 - (H - 28) * (ft - bot) / max(1, top - bot)
    pts = [P(nm, ft) for nm, ft, _ in profile]
    poly = [(m, H - 18)] + pts + [(W - 10, H - 18)]
    cv.create_polygon([c for xy in poly for c in xy], fill="#9a8a6a", outline="#6f6247")
    for label, ft, col in (("cruise", cruise_ft, "#1f6fd1"), ("MSA", msa_ft, "#c33")):
        _, y = P(0, ft)
        cv.create_line(m, y, W - 10, y, fill=col, width=2, dash=(6, 4) if label == "MSA" else None)
        _label(cv, W - 12, y - 8, f"{label} {ft:,.0f} ft", anchor="e", fill=col)
    # axes
    cv.create_line(m, 6, m, H - 18, fill="#888")
    cv.create_line(m, H - 18, W - 10, H - 18, fill="#888")
    for f in (0, 0.5, 1.0):
        x, _ = P(nm_max * f, 0)
        cv.create_text(x, H - 8, text=f"{nm_max * f:.0f} nm", font=("TkDefaultFont", 7), fill="#555")
    for f in (0.25, 0.5, 0.75, 1.0):
        ft = bot + (top - bot) * f
        _, y = P(0, ft)
        cv.create_text(m - 3, y, text=f"{ft:,.0f}", anchor="e", font=("TkDefaultFont", 7), fill="#555")
    src = profile[0][2] if profile else ""
    _label(cv, 8, 6, "Terrain profile (" + ("terrain data" if any(p[2] == "dem" for p in profile)
                                            else "airport elevations only") + ")", anchor="nw", bold=True)
