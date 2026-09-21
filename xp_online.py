"""
xp_online.py - two public, free online databases.

  * OurAirports  - the open airport database (davidmegginson.github.io/ourairports-data).
                   Adds country and region names, city, airport type, IATA code,
                   Wikipedia links and keywords to the airports X-Plane gave us.
  * Flight Plan Database (flightplandatabase.com) - tens of thousands of routes
                   shared by other pilots, searchable by airport, distance, tags
                   and popularity. Its search API is public; an account key just
                   raises the request limit.

Everything is cached on disk and every call fails quietly if you're offline.
"""
from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "XPlaneFlightIdeas/6.0 (personal flight-sim helper; python urllib)"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
FPDB = "https://api.flightplandatabase.com"

TYPE_NAMES = {"large_airport": "large airport", "medium_airport": "medium airport",
              "small_airport": "small airport", "heliport": "heliport",
              "seaplane_base": "seaplane base", "balloonport": "balloonport", "closed": "closed"}


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


# ==========================================================================
# OurAirports
# ==========================================================================
class OurAirports:
    def __init__(self, cache_dir: Path):
        self.file = Path(cache_dir) / "ourairports.json.gz"
        self.data, self.fetched = {}, 0.0
        try:
            with gzip.open(self.file, "rt", encoding="utf-8") as f:
                d = json.load(f)
            self.data, self.fetched = d["a"], d.get("t", 0)
        except Exception:
            pass

    def age_days(self):
        return (time.time() - self.fetched) / 86400 if self.fetched else None

    def download(self, log=print):
        log("Downloading the OurAirports database (about 10 MB)...")
        raw, _ = _get(OURAIRPORTS_URL, timeout=120)
        text = raw.decode("utf-8", "replace")
        out = {}
        for row in csv.DictReader(io.StringIO(text)):
            ident = (row.get("ident") or "").strip().upper()
            if not ident:
                continue
            out[ident] = {"t": row.get("type", ""), "n": row.get("name", ""),
                          "c": row.get("iso_country", ""), "r": (row.get("iso_region") or "").split("-")[-1],
                          "m": row.get("municipality", ""), "w": row.get("wikipedia_link", ""),
                          "i": row.get("iata_code", ""), "l": row.get("local_code", ""),
                          "s": row.get("scheduled_service", ""), "k": (row.get("keywords") or "")[:120],
                          "h": row.get("home_link", "")}
            local = (row.get("local_code") or "").strip().upper()
            if local and local not in out:
                out[local] = out[ident]
            gps = (row.get("gps_code") or "").strip().upper()
            if gps and gps not in out:
                out[gps] = out[ident]
        self.data, self.fetched = out, time.time()
        try:
            with gzip.open(self.file, "wt", encoding="utf-8") as f:
                json.dump({"t": self.fetched, "a": out}, f)
        except OSError:
            pass
        log(f"OurAirports: {len(out):,} entries.")
        return len(out)

    def enrich(self, airports, country_names=None):
        """Fill in city, region, country, type, Wikipedia link... on X-Plane's airports."""
        if not self.data:
            return 0
        n = 0
        for a in airports:
            e = self.data.get(a["id"].upper())
            if not e:
                for alias in a.get("alias", []):
                    e = self.data.get(str(alias).upper())
                    if e:
                        break
            if not e:
                continue
            n += 1
            a["oa_type"] = e["t"]
            a["wiki"] = e["w"]
            a["iata"] = e["i"]
            a["sched"] = e["s"] == "yes"
            a["keywords"] = e["k"]
            if not a.get("city"):
                a["city"] = e["m"]
            if not a.get("iso"):
                a["iso"] = e["c"]
            if not a.get("state") and e["r"]:
                a["state"] = e["r"]
            if not a.get("country") and country_names:
                a["country"] = country_names.get(e["c"], "")
        return n


# ==========================================================================
# Flight Plan Database
# ==========================================================================
class FlightPlanDB:
    def __init__(self, api_key=""):
        self.key = (api_key or "").strip()

    def _headers(self):
        h = {"Accept": "application/json", "X-Units": "AVIATION"}
        if self.key:
            h["Authorization"] = "Basic " + base64.b64encode((self.key + ":").encode()).decode()
        return h

    def search(self, from_icao=None, to_icao=None, tags=None, dist_min=None, dist_max=None,
               sort="popularity", limit=40):
        q = {"sort": sort, "limit": max(1, min(100, int(limit)))}
        if from_icao:
            q["fromICAO"] = from_icao.upper()
        if to_icao:
            q["toICAO"] = to_icao.upper()
        if tags:
            q["tags"] = tags
        if dist_min:
            q["distanceMin"] = dist_min
        if dist_max:
            q["distanceMax"] = dist_max
        raw, _ = _get(f"{FPDB}/search/plans?" + urllib.parse.urlencode(q), self._headers())
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get("data", [])

    def plan(self, plan_id):
        raw, _ = _get(f"{FPDB}/plan/{int(plan_id)}", self._headers())
        return json.loads(raw)

    def fms(self, plan_id, xplane11=True):
        """The plan as an X-Plane .fms file (text)."""
        acc = "application/vnd.fpd.export.v1.xplane11" if xplane11 else "application/vnd.fpd.export.v1.fms"
        raw, _ = _get(f"{FPDB}/plan/{int(plan_id)}", {**self._headers(), "Accept": acc})
        return raw.decode("utf-8", "replace")


# ==========================================================================
# OpenSky Network - what is actually flying right now
# ==========================================================================
OPENSKY = "https://opensky-network.org/api/states/all"


class OpenSky:
    """Aircraft airborne this minute. The anonymous API is free and rate-limited."""

    def __init__(self, cache_dir=None):
        self.states, self.fetched = [], 0.0

    def fetch(self, lat=None, lon=None, radius_nm=400, timeout=30):
        q = {}
        if lat is not None and lon is not None:
            dlat = radius_nm / 60.0
            dlon = radius_nm / (60.0 * max(0.2, math.cos(math.radians(lat))))
            q = {"lamin": round(lat - dlat, 3), "lamax": round(lat + dlat, 3),
                 "lomin": round(lon - dlon, 3), "lomax": round(lon + dlon, 3)}
        url = OPENSKY + ("?" + urllib.parse.urlencode(q) if q else "")
        raw, _ = _get(url, timeout=timeout)
        data = json.loads(raw)
        out = []
        for s in data.get("states") or []:
            # icao24, callsign, country, time_pos, last_contact, lon, lat, baro_alt, on_ground,
            # velocity, heading, vert_rate, sensors, geo_alt, squawk, spi, category
            try:
                if s[8] or s[5] is None or s[6] is None:
                    continue           # on the ground, or no position
                alt_ft = (s[13] or s[7] or 0) * 3.28084
                out.append({"icao24": s[0], "callsign": (s[1] or "").strip(), "country": s[2],
                            "lon": float(s[5]), "lat": float(s[6]), "alt_ft": alt_ft,
                            "kt": (s[9] or 0) * 1.94384, "hdg": s[10] or 0,
                            "climb": (s[11] or 0) * 196.85})
            except (IndexError, TypeError, ValueError):
                continue
        self.states, self.fetched = out, time.time()
        return out

    @staticmethod
    def light_traffic(states, max_kt=250, max_ft=18000):
        """The ones that fly like a light aircraft - the kind you can actually copy."""
        return [s for s in states if s["kt"] <= max_kt and s["alt_ft"] <= max_ft and s["kt"] > 40]


def real_flight_idea(state, core, gen, ac, wx=None):
    """Turn 'this aeroplane is here, at this height, going this way' into a flight."""
    here = {"lat": state["lat"], "lon": state["lon"], "id": "?", "name": "", "elev": 0}
    pool = [a for a in gen.pool if gen.usable(a)]
    if not pool:
        raise ValueError("No airports your aircraft can use near there.")
    start = min(pool, key=lambda a: core.d(here, a))
    ahead = {"lat": state["lat"] + math.cos(math.radians(state["hdg"])) * 1.2,
             "lon": state["lon"] + math.sin(math.radians(state["hdg"])) * 1.2, "id": "?", "name": ""}
    cands = [a for a in pool if a["id"] != start["id"] and 15 <= core.d(start, a) <= ac["range"] * 0.7]
    if not cands:
        raise ValueError("Nothing within range of there in your scenery.")
    dest = min(cands, key=lambda a: core.d(ahead, a))
    m = time.localtime()
    idea = core.Idea("shared", f"Real traffic: {state['callsign'] or state['icao24']}",
                     [start, dest],
                     f"Somebody is flying this right now. {state['callsign'] or 'An aircraft'} is over "
                     f"{core.d(here, start):.0f} nm from {start['id']}, at {state['alt_ft']:,.0f} ft doing "
                     f"{state['kt']:.0f} kt on a heading of {state['hdg']:03.0f}. Take off from "
                     f"{start['id']}, join their track and fly it to {dest['id']} at about their height.",
                     month=m.tm_mon - 1, tod="midday", hour=m.tm_hour + m.tm_min / 60,
                     wx=wx or gen.mkwx(dest, m.tm_mon - 1), live=True,
                     notes=[f"Squawk and callsign from OpenSky Network ({state['icao24']}).",
                            "Positions are a minute or two old, and the aircraft may land or turn - "
                            "this is a starting point, not a shadow.",
                            "Use real-world weather on the 'Fly it' tab to match what they're in."])
    return idea


def describe_plan(p):
    d = p.get("distance")
    tags = ", ".join(p.get("tags") or [])
    return (f"{p.get('fromICAO') or '?'} to {p.get('toICAO') or '?'}  "
            f"{('%.0f nm' % d) if isinstance(d, (int, float)) else ''}  "
            f"{p.get('name') or ''}  {('[' + tags + ']') if tags else ''}").strip()


def plan_to_idea(plan, core, gen, ac, title_prefix="Shared route"):
    """Turn a Flight Plan Database plan into one of our ideas (airports only)."""
    nodes = (plan.get("route") or {}).get("nodes") or []
    stops, seen = [], set()
    for n in nodes:
        ident = (n.get("ident") or "").upper()
        typ = (n.get("type") or "").upper()
        a = gen.find(ident) if ident else None
        if a is None and ident and typ in ("VOR", "NDB"):
            a = next((x for x in getattr(core, "NAVAIDS", []) if x["id"] == ident), None)
        if a is not None and a["id"] not in seen:
            stops.append(a)
            seen.add(a["id"])
    for icao in (plan.get("fromICAO"), plan.get("toICAO")):
        a = gen.find(icao) if icao else None
        if a is None:
            continue
        if not stops or (icao == plan.get("fromICAO") and stops[0]["id"] != a["id"]):
            stops.insert(0, a)
        elif icao == plan.get("toICAO") and stops[-1]["id"] != a["id"]:
            stops.append(a)
    # drop stops the aircraft can't use, except the ends
    keep = [stops[0]] + [s for s in stops[1:-1] if gen.usable(s)] + ([stops[-1]] if len(stops) > 1 else []) \
        if stops else []
    if len(keep) < 2:
        raise ValueError("None of that plan's airports are in your scenery.")
    if len(keep) > 8:
        step = len(keep) // 7 + 1
        keep = [keep[0]] + keep[1:-1:step] + [keep[-1]]
    m = gen.month()
    wx = gen.mkwx(keep[-1], m)
    who = (plan.get("user") or {}).get("username") or "someone"
    name = plan.get("name") or f"{keep[0]['id']} to {keep[-1]['id']}"
    notes = [f"From Flight Plan Database, shared by {who}"
             + (f" - {plan.get('likes', 0)} likes, {plan.get('downloads', 0)} downloads" if plan.get("downloads")
                else "") + ".",
             f"https://flightplandatabase.com/plan/{plan.get('id')}"]
    if plan.get("tags"):
        notes.append("Tags: " + ", ".join(plan["tags"]))
    if plan.get("notes"):
        notes.append(str(plan["notes"])[:400])
    idea = core.Idea("shared", f"{title_prefix}: {name}", keep,
                     "A route other pilots have flown and shared. Fly it your way - the notes below are theirs.",
                     month=m, tod=gen.tod(), wx=wx, notes=notes)
    return idea
