"""
xp_terrain.py - terrain awareness for a route.

Two sources, both optional:
  * airports   - the highest airport elevation near the route (always available,
                 but only as good as the airports around; it under-reads peaks)
  * online DEM - opentopodata.org (free, public, ~1 request/second, 1000/day).
                 Off unless you switch it on; results are cached on disk.

Gives: the highest ground near each leg, a suggested minimum safe altitude,
a terrain profile for drawing, and mountain-wave / high-terrain warnings.
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEM_URL = "https://api.opentopodata.org/v1/"
DATASETS = ["srtm90m", "aster30m", "etopo1"]
UA = "XPlaneFlightIdeas/3.5 (personal flight-sim helper)"
M_FT = 3.28084


def _interp(a, b, f):
    return (a["lat"] + (b["lat"] - a["lat"]) * f, a["lon"] + (b["lon"] - a["lon"]) * f)


def sample_points(stops, per_leg=12):
    """Points along the route: [(lat, lon, nm_from_start)]"""
    from xp_flight_ideas import d as dist
    out, run = [], 0.0
    for a, b in zip(stops, stops[1:]):
        L = dist(a, b)
        n = max(2, min(40, int(per_leg * max(1, L / 60))))
        for i in range(n + 1):
            lat, lon = _interp(a, b, i / n)
            out.append((lat, lon, run + L * i / n))
        run += L
    if not out:
        out = [(stops[0]["lat"], stops[0]["lon"], 0.0)]
    return out


class Terrain:
    def __init__(self, cache_dir: Path, airports=None, online=False):
        self.file = Path(cache_dir) / "terrain.json"
        self.online = online
        self.cache = {}
        try:
            self.cache = json.loads(self.file.read_text())
        except Exception:
            pass
        self.grid = {}
        self.cell = 0.25
        for a in airports or ():
            k = f"{int(a['lat'] // self.cell)},{int(a['lon'] // self.cell)}"
            self.grid[k] = max(self.grid.get(k, -1400), a["elev"])
        self._last_call = 0.0

    # ---- airport-based estimate -------------------------------------------
    def near_airport_high(self, lat, lon, cells=2):
        ci, cj = int(lat // self.cell), int(lon // self.cell)
        best = -1400
        for i in range(ci - cells, ci + cells + 1):
            for j in range(cj - cells, cj + cells + 1):
                best = max(best, self.grid.get(f"{i},{j}", -1400))
        return best

    # ---- online DEM ---------------------------------------------------------
    def _dem(self, pts):
        """Elevation (ft) for up to 100 (lat, lon) points, cached."""
        out, missing = {}, []
        for lat, lon in pts:
            k = f"{lat:.3f},{lon:.3f}"
            if k in self.cache:
                out[k] = self.cache[k]
            else:
                missing.append((k, lat, lon))
        if missing and self.online:
            for chunk in [missing[i:i + 90] for i in range(0, len(missing), 90)]:
                locs = "|".join(f"{lat:.4f},{lon:.4f}" for _, lat, lon in chunk)
                wait = 1.1 - (time.time() - self._last_call)
                if wait > 0:
                    time.sleep(wait)
                for ds in DATASETS:
                    try:
                        url = DEM_URL + ds + "?" + urllib.parse.urlencode({"locations": locs})
                        req = urllib.request.Request(url, headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=25) as r:
                            js = json.loads(r.read())
                        self._last_call = time.time()
                        res = js.get("results") or []
                        if len(res) != len(chunk):
                            continue
                        for (k, _, _), item in zip(chunk, res):
                            e = item.get("elevation")
                            val = round(e * M_FT) if e is not None else None
                            self.cache[k] = val
                            out[k] = val
                        break
                    except Exception:
                        continue
            try:
                self.file.write_text(json.dumps(self.cache))
            except OSError:
                pass
        return out

    # ---- route analysis ------------------------------------------------------
    def profile(self, stops, per_leg=12):
        """[(nm_from_start, ground_ft, source)] along the route."""
        pts = sample_points(stops, per_leg)
        dem = self._dem([(la, lo) for la, lo, _ in pts]) if self.online else {}
        prof = []
        for la, lo, nm in pts:
            k = f"{la:.3f},{lo:.3f}"
            v = dem.get(k)
            if v is None:
                prof.append((nm, self.near_airport_high(la, lo), "airports"))
            else:
                prof.append((nm, v, "dem"))
        return prof

    def summary(self, stops, cruise_ft, wind=None, per_leg=12):
        prof = self.profile(stops, per_leg)
        hi = max(p[1] for p in prof)
        src = "terrain data" if any(p[2] == "dem" for p in prof) else "nearby airport elevations"
        msa = int(math.ceil((hi + (2000 if hi > 5000 else 1000)) / 500.0) * 500)
        warn = []
        if cruise_ft < msa:
            warn.append(f"Highest ground found on the route is about {hi:,} ft ({src}). A safe cruise would be "
                        f"{msa:,} ft or above - the planned {cruise_ft:,} ft is lower.")
        elif hi > 3000:
            warn.append(f"Highest ground on the route is about {hi:,} ft ({src}); planned cruise {cruise_ft:,} ft.")
        if src.startswith("nearby"):
            warn.append("That figure comes from airport elevations only, so real peaks will be higher - "
                        "switch on the online terrain lookup, or check a chart.")
        if wind and wind[1] >= 20 and hi > 4000:
            warn.append(f"Wind {wind[0]:03.0f}@{wind[1]:.0f} over high ground: expect mountain wave, rotor and "
                        f"strong up/downdrafts. Cross ridges at 45 degrees with an escape turn planned, and add "
                        f"50% more terrain clearance.")
        return {"profile": prof, "max_ft": hi, "msa_ft": msa, "source": src, "warnings": warn}
