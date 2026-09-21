"""
xp_export.py - nav logs, printable briefings, GPX/KML, SimBrief links, and saved trips.
"""
from __future__ import annotations

import html
import json
import math
import time
import urllib.parse
from pathlib import Path


# ==========================================================================
# Nav log
# ==========================================================================
def fuel_gph(ac):
    d = ac.get("acf") or {}
    if d.get("jet"):
        return ac["cruise"] / 2.2
    if d.get("turbine"):
        return ac["cruise"] / 3.2
    return max(4.0, ac["cruise"] / 12.0)


def wind_at(idea, core, ac):
    """(direction, speed) at the planned cruise altitude, from the weather's wind layers."""
    wx = idea.wx
    alt = core.cruise_alt(idea.stops, ac, idea.ifr)
    elev = idea.stops[0]["elev"]
    try:
        layers = wx.to_xplane(idea.stops[0]["lat"], idea.stops[0]["lon"], elev)["definition"]["wind"]
    except Exception:
        return wx.wind_dir, wx.wind_spd
    best = min(layers, key=lambda L: abs(L["altitude_in_feet_msl"] - alt))
    return best["direction_in_degrees_true"], best["speed_in_knots"]


def leg_rows(core, idea, ac):
    """[(from, to, dist, true course, wind corr heading, GS, ETE min, fuel gal)]"""
    wdir, wspd = wind_at(idea, core, ac)
    wx = type("W", (), {"wind_dir": wdir, "wind_spd": wspd})()
    tas = ac["cruise"]
    rows = []
    for a, b in zip(idea.stops, idea.stops[1:]):
        dist = core.d(a, b)
        tc = core.crs(a, b)
        if dist < 0.5:
            continue
        w = math.radians((wx.wind_dir - tc + 180) % 360)     # wind angle relative to course
        xw = wx.wind_spd * math.sin(w)
        hw = wx.wind_spd * math.cos(w)
        wca = math.degrees(math.asin(max(-0.9, min(0.9, xw / max(40.0, tas)))))
        gs = max(35.0, tas * math.cos(math.radians(wca)) + hw)
        ete = dist / gs * 60 + 5
        rows.append((a, b, dist, tc, (tc + wca) % 360, gs, ete, ete / 60 * fuel_gph(ac)))
    return rows


def nav_log(core, idea, ac, terrain=None):
    rows = leg_rows(core, idea, ac)
    alt = core.cruise_alt(idea.stops, ac, idea.ifr)
    wdir, wspd = wind_at(idea, core, ac)
    L = [f"NAV LOG - {idea.title}", f"{ac['name']}   |   {idea.when_text()}", f"Weather: {idea.wx.describe()}",
         idea.sun_text(),
         f"Planned cruise: {alt:,} ft   |   TAS {ac['cruise']} kt   |   ~{fuel_gph(ac):.1f} gal/hr",
         f"Wind used: surface {idea.wx.wind_dir:03.0f}@{idea.wx.wind_spd}, "
         f"at cruise {wdir:03.0f}@{wspd:.0f}", "",
         f"{'From':<7}{'To':<7}{'nm':>7}{'TC':>6}{'HDG':>6}{'GS':>6}{'min':>6}{'gal':>7}", "-" * 52]
    tot_d = tot_t = tot_f = 0.0
    for a, b, dist, tc, hdg, gs, ete, fuel in rows:
        L.append(f"{a['id']:<7}{b['id']:<7}{dist:>7.0f}{tc:>6.0f}{hdg:>6.0f}{gs:>6.0f}{ete:>6.0f}{fuel:>7.1f}")
        tot_d, tot_t, tot_f = tot_d + dist, tot_t + ete, tot_f + fuel
    L += ["-" * 52, f"{'TOTAL':<14}{tot_d:>7.0f}{'':>12}{tot_t:>12.0f}{tot_f:>7.1f}", "",
          f"Fuel with 45 min reserve: {tot_f + fuel_gph(ac) * 0.75:.1f} gal",
          "Headings are true (no magnetic variation applied) and assume the wind above."]
    if terrain:
        L += ["", f"Terrain: highest ground about {terrain['max_ft']:,} ft ({terrain['source']}), "
                  f"suggested minimum safe altitude {terrain['msa_ft']:,} ft"]
        L += ["  " + w for w in terrain["warnings"]]
    return "\n".join(L)


# ==========================================================================
# Printable briefing (HTML)
# ==========================================================================
def briefing_html(core, idea, ac, extra_text=""):
    e = html.escape
    rows = leg_rows(core, idea, ac)
    legs = "".join(
        f"<tr><td>{e(a['id'])}</td><td>{e(a['name'])}</td><td>{e(b['id'])}</td><td>{dist:.0f}</td>"
        f"<td>{tc:.0f}&deg;</td><td>{hdg:.0f}&deg;</td><td>{gs:.0f}</td><td>{ete:.0f}</td><td>{fuel:.1f}</td></tr>"
        for a, b, dist, tc, hdg, gs, ete, fuel in rows)
    stops = "".join(
        f"<tr><td>{e(a['id'])}</td><td>{e(a['name'])}</td><td>{a['elev']:,} ft</td>"
        f"<td>{e(core.rwy_list(a))}</td><td>{'tower' if a['tower'] else ''}"
        f"{' ILS ' + ','.join(a['ils']) if a.get('ils') else ''}</td></tr>" for a in idea.stops)
    notes = "".join(f"<li>{e(n)}</li>" for n in idea.notes)
    twist = f"<p class='twist'><b>Twist:</b> {e(idea.twist)}</p>" if idea.twist else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(idea.title)}</title>
<style>
 body{{font-family:Segoe UI,Helvetica,Arial,sans-serif;margin:28px;color:#222;max-width:900px}}
 h1{{font-size:20px;margin:0 0 2px}} h2{{font-size:14px;margin:18px 0 6px;color:#444}}
 .sub{{color:#666;margin-bottom:14px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{border:1px solid #ccd;padding:4px 6px;text-align:left}} th{{background:#eef2f6}}
 .mission{{background:#f6f8fa;border-left:4px solid #1f6fd1;padding:8px 12px;margin:10px 0}}
 .twist{{background:#fff4f4;border-left:4px solid #c33;padding:8px 12px}}
 ul{{margin:6px 0 0 18px;padding:0}} li{{margin:2px 0}}
 @media print{{body{{margin:10px}} h1{{font-size:18px}}}}
</style></head><body>
<h1>{e(idea.title)}</h1>
<div class="sub">{e(ac['name'])} &middot; {e(idea.when_text())} &middot; {e(idea.wx.describe())}</div>
<div class="sub">{e(idea.sun_text())}</div>
<div class="mission">{e(idea.mission)}</div>{twist}
<h2>Route</h2>
<table><tr><th>From</th><th></th><th>To</th><th>nm</th><th>TC</th><th>HDG</th><th>GS</th><th>min</th><th>gal</th></tr>
{legs}</table>
<h2>Airports</h2>
<table><tr><th>ID</th><th>Name</th><th>Elev</th><th>Runways</th><th></th></tr>{stops}</table>
<h2>Notes</h2><ul>{notes}</ul>
<p style="color:#666;font-size:12px">Suggested cruise {core.cruise_alt(idea.stops, ac, idea.ifr):,} ft &middot;
 fuel about {fuel_gph(ac):.1f} gal/hr &middot; headings are true.</p>
<pre style="font-size:12px;white-space:pre-wrap">{e(extra_text)}</pre>
</body></html>"""


# ==========================================================================
# GPX / KML / SimBrief
# ==========================================================================
def gpx(idea):
    pts = "".join(f'  <rtept lat="{a["lat"]:.6f}" lon="{a["lon"]:.6f}"><name>{html.escape(a["id"])}</name>'
                  f'<ele>{a["elev"] / 3.28084:.0f}</ele></rtept>\n' for a in idea.stops)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="X-Plane Flight Ideas" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f'<rte><name>{html.escape(idea.title)}</name>\n{pts}</rte>\n</gpx>\n')


def kml(idea):
    coords = " ".join(f'{a["lon"]:.6f},{a["lat"]:.6f},{a["elev"] / 3.28084:.0f}' for a in idea.stops)
    marks = "".join(f'<Placemark><name>{html.escape(a["id"])}</name><Point><coordinates>'
                    f'{a["lon"]:.6f},{a["lat"]:.6f},0</coordinates></Point></Placemark>' for a in idea.stops)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            f'<name>{html.escape(idea.title)}</name>{marks}'
            f'<Placemark><name>Route</name><LineString><tessellate>1</tessellate>'
            f'<coordinates>{coords}</coordinates></LineString></Placemark></Document></kml>\n')


def lnmpln(idea, ac):
    """Little Navmap flight plan (.lnmpln)."""
    def wp(a, kind="AIRPORT"):
        return (f'    <Waypoint>\n      <Name>{html.escape(a["name"])}</Name>\n'
                f'      <Ident>{html.escape(a["id"])}</Ident>\n      <Type>{kind}</Type>\n'
                f'      <Pos Lon="{a["lon"]:.6f}" Lat="{a["lat"]:.6f}" Alt="{a["elev"]}"/>\n    </Waypoint>\n')
    wps = "".join(wp(a) for a in idea.stops)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<LittleNavmap>\n  <Flightplan>\n    <Header>\n'
            f'      <FlightplanType>VFR</FlightplanType>\n      <CruisingAlt>0</CruisingAlt>\n'
            f'      <CreationDate>{time.strftime("%Y-%m-%dT%H:%M:%S")}</CreationDate>\n'
            f'      <ProgramName>X-Plane Flight Ideas</ProgramName>\n'
            f'      <ProgramVersion>3.5</ProgramVersion>\n'
            f'      <Documentation>{html.escape(idea.title)}</Documentation>\n    </Header>\n'
            f'    <SimData>XP12</SimData>\n    <AircraftPerformance><FilePath></FilePath>\n'
            f'      <Type>{html.escape((ac.get("acf") or {}).get("icao") or "")}</Type>\n'
            f'      <Name>{html.escape(ac["name"])}</Name>\n    </AircraftPerformance>\n'
            f'    <Waypoints>\n{wps}    </Waypoints>\n  </Flightplan>\n</LittleNavmap>\n')


# ==========================================================================
# Share codes - a whole idea squeezed into a bit of text
# ==========================================================================
def share_code(idea, ac_name=""):
    import base64
    import zlib
    d = {"v": 1, "t": idea.title, "k": idea.kind, "s": [a["id"] for a in idea.stops], "m": idea.month,
         "tod": idea.tod, "h": idea._hour, "mi": idea.mission, "n": idea.notes, "tw": idea.twist,
         "ac": ac_name, "ifr": idea.ifr, "ov": sorted(idea.overfly), "pay": idea.payload_kg,
         "wx": {"sky": idea.wx.sky, "d": idea.wx.wind_dir, "s": idea.wx.wind_spd, "g": idea.wx.gust,
                "t": idea.wx.temp, "a": idea.wx.altimeter, "v": idea.wx.vis,
                "L": idea.wx.layers if idea.wx.custom else None, "x": idea.wx.sky_text if idea.wx.custom else None,
                "p": idea.wx.precip if idea.wx.custom else None}}
    raw = zlib.compress(json.dumps(d, separators=(",", ":")).encode(), 9)
    return "XPFI1:" + base64.urlsafe_b64encode(raw).decode()


def from_share_code(code, core, gen):
    """Rebuild an idea from a share code (airports must exist in this scenery)."""
    import base64
    import zlib
    code = (code or "").strip()
    if not code.startswith("XPFI1:"):
        raise ValueError("That doesn't look like a flight share code.")
    d = json.loads(zlib.decompress(base64.urlsafe_b64decode(code[6:].encode())))
    stops = []
    for i in d["s"]:
        a = gen.find(i) or next((n for n in getattr(core, "NAVAIDS", []) if n["id"] == i), None)
        if not a:
            raise ValueError(f"{i} isn't in your scenery.")
        stops.append(a)
    w = d.get("wx") or {}
    if w.get("L"):
        wx = core.Wx(layers=[tuple(x) for x in w["L"]], sky_text=w.get("x") or "Shared weather",
                     precip=w.get("p") or 0, wind_dir=w.get("d", 0), wind_spd=w.get("s", 0), gust=w.get("g", 0),
                     temp=w.get("t", 15), altimeter=w.get("a", 29.92), vis=w.get("v", 10))
    else:
        wx = core.Wx(w.get("sky", "clear"), w.get("d", 0), w.get("s", 0), w.get("g", 0), w.get("t", 15),
                     w.get("a", 29.92), w.get("v"))
    gen.set_wind_text(wx, stops[-1])
    idea = core.Idea(d.get("k", "custom"), d.get("t", "Shared flight"), stops, d.get("mi", ""),
                     month=d.get("m", 5), tod=d.get("tod", "morning"), hour=d.get("h"), wx=wx,
                     notes=list(d.get("n") or []), ifr=d.get("ifr", False), overfly=d.get("ov") or [],
                     payload_kg=d.get("pay"))
    idea.twist = d.get("tw")
    return idea


def route_string(idea):
    return " ".join(a["id"] for a in idea.stops)


def simbrief_url(idea, ac):
    mid = [a["id"] for a in idea.stops[1:-1]]
    q = {"orig": idea.stops[0]["id"], "dest": idea.stops[-1]["id"], "route": " ".join(mid) or "DCT",
         "type": (ac.get("acf") or {}).get("icao") or "C172", "planformat": "lido", "units": "LBS"}
    return "https://dispatch.simbrief.com/options/custom?" + urllib.parse.urlencode(q)


# ==========================================================================
# Trips (multi-leg, flown over several sessions)
# ==========================================================================
class TripBook:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.trips = []
        try:
            self.trips = json.loads(self.path.read_text())
        except Exception:
            pass

    def save(self):
        try:
            self.path.write_text(json.dumps(self.trips, indent=1))
        except OSError:
            pass

    def add_from_idea(self, idea, ac_name, name=None):
        legs = [{"from": a["id"], "to": b["id"], "nm": None, "done": False, "score": None}
                for a, b in zip(idea.stops, idea.stops[1:]) if a["id"] != b["id"]]
        trip = {"name": name or idea.title, "created": time.time(), "aircraft": ac_name,
                "mission": idea.mission, "kind": idea.kind, "legs": legs,
                "ids": [a["id"] for a in idea.stops]}
        self.trips.insert(0, trip)
        self.save()
        return trip

    def next_leg(self, trip):
        return next((l for l in trip["legs"] if not l["done"]), None)

    def mark(self, trip, leg, done=True, score=None):
        leg["done"] = done
        if score is not None:
            leg["score"] = score
        self.save()

    def progress(self, trip):
        done = sum(1 for l in trip["legs"] if l["done"])
        return done, len(trip["legs"])

    def remove(self, trip):
        if trip in self.trips:
            self.trips.remove(trip)
            self.save()
