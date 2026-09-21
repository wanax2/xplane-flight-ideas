"""
xp_wx.py - live weather for the Flight Ideas app.

Downloads the current METARs for the whole world from aviationweather.gov
(NOAA's Aviation Weather Center - one small file, refreshed there every minute),
scores each report for "interesting" (bad) weather and finds the X-Plane
airports closest to it.

Only standard-library Python is used.  Please don't poll more often than every
few minutes - the app defaults to 10.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "XPlaneFlightIdeas/2.5 (personal flight-sim helper; python urllib)"
CACHE_URL = "https://aviationweather.gov/data/cache/metars.cache.csv.gz"
API_URL = "https://aviationweather.gov/api/data/metar"
MIN_REFRESH_S = 120

HAZARDS = {
    "any":   "Any bad weather",
    "ifr":   "Anything IFR or LIFR",
    "ceiling": "Low ceilings only",
    "vis":   "Low visibility only",
    "wind":  "Strong or gusty wind",
    "ts":    "Thunderstorms",
    "snow":  "Snow, ice, freezing rain",
    "fog":   "Fog",
    "rain":  "Rain",
    "dust":  "Dust, sand, smoke, volcanic ash",
}
SHORT = {"ifr": "low IFR", "ceiling": "a low ceiling", "vis": "low visibility", "wind": "strong wind", "ts": "thunderstorms", "snow": "snow/ice", "rain": "rain",
         "fog": "fog", "dust": "dust/smoke"}
# rough boxes: (min lat, max lat, min lon, max lon) - first match wins
CONTINENTS = {
    "Whole world": [],
    "North America & Caribbean": [(7, 84, -170, -50)],
    "South America": [(-57, 7, -93, -30)],
    "Europe": [(34, 72, -25, 45)],
    "Africa": [(-36, 37, -20, 52)],
    "Asia & Middle East": [(12, 80, 34, 180), (-11, 12, 90, 150)],
    "Oceania & Pacific": [(-50, -11, 110, 180), (-30, 25, -180, -130), (-30, 25, 150, 180)],
}


def in_area(o, area):
    boxes = CONTINENTS.get(area) or []
    if not boxes:
        return True
    return any(a <= o["lat"] <= b and c <= o["lon"] <= d for a, b, c, d in boxes)
CAT_COLOR = {"VFR": "#2e9e4f", "MVFR": "#2f6fd6", "IFR": "#d23c3c", "LIFR": "#b03cb8", "": "#999999"}
COVER = {"FEW": 0.2, "SCT": 0.4, "BKN": 0.75, "OVC": 1.0, "OVX": 1.0, "VV": 1.0}


# ==========================================================================
# Parsing helpers
# ==========================================================================
def _num(v, default=None):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("+", "").replace("P", "").replace("M", "")
    if not s or s.upper() in ("VRB", "NAN"):
        return default
    try:
        if " " in s:                     # "1 1/2"
            a, b = s.split(" ", 1)
            return float(a) + _num(b, 0)
        if "/" in s:
            a, b = s.split("/", 1)
            return float(a) / float(b)
        return float(s)
    except (ValueError, ZeroDivisionError):
        return default


def flight_category(ceiling, vis):
    c = ceiling if ceiling is not None else 99999
    v = vis if vis is not None else 99
    if c < 500 or v < 1:
        return "LIFR"
    if c < 1000 or v < 3:
        return "IFR"
    if c <= 3000 or v <= 5:
        return "MVFR"
    return "VFR"


def _finish(o):
    """Fill derived fields: ceiling, category, CB flag."""
    cl = o["clouds"]
    ceil = [b for c, b in cl if c in ("BKN", "OVC", "OVX", "VV") and b is not None]
    o["ceiling"] = min(ceil) if ceil else None
    if not o.get("cat"):
        o["cat"] = flight_category(o["ceiling"], o["vis"])
    raw = o.get("raw", "")
    o["cb"] = bool(re.search(r"\b(FEW|SCT|BKN|OVC)\d{3}(CB|TCU)\b", raw))
    if not o.get("wx"):
        m = re.findall(r"(?<=\s)([+-]|VC)?(TS|SH|FZ|MI|BC|BL|DR)?(RA|SN|DZ|GR|GS|PL|IC|UP|FG|BR|HZ|FU|SQ|FC|DS|SS)+(?=\s)",
                       " " + raw + " ")
        o["wx"] = " ".join("".join(t) for t in m)
        if re.search(r"\sTS\s", " " + raw + " ") and "TS" not in o["wx"]:
            o["wx"] = (o["wx"] + " TS").strip()
    return o


def parse_cache_csv(text):
    """aviationweather.gov metars.cache.csv -> list of observations."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("raw_text")), None)
    if start is None:
        raise ValueError("unexpected METAR file format")
    rows = csv.reader(lines[start:])
    head = next(rows)
    col = {}
    for i, h in enumerate(head):
        col.setdefault(h, i)
    sky_i = [i for i, h in enumerate(head) if h == "sky_cover"]
    base_i = [i for i, h in enumerate(head) if h == "cloud_base_ft_agl"]

    def g(r, name):
        i = col.get(name)
        return r[i] if i is not None and i < len(r) else ""
    out = []
    for r in rows:
        if len(r) < 8:
            continue
        lat, lon = _num(g(r, "latitude")), _num(g(r, "longitude"))
        if lat is None or lon is None:
            continue
        clouds = []
        for si, bi in zip(sky_i, base_i):
            c = r[si] if si < len(r) else ""
            if c in COVER:
                clouds.append((c, _num(r[bi] if bi < len(r) else None)))
        wd = g(r, "wind_dir_degrees")
        o = {"id": g(r, "station_id"), "lat": lat, "lon": lon, "raw": g(r, "raw_text"),
             "time": g(r, "observation_time"), "temp": _num(g(r, "temp_c")), "dewp": _num(g(r, "dewpoint_c")),
             "wdir": None if wd.upper() == "VRB" else _num(wd), "wspd": _num(g(r, "wind_speed_kt"), 0),
             "wgst": _num(g(r, "wind_gust_kt"), 0), "vis": _num(g(r, "visibility_statute_mi")),
             "altim": _num(g(r, "altim_in_hg")), "wx": g(r, "wx_string"), "clouds": clouds,
             "cat": g(r, "flight_category"), "name": ""}
        out.append(_finish(o))
    return out


def parse_api_json(data):
    """aviationweather.gov /api/data/metar?format=json -> list of observations."""
    out = []
    for m in data:
        try:
            clouds = [(c.get("cover"), _num(c.get("base"))) for c in (m.get("clouds") or []) if c.get("cover") in COVER]
            alt = _num(m.get("altim"))
            if alt and alt > 100:           # hPa -> inHg
                alt = alt / 33.8639
            t = m.get("obsTime")
            o = {"id": m.get("icaoId", ""), "lat": float(m["lat"]), "lon": float(m["lon"]), "raw": m.get("rawOb", ""),
                 "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)) if isinstance(t, (int, float)) else str(t or ""),
                 "temp": _num(m.get("temp")), "dewp": _num(m.get("dewp")),
                 "wdir": None if str(m.get("wdir", "")).upper() == "VRB" else _num(m.get("wdir")),
                 "wspd": _num(m.get("wspd"), 0), "wgst": _num(m.get("wgst"), 0), "vis": _num(m.get("visib")),
                 "altim": alt, "wx": m.get("wxString") or "", "clouds": clouds, "cat": m.get("fltCat") or "",
                 "name": m.get("name", "")}
            out.append(_finish(o))
        except (KeyError, TypeError, ValueError):
            continue
    return out


# ==========================================================================
# Fetching (with a small on-disk cache so the app starts with data)
# ==========================================================================
class MetarSource:
    def __init__(self, cache_dir: Path):
        self.file = Path(cache_dir) / "metars.json.gz"
        self.obs, self.fetched = [], 0.0
        try:
            with gzip.open(self.file, "rt", encoding="utf-8") as f:
                d = json.load(f)
            self.obs, self.fetched = d["obs"], d["fetched"]
        except Exception:
            pass

    def age_min(self):
        return (time.time() - self.fetched) / 60 if self.fetched else None

    def refresh(self, force=False, bbox=None):
        """Download fresh METARs (blocking). Returns number of reports."""
        if not force and self.fetched and time.time() - self.fetched < MIN_REFRESH_S:
            return len(self.obs)
        err = None
        try:
            req = urllib.request.Request(CACHE_URL, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
            try:
                text = gzip.decompress(raw).decode("utf-8", "replace")
            except OSError:
                text = raw.decode("utf-8", "replace")
            obs = parse_cache_csv(text)
        except Exception as e:  # fall back to the JSON API for the area
            err, obs = e, []
        if not obs:
            b = bbox or (-90, -180, 90, 180)
            q = urllib.parse.urlencode({"bbox": f"{b[0]},{b[1]},{b[2]},{b[3]}", "format": "json"})
            req = urllib.request.Request(f"{API_URL}?{q}", headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    obs = parse_api_json(json.loads(r.read()))
            except Exception as e2:
                raise RuntimeError(f"Couldn't download weather ({err or ''} / {e2})") from None
        self.obs, self.fetched = obs, time.time()
        try:
            with gzip.open(self.file, "wt", encoding="utf-8") as f:
                json.dump({"fetched": self.fetched, "obs": obs}, f)
        except OSError:
            pass
        return len(obs)


# ==========================================================================
# Scoring
# ==========================================================================
def hazards(o):
    """Dict of hazard -> strength (0..~5) for one observation."""
    wx = (o.get("wx") or "").upper()
    h = {}
    cat = o.get("cat") or ""
    h["ifr"] = {"LIFR": 4.0, "IFR": 3.0, "MVFR": 1.2}.get(cat, 0.0)
    if "FG" in wx:
        h["ifr"] += 1.0
    spd, gst = o.get("wspd") or 0, o.get("wgst") or 0
    h["wind"] = max(0.0, (max(spd, gst * 0.9) - 12) / 5) + (1.0 if gst - spd >= 10 else 0.0)
    h["ts"] = (4.0 if "TS" in wx else 0.0) + (1.5 if o.get("cb") else 0.0) + (1.0 if "GR" in wx or "GS" in wx else 0.0) \
        + (1.5 if "SQ" in wx else 0.0)
    snow = 0.0
    if "FZ" in wx:
        snow += 4.0
    if "SN" in wx or "PL" in wx or "IC" in wx:
        snow += 3.0 if "+SN" in wx else 2.2
    if "BL" in wx:
        snow += 1.0
    h["snow"] = snow
    rain = 0.0
    if "RA" in wx or "DZ" in wx:
        rain = 2.5 if "+RA" in wx else 1.0 if "-RA" in wx or "DZ" in wx else 1.8
    if "SH" in wx:
        rain += 0.4
    h["rain"] = rain
    vis = o.get("vis")
    ceil = o.get("ceiling")
    # low ceiling on its own: 3,000 ft is the top of the scale, below 200 ft is the worst
    if ceil is None:
        h["ceiling"] = 0.0
    elif ceil >= 3000:
        h["ceiling"] = 0.0
    else:
        h["ceiling"] = round(min(5.0, (3000 - ceil) / 600.0), 2)
    # low visibility on its own: under 5 SM starts to count, 1/4 SM is the worst
    if vis is None:
        h["vis"] = 0.0
    elif vis >= 5:
        h["vis"] = 0.0
    else:
        h["vis"] = round(min(5.0, (5.0 - vis) / 0.95), 2)
    fog = (3.0 if "FG" in wx else 0.0) + (1.0 if "FZFG" in wx else 0.0)
    if fog and vis is not None:
        fog += 2.0 if vis < 0.5 else 1.0 if vis < 1 else 0.0
    h["fog"] = fog
    dust = 0.0
    for code, v in (("VA", 5.0), ("DS", 4.0), ("SS", 4.0), ("PO", 3.0), ("DU", 2.5), ("SA", 2.5), ("FU", 2.0),
                    ("HZ", 1.0)):
        if code in wx:
            dust = max(dust, v)
    if dust and vis is not None and vis < 3:
        dust += 1.0
    h["dust"] = dust
    return h


def score(o, kind="any"):
    h = hazards(o)
    if kind == "any":
        return h["ifr"] + h["wind"] * 1.1 + h["ts"] + h["snow"] + h["rain"] * 0.6 + h["fog"] * 0.5 + h["dust"] * 0.8
    return h.get(kind, 0.0)


def describe(o):
    """Short plain-English summary of an observation."""
    parts = [o.get("cat") or "?"]
    if o.get("wdir") is None and (o.get("wspd") or 0) > 0:
        w = f"wind variable {o['wspd']:.0f} kt"
    elif (o.get("wspd") or 0) > 0:
        w = f"wind {o['wdir']:03.0f}@{o['wspd']:.0f}" + (f"G{o['wgst']:.0f}" if o.get("wgst") else "")
    else:
        w = "calm"
    parts.append(w)
    if o.get("vis") is not None:
        parts.append(f"vis {o['vis']:g} SM")
    if o.get("ceiling") is not None:
        parts.append(f"ceiling {o['ceiling']:,.0f} ft")
    if o.get("wx"):
        parts.append(o["wx"])
    return ", ".join(parts)


# ==========================================================================
# Spatial index + matching METARs to X-Plane airports
# ==========================================================================
def _dist(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(a)))


class Grid:
    """Buckets of points on a 0.5-degree grid for quick 'what's near here' queries."""

    def __init__(self, items, cell=0.5):
        self.cell, self.b = cell, {}
        for it in items:
            self.b.setdefault((int(it["lat"] // cell), int(it["lon"] // cell)), []).append(it)

    def near(self, lat, lon, r_nm):
        dl = r_nm / 60 / self.cell + 1
        dlo = r_nm / (60 * max(0.2, math.cos(math.radians(lat)))) / self.cell + 1
        ci, cj = int(lat // self.cell), int(lon // self.cell)
        out = []
        for i in range(ci - int(dl), ci + int(dl) + 1):
            for j in range(cj - int(dlo), cj + int(dlo) + 1):
                for it in self.b.get((i, j), ()):
                    dd = _dist(lat, lon, it["lat"], it["lon"])
                    if dd <= r_nm:
                        out.append((dd, it))
        out.sort(key=lambda t: t[0])
        return out


def find_bad_weather(obs, gen, kind="any", home=None, max_nm=None, usable_only=True, min_score=1.0,
                     limit=150, match_nm=12):
    """
    Rank airports near bad weather.
    Returns [{'obs', 'score', 'apt', 'apt_dist' (nm from station), 'home_dist', 'alts'[(nm, apt)]}].
    """
    pool = gen.pool if usable_only else [a for a in gen.all if gen.region_ok(a)]
    grid = Grid(pool)
    res, used = [], set()
    for o in obs:
        s = score(o, kind)
        if s < min_score:
            continue
        if home is not None:
            hd = _dist(home["lat"], home["lon"], o["lat"], o["lon"])
            if max_nm and hd > max_nm + match_nm:
                continue
        near = grid.near(o["lat"], o["lon"], match_nm)
        if not near:
            continue
        own = next(((dd, a) for dd, a in near if a["id"] == o["id"]), None)
        dd, apt = own or near[0]
        if apt["id"] in used:
            continue
        hd = _dist(home["lat"], home["lon"], apt["lat"], apt["lon"]) if home else None
        if home is not None and max_nm and hd > max_nm:
            continue
        used.add(apt["id"])
        res.append({"obs": o, "score": round(s, 1), "apt": apt, "apt_dist": dd, "home_dist": hd,
                    "alts": [(d2, a2) for d2, a2 in near if a2 is not apt][:4]})
    res.sort(key=lambda r: (-r["score"], r["home_dist"] or 0))
    return res[:limit]


def nearest_obs(obs_grid, lat, lon, r=40):
    n = obs_grid.near(lat, lon, r)
    return n[0][1] if n else None


# ==========================================================================
# METAR -> the app's weather object
# ==========================================================================
def to_wx(o, core):
    """Build a core.Wx that reproduces this METAR."""
    layers = []
    raw = o.get("raw", "")
    ts = "TS" in (o.get("wx") or "") or o.get("cb")
    for i, (c, base) in enumerate(o["clouds"][:3]):
        if base is None:
            continue
        cov = COVER.get(c, 0.4)
        if ts and i == 0 or re.search(rf"\b{c}{int(base) // 100:03d}CB\b", raw):
            typ, th = "cumulonimbus", 25000
        elif base >= 18000:
            typ, th = "cirrus", 1500
        elif cov >= 0.75 and base < 8000:
            typ, th = "stratus", 2500
        else:
            typ, th = "cumulus", 3000
        layers.append((typ, cov, int(base), th))
    wx = (o.get("wx") or "").upper()
    precip = 0.0
    if any(k in wx for k in ("RA", "SN", "DZ", "PL", "GR", "GS")):
        precip = 0.8 if "+" in wx else 0.25 if "-" in wx or "DZ" in wx else 0.5
    vis = o.get("vis")
    if vis is None:
        vis = 10
    clouds_txt = " ".join(f"{c}{int(b):,}" for c, b in o["clouds"] if b is not None) or "no clouds reported"
    text = f"Live METAR {o['id']} ({o.get('cat') or '?'}): {clouds_txt}" + (f", {o['wx']}" if o.get("wx") else "")
    w = core.Wx("clear", o.get("wdir") or 0, o.get("wspd") or 0, max(0, (o.get("wgst") or 0) - (o.get("wspd") or 0)),
                o.get("temp") if o.get("temp") is not None else 15,
                round(o.get("altim") or 29.92, 2), min(vis, 30),
                layers=layers, sky_text=text, precip=precip)
    return w


# ==========================================================================
# Forecasts (TAF)
# ==========================================================================
TAF_URL = "https://aviationweather.gov/api/data/taf"


def fetch_taf(icao, timeout=20):
    """Raw TAF text for one airport, or None."""
    q = urllib.parse.urlencode({"ids": icao, "format": "json"})
    req = urllib.request.Request(f"{TAF_URL}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            js = json.loads(r.read())
    except Exception:
        return None
    if isinstance(js, dict):
        js = js.get("data") or []
    for t in js:
        raw = t.get("rawTAF") or t.get("rawOb") or t.get("raw_text")
        if raw:
            return raw.strip()
    return None


def taf_lines(raw):
    """Split a raw TAF into readable lines."""
    if not raw:
        return []
    raw = " ".join(raw.split())
    out, cur = [], ""
    for tok in raw.split(" "):
        if tok in ("FM", "TEMPO", "BECMG", "PROB30", "PROB40") or tok.startswith("FM") and tok[2:].isdigit():
            if cur:
                out.append(cur.strip())
            cur = tok + " "
        else:
            cur += tok + " "
    if cur:
        out.append(cur.strip())
    return out
