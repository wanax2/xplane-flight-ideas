"""
xp_score.py - watch a flight in X-Plane, grade the landings, and keep a logbook.

Uses the same local Web API as xp_link (X-Plane 12.1.1+ for datarefs).
Polls slowly in the cruise and faster near the ground so touchdowns are caught.
"""
from __future__ import annotations

import csv
import json
import math
import threading
import time
from pathlib import Path

M_FT = 3.28084
MS_KT = 1.94384

REFS = {
    "lat": "sim/flightmodel/position/latitude",
    "lon": "sim/flightmodel/position/longitude",
    "agl": "sim/flightmodel/position/y_agl",
    "gs": "sim/flightmodel/position/groundspeed",
    "vs": "sim/flightmodel/position/vh_ind_fpm",
    "ias": "sim/flightmodel/position/indicated_airspeed",
    "roll": "sim/flightmodel/position/phi",
    "hdg": "sim/flightmodel/position/psi",
    "gnd": "sim/flightmodel/failures/onground_any",
    "g": "sim/flightmodel/forces/g_nrml",
}
FAST = ("lat", "lon", "agl", "vs", "gs", "gnd", "ias")


def _dist_nm(a1, o1, a2, o2):
    p1, p2 = math.radians(a1), math.radians(a2)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(o2 - o1) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(x)))


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def grade_landing(fpm, spot_ft, offset_ft):
    rate = _clamp(100 - max(0.0, abs(fpm) - 120) / 3.5)
    spot = _clamp(100 - abs((spot_ft if spot_ft is not None else 1000) - 1000) / 12)
    centre = _clamp(100 - abs(offset_ft or 0) / 0.6)
    return round(0.45 * rate + 0.35 * spot + 0.20 * centre), round(rate), round(spot), round(centre)


def landing_words(fpm):
    f = abs(fpm)
    return ("a greaser" if f < 80 else "smooth" if f < 150 else "firm" if f < 300 else
            "hard - check for damage" if f < 600 else "very hard")


class Logbook:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries = []
        try:
            self.entries = json.loads(self.path.read_text())
        except Exception:
            pass

    def save(self):
        try:
            self.path.write_text(json.dumps(self.entries, indent=1))
        except OSError:
            pass

    def add(self, entry):
        entry.setdefault("time", time.time())
        entry.setdefault("favourite", False)
        self.entries.insert(0, entry)
        self.save()
        return entry

    def remove(self, entry):
        if entry in self.entries:
            self.entries.remove(entry)
            self.save()

    def stats(self):
        n = len(self.entries)
        hours = sum(e.get("minutes", 0) for e in self.entries) / 60
        nm = sum(e.get("distance_nm", 0) for e in self.entries)
        lands = [l for e in self.entries for l in e.get("landings", [])]
        scored = [e["score"] for e in self.entries if e.get("score")]
        apts = {a for e in self.entries for a in e.get("route", [])}
        best = min((abs(l["fpm"]) for l in lands), default=None)
        return {"flights": n, "hours": hours, "nm": nm, "landings": len(lands),
                "airports": len(apts), "avg_score": sum(scored) / len(scored) if scored else 0,
                "best_fpm": best, "aircraft": len({e.get("aircraft", "") for e in self.entries})}

    def export_csv(self, path):
        cols = ["date", "title", "aircraft", "route", "distance_nm", "minutes", "landings", "score", "favourite"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for e in self.entries:
                w.writerow([time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("time", 0))), e.get("title", ""),
                            e.get("aircraft", ""), "-".join(e.get("route", [])), round(e.get("distance_nm", 0)),
                            round(e.get("minutes", 0)), len(e.get("landings", [])), e.get("score", ""),
                            "yes" if e.get("favourite") else ""])
        return path


class FlightGrader(threading.Thread):
    """Follows the flight, records landings, and writes a logbook entry at the end."""

    def __init__(self, api, idea, aircraft_name, airports, logbook: Logbook, on_status=None, on_event=None,
                 on_done=None, start_delay=6.0, stop_after_s=45, on_sample=None, xplane_root=None,
                 screenshots=True):
        super().__init__(daemon=True)
        self.api, self.idea, self.acname = api, idea, aircraft_name
        self.airports = [a for a in airports if a] if airports else []
        self.log, self.on_status = logbook, on_status or (lambda s: None)
        self.on_event = on_event or (lambda s: None)
        self.on_done = on_done or (lambda e: None)
        self._halt = threading.Event()
        self.landings, self.track = [], []
        self.t0 = None
        self.dist_nm = 0.0
        self.max_alt = 0.0
        self.max_bank = 0.0
        self.max_g = 1.0
        self.started = False
        self.entry = None
        self._save = True
        self.start_delay, self.stop_after_s = start_delay, stop_after_s
        self.on_sample = on_sample or (lambda d: None)
        self.xplane_root = Path(xplane_root) if xplane_root else None
        self.screenshots = screenshots
        self.last = {}

    def stop(self, save=True):
        self._save = save
        self._halt.set()

    # ---- runway geometry ---------------------------------------------------
    def _touchdown_stats(self, lat, lon, hdg):
        best = None
        for a in self.airports:
            if abs(a["lat"] - lat) > 0.12 or abs(a["lon"] - lon) > 0.2:
                continue
            for r in a["rwys"]:
                c = r.get("c")
                if not c or len(c) != 4:
                    continue
                for (la1, lo1, la2, lo2), end in (((c[0], c[1], c[2], c[3]), r["e"][0]),
                                                  ((c[2], c[3], c[0], c[1]), r["e"][1])):
                    brg = math.degrees(math.atan2(math.radians(lo2 - lo1) * math.cos(math.radians(la1)),
                                                  math.radians(la2 - la1))) % 360
                    if hdg is not None and abs((brg - hdg + 180) % 360 - 180) > 50:
                        continue
                    # distance from the threshold, along and across the runway
                    dn = (lat - la1) * 60 * 6076.1
                    de = (lon - lo1) * 60 * 6076.1 * math.cos(math.radians(la1))
                    b = math.radians(brg)
                    along = dn * math.cos(b) + de * math.sin(b)
                    across = -dn * math.sin(b) + de * math.cos(b)
                    if -500 < along < r["len"] + 500 and abs(across) < 350:
                        sc = abs(across) + abs(along - 1000) * 0.1
                        if best is None or sc < best[0]:
                            best = (sc, a, end, along, across, r)
        if not best:
            return None
        _, a, end, along, across, r = best
        return {"airport": a["id"], "name": a["name"], "runway": end, "spot_ft": round(along),
                "offset_ft": round(across), "rwy_len": r["len"]}

    # ---- main loop -------------------------------------------------------------
    def run(self):
        api = self.api
        prev = None
        airborne = False
        last_air = None
        vs_hist = []
        errors = 0
        stopped_since = None
        self._halt.wait(self.start_delay)
        while not self._halt.is_set():
            try:
                fast = {k: float(api.get(REFS[k])) for k in FAST}
                errors = 0
            except Exception as e:
                errors += 1
                if errors > 20:
                    self.on_status(f"Scoring stopped: {e}")
                    break
                self._halt.wait(2)
                continue
            lat, lon = fast["lat"], fast["lon"]
            agl_ft, gs_kt = fast["agl"] * M_FT, fast["gs"] * MS_KT
            on_ground = fast["gnd"] > 0.5
            now = time.time()
            if self.t0 is None:
                self.t0 = now
            vs_hist.append(fast["vs"])
            vs_hist = vs_hist[-12:]
            if prev:
                self.dist_nm += _dist_nm(prev[0], prev[1], lat, lon)
            prev = (lat, lon)
            self.max_alt = max(self.max_alt, agl_ft)
            self.track.append((round(lat, 4), round(lon, 4)))
            if not self.started and (not on_ground or gs_kt > 25):
                self.started = True
                self.on_event("Flight started - scoring.")
            if not on_ground:
                airborne = True
                last_air = fast
                stopped_since = None
            elif airborne:
                airborne = False
                try:
                    hdg = float(api.get(REFS["hdg"]))
                    roll = abs(float(api.get(REFS["roll"])))
                except Exception:
                    hdg, roll = None, 0
                fpm = min(vs_hist[-4:]) if vs_hist else 0
                geo = self._touchdown_stats(lat, lon, hdg) or {}
                sc, r1, r2, r3 = grade_landing(fpm, geo.get("spot_ft"), geo.get("offset_ft"))
                land = {"fpm": round(fpm), "ias": round((last_air or fast)["ias"]), "bank": round(roll, 1), "score": sc,
                        "rate_score": r1, "spot_score": r2, "centre_score": r3, "time": now, **geo}
                shot = self._screenshot() if self.screenshots else None
                if shot:
                    land["screenshot"] = str(shot)
                self.landings.append(land)
                where = f" at {geo['airport']} rwy {geo['runway']}" if geo else ""
                spot = f", {geo['spot_ft']:,} ft past the threshold" if geo.get("spot_ft") is not None else ""
                self.on_event(f"Landing{where}: {abs(fpm):.0f} fpm ({landing_words(fpm)}){spot} - score {sc}/100")
            if on_ground and gs_kt < 2:
                stopped_since = stopped_since or now
            elif on_ground:
                stopped_since = None
            # slow/fast polling
            near = agl_ft < 700 or not self.started
            if not near:
                try:
                    self.max_bank = max(self.max_bank, abs(float(api.get(REFS["roll"]))))
                    self.max_g = max(self.max_g, float(api.get(REFS["g"])))
                except Exception:
                    pass
            self.last = {"lat": lat, "lon": lon, "agl": agl_ft, "gs": gs_kt, "vs": fast["vs"],
                         "ias": fast["ias"], "on_ground": on_ground, "t": now,
                         "dist_nm": self.dist_nm, "landings": len(self.landings)}
            self.on_sample(self.last)
            mins = (now - self.t0) / 60
            self.on_status(f"Scoring: {self.dist_nm:.0f} nm, {mins:.0f} min, {len(self.landings)} landing(s)"
                           + (f", last {abs(self.landings[-1]['fpm']):.0f} fpm" if self.landings else ""))
            # finished? on the ground, stopped for a while, after at least one landing
            if self.landings and stopped_since and now - stopped_since > self.stop_after_s:
                self.on_event("Engine-off / stopped - saving the flight.")
                break
            self._halt.wait(0.2 if near else 1.5)
        if self._save and self.started:
            try:
                self.finish()
            except Exception as e:
                self.on_status(f"Couldn't save the flight: {e}")

    def _screenshot(self):
        """Ask X-Plane for a screenshot and return the file it wrote (best effort)."""
        if not self.xplane_root:
            return None
        folder = self.xplane_root / "Output" / "screenshots"
        before = set(folder.glob("*.png")) | set(folder.glob("*.jpg")) if folder.is_dir() else set()
        try:
            self.api.command("sim/operation/screenshot")
        except Exception:
            return None
        for _ in range(12):
            time.sleep(0.25)
            if not folder.is_dir():
                continue
            new = (set(folder.glob("*.png")) | set(folder.glob("*.jpg"))) - before
            if new:
                return max(new, key=lambda p: p.stat().st_mtime)
        return None

    def finish(self):
        mins = (time.time() - (self.t0 or time.time())) / 60
        lands = self.landings
        avg = sum(l["score"] for l in lands) / len(lands) if lands else 0
        smooth = _clamp(100 - max(0.0, self.max_bank - 35) * 2 - max(0.0, self.max_g - 1.6) * 30)
        planned = [a["id"] for a in self.idea.stops] if self.idea else []
        arrived = bool(lands) and planned and lands[-1].get("airport") == planned[-1]
        score = round(0.7 * avg + 0.2 * smooth + (10 if arrived else 0)) if lands else 0
        self.entry = {
            "title": self.idea.title if self.idea else "Free flight",
            "kind": getattr(self.idea, "kind", ""), "aircraft": self.acname,
            "route": planned, "flown_to": [l.get("airport") for l in lands if l.get("airport")],
            "distance_nm": round(self.dist_nm, 1), "minutes": round(mins, 1), "landings": lands,
            "max_bank": round(self.max_bank), "max_g": round(self.max_g, 2), "arrived": arrived,
            "score": score, "track": self.track[::max(1, len(self.track) // 300)],
        }
        self.log.add(self.entry)
        self.on_done(self.entry)


def report(entry) -> str:
    """A readable grade card."""
    L = [f"{entry['title']}", f"{entry.get('aircraft', '')}",
         f"Route planned: {' - '.join(entry.get('route', [])) or '?'}",
         f"Flown: {entry['distance_nm']:.0f} nm in {entry['minutes']:.0f} min"
         + (" (arrived as planned)" if entry.get("arrived") else ""), ""]
    for i, l in enumerate(entry.get("landings", []), 1):
        where = f"{l.get('airport', '?')} rwy {l.get('runway', '?')}"
        L.append(f"Landing {i}: {where} - {abs(l['fpm']):.0f} fpm ({landing_words(l['fpm'])}), "
                 f"{l.get('ias', 0):.0f} kt")
        if l.get("spot_ft") is not None:
            L.append(f"    {l['spot_ft']:,} ft past the threshold, {abs(l.get('offset_ft', 0)):,} ft off the "
                     f"centreline (runway {l.get('rwy_len', 0):,} ft)")
        L.append(f"    rate {l['rate_score']}/100, spot {l['spot_score']}/100, centreline {l['centre_score']}/100"
                 f"  ->  {l['score']}/100")
    L += ["", f"Smoothness: max bank {entry.get('max_bank', 0)} deg, max {entry.get('max_g', 1):.2f} G",
          f"FLIGHT SCORE: {entry.get('score', 0)}/100"]
    return "\n".join(L)
