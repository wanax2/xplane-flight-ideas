"""
xp_world.py - every airport on earth, without X-Plane.

The whole app is normally built out of your own scenery: it reads apt.dat, so it
only ever offers you places your install actually has, add-on airports included.
That is the right way round when the simulator is on the machine.

When it isn't - a laptop on the sofa, a work computer, a new machine you haven't
installed anything on yet - there is no apt.dat to read, and until now that meant
no airports, no aircraft, and an app that could do nothing but show you weather.

This fills the gap with the OurAirports database: three free public CSVs listing
around eighty thousand airports worldwide, their runways, and their radio
frequencies. It reshapes them into exactly the same airport records the apt.dat
parser produces, so everything downstream - the generator, the scenic engine, the
wonders, the approach geometry, the briefings, the export - works unchanged and
does not need to know where the airports came from.

What you lose without the simulator's own files, and there is no way round it:

  * ILS frequencies and courses. Those live in earth_nav.dat and have no open
    equivalent, so approaches fall back to the RNAV straight-in the app already
    builds. Runway lighting is known, so the minimums are still sensible.
  * Which add-on scenery you have. There is nothing to be clever about: every
    airport is treated as stock.
  * Your aircraft. The built-in performance profiles stand in for the .acf files,
    so you pick "a 172" rather than your particular 172.
  * Parking stands, and therefore gate starts.

Everything else is real data: runway lengths, surfaces, lighting, true headings,
both thresholds to five decimal places, field elevation, tower and CTAF
frequencies. It is a different source, not a worse one - OurAirports is where a
good deal of scenery gets its numbers in the first place.

The data is CC0 and needs no account. It downloads once, caches, and then works
offline like everything else here.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import time
from pathlib import Path

BASE = "https://davidmegginson.github.io/ourairports-data/"
FILES = {"airports": "airports.csv", "runways": "runways.csv", "freqs": "airport-frequencies.csv"}
CACHE_FORMAT = 2
M_TO_FT = 3.28084

# OurAirports' type column -> the app's idea of what a place is
KIND = {"large_airport": "land", "medium_airport": "land", "small_airport": "land",
        "seaplane_base": "sea", "heliport": "heli"}

# OurAirports writes the surface in free text, and everyone spells it differently
SURFACE = [
    (("ASP", "ASPH", "CON", "CONC", "PEM", "BIT", "TAR", "PAVED", "MAC", "ASFALT", "COP", "COM"), "paved"),
    (("GRS", "GRASS", "TURF", "GRASS/SOD", "SOD"), "grass"),
    (("GVL", "GRAVEL", "GRE", "CORAL", "SHELL", "PER", "LATERITE"), "gravel"),
    (("DIRT", "SAND", "EARTH", "CLAY", "GROUND", "SOIL", "NAT", "BRICK"), "dirt"),
    (("WATER", "WAT"), "water"),
    (("SNOW", "ICE", "SNO"), "snow"),
]


def surface_of(text):
    s = (text or "").strip().upper().replace("-", " ")
    first = s.split("/")[0].split()[0] if s else ""
    for keys, name in SURFACE:
        if s in keys or first in keys:
            return name
    for keys, name in SURFACE:
        if any(k in s for k in keys if len(k) > 3):
            return name
    return "other" if s else "paved"


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _course(la1, lo1, la2, lo2):
    dy = math.radians(la2 - la1)
    dx = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
    return math.degrees(math.atan2(dx, dy)) % 360


def _len_ft(la1, lo1, la2, lo2):
    dy = (la2 - la1) * 60 * 6076.1
    dx = (lo2 - lo1) * 60 * 6076.1 * math.cos(math.radians((la1 + la2) / 2))
    return int(math.hypot(dx, dy))


class World:
    """The worldwide airport list, downloaded once and kept."""

    def __init__(self, cache_dir: Path):
        self.file = Path(cache_dir) / "world_airports.json.gz"
        self.airports, self.fetched = [], 0.0
        self._load()

    # ---- on disk ----------------------------------------------------------
    def _load(self):
        try:
            with gzip.open(self.file, "rt", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("format") == CACHE_FORMAT:
                self.airports, self.fetched = d["airports"], d.get("t", 0)
        except Exception:
            self.airports, self.fetched = [], 0.0

    def _save(self):
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(self.file, "wt", encoding="utf-8") as f:
                json.dump({"format": CACHE_FORMAT, "t": self.fetched, "airports": self.airports}, f)
        except OSError:
            pass

    def age_days(self):
        return (time.time() - self.fetched) / 86400 if self.fetched else None

    def ready(self):
        return bool(self.airports)

    def line(self):
        if not self.airports:
            return "Not downloaded yet."
        age = self.age_days()
        rwys = sum(len(a["rwys"]) for a in self.airports)
        return (f"{len(self.airports):,} airports, {rwys:,} runways "
                f"(downloaded {age:.0f} days ago)" if age is not None
                else f"{len(self.airports):,} airports")

    # ---- building it ------------------------------------------------------
    def build(self, get, log=print, closed=False):
        """Download the three CSVs and turn them into airport records.

        `get(url, timeout)` fetches bytes - handed in so this module never has to
        care how the app talks to the internet.
        """
        t0 = time.time()
        text = {}
        for key, name in FILES.items():
            log(f"Downloading {name} from OurAirports...")
            raw = get(BASE + name, 180)
            text[key] = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw

        rwys = {}
        n_rwy = 0
        for row in csv.DictReader(io.StringIO(text["runways"])):
            if row.get("closed") == "1":
                continue
            la1, lo1 = _f(row.get("le_latitude_deg")), _f(row.get("le_longitude_deg"))
            la2, lo2 = _f(row.get("he_latitude_deg")), _f(row.get("he_longitude_deg"))
            length = _f(row.get("length_ft"))
            e1 = (row.get("le_ident") or "").strip()
            e2 = (row.get("he_ident") or "").strip()
            if not e1 or not e2:
                continue
            if None in (la1, lo1, la2, lo2):
                continue                      # no geometry, no use to the approach or the scoring
            r = {"e": [e1, e2],
                 "len": int(length) if length else _len_ft(la1, lo1, la2, lo2),
                 "w": int(_f(row.get("width_ft")) or 75),
                 "s": surface_of(row.get("surface")),
                 "lit": row.get("lighted") == "1",
                 "h": round(_f(row.get("le_heading_degT")) or _course(la1, lo1, la2, lo2), 1),
                 "c": [round(la1, 6), round(lo1, 6), round(la2, 6), round(lo2, 6)]}
            rwys.setdefault((row.get("airport_ident") or "").strip().upper(), []).append(r)
            n_rwy += 1

        want = {"TWR": "twr", "TOWER": "twr", "ATIS": "atis", "CTAF": "ctaf", "UNIC": "ctaf",
                "UNICOM": "ctaf", "GND": "gnd", "GROUND": "gnd"}
        freqs = {}
        for row in csv.DictReader(io.StringIO(text["freqs"])):
            key = want.get((row.get("type") or "").strip().upper())
            mhz = _f(row.get("frequency_mhz"))
            if not key or not mhz or not (108.0 <= mhz <= 137.0):
                continue
            ident = (row.get("airport_ident") or "").strip().upper()
            freqs.setdefault(ident, {}).setdefault(key, round(mhz, 3))

        out = []
        for row in csv.DictReader(io.StringIO(text["airports"])):
            typ = (row.get("type") or "").strip()
            if typ == "closed" and not closed:
                continue
            kind = KIND.get(typ)
            if not kind:
                continue
            ident = (row.get("ident") or "").strip().upper()
            lat, lon = _f(row.get("latitude_deg")), _f(row.get("longitude_deg"))
            if not ident or lat is None or lon is None:
                continue
            rs = rwys.get(ident, [])
            if kind == "land" and not rs:
                continue                      # an airport with no runway we can place you on
            elev = _f(row.get("elevation_ft"))
            if elev is None:
                elev = 0
            alias = {(row.get("local_code") or "").strip().upper(),
                     (row.get("gps_code") or "").strip().upper(),
                     (row.get("iata_code") or "").strip().upper()}
            f = freqs.get(ident, {})
            a = {"id": ident, "name": (row.get("name") or ident).strip(), "kind": kind,
                 "elev": int(elev), "rwys": rs, "ramps": [], "pack": None,
                 "tower": "twr" in f, "atis": "atis" in f,
                 "lat": round(lat, 5), "lon": round(lon, 5),
                 "city": (row.get("municipality") or "").strip(),
                 "state": (row.get("iso_region") or "").split("-")[-1],
                 "iso": (row.get("iso_country") or "").strip(),
                 "country": "", "alias": sorted(x for x in alias if x and x != ident),
                 "ils": [], "oa_type": typ, "wiki": (row.get("wikipedia_link") or "").strip(),
                 "iata": (row.get("iata_code") or "").strip(),
                 "sched": row.get("scheduled_service") == "yes",
                 "keywords": (row.get("keywords") or "")[:120], "world": True}
            if f:
                a["freqs"] = f
            out.append(a)
        self.airports, self.fetched = out, time.time()
        self._save()
        log(f"Worldwide database: {len(out):,} airports, {n_rwy:,} runways, "
            f"{len(freqs):,} with published frequencies, in {time.time() - t0:.0f} s.")
        return len(out)

    # ---- using it ---------------------------------------------------------
    def copy(self, country_names=None):
        """A fresh list for the app to own, with country names filled in."""
        out = []
        for a in self.airports:
            b = dict(a)
            b["rwys"] = [dict(r) for r in a["rwys"]]
            if country_names:
                b["country"] = country_names.get(b.get("iso", ""), "")
            out.append(b)
        return out


NO_ILS = ("These airports come from the worldwide database, which has no ILS frequencies - "
          "only X-Plane's own earth_nav.dat has those. Approaches will be built as RNAV "
          "straight-ins, which is what the app does at any airport without a localizer.")

NO_ACF = ("Without X-Plane there are no .acf files to read, so the aircraft list is the built-in "
          "performance profiles rather than the aeroplanes you actually own.")

NO_SIM = ("Nothing can be set up in the simulator from here, for the obvious reason. Everything "
          "else works: briefings, the numbers, weather, the scenic engine, exports and the .fms "
          "plan you can drop into X-Plane later.")
