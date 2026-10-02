"""
xp_history.py - the weather on a particular day, anywhere, any year.

The app can already fly today's real weather. This flies a day that has already
happened: the afternoon of the derecho, the morning you actually got weathered
in at Aspen, the Christmas Eve you were at the airport instead of at home.

Two sources, tried in that order:

  * Iowa State's ASOS archive, which keeps the raw METARs airports actually
    filed, hour by hour, going back decades. When a station reported, this is
    not a model of the weather - it is the weather, in the words the station
    used. Parsed here, because the archive hands back the raw text.

  * Open-Meteo's ERA5 archive, which is reanalysis: a model run backwards over
    every observation anyone made, on a grid covering the whole planet back to
    1940. It knows nothing about your airport specifically, and it has no idea
    what the visibility was, so some of what comes out of it here is inferred
    from temperature, dew point and rain. It is an honest guess, and it is
    labelled as one. But it works over the Sahara and the Southern Ocean, and
    it works for 1952.

Both are free and need no account. Both are optional: a day you have already
fetched is kept on disk and flies again offline, and if neither can be reached
the app carries on with everything else.

Nothing here is a forecast and nothing is live. The point is a date.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import urllib.parse
import urllib.request

UA = "XPlaneFlightIdeas/6.8 (personal flight-sim helper; python urllib)"
ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ERA5_URL = "https://archive-api.open-meteo.com/v1/archive"
ERA5_FIELDS = ("temperature_2m,dew_point_2m,relative_humidity_2m,precipitation,snowfall,"
               "pressure_msl,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
               "wind_speed_10m,wind_direction_10m,wind_gusts_10m")
EARLIEST = 1940                     # ERA5 starts here; ASOS is patchier before the 1970s

COVER_CODE = ((0.90, "OVC"), (0.60, "BKN"), (0.30, "SCT"), (0.10, "FEW"))


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def cover_code(frac):
    for lim, code in COVER_CODE:
        if frac >= lim:
            return code
    return None


# ==========================================================================
# Reading a raw METAR
# ==========================================================================
_WX_RE = re.compile(r"^(?:[+-]|VC)?(?:TS|SH|FZ|MI|PR|BC|BL|DR)?"
                    r"(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+$")


def parse_metar(raw, ident=None, lat=None, lon=None, when=None):
    """A raw METAR string -> the same observation dict the rest of the app uses.

    `when` is a UTC datetime if you know it (the archive tells us); otherwise the
    day-hour-minute group in the report is all there is and the month is unknown.
    """
    raw = " ".join((raw or "").split())
    if not raw:
        return None
    t = raw.replace("=", "").split()
    if t and t[0] in ("METAR", "SPECI"):
        t = t[1:]
    if not t:
        return None
    o = {"id": ident or t[0], "lat": lat, "lon": lon, "raw": raw, "clouds": [], "wx": "",
         "wdir": None, "wspd": None, "wgst": 0, "vis": None, "temp": None, "dewp": None,
         "altim": None, "cat": "", "source": "metar"}
    if when is not None:
        o["time"] = when.replace(tzinfo=dt.timezone.utc).timestamp() if when.tzinfo is None else when.timestamp()
        o["when"] = when.strftime("%Y-%m-%d %H:%MZ")
    cavok = "CAVOK" in t
    i = 1
    vis_frac = None
    while i < len(t):
        w = t[i]
        i += 1
        if w in ("AUTO", "COR", "RMK", "NOSIG"):
            if w == "RMK":
                break
            continue
        m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})Z", w)
        if m and "time" not in o:
            o["day"] = int(m.group(1))
            continue
        # wind
        m = re.fullmatch(r"(\d{3}|VRB|///)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)", w)
        if m:
            unit = m.group(4)
            k = 1.94384 if unit == "MPS" else 0.539957 if unit == "KMH" else 1.0
            o["wdir"] = 0 if m.group(1) in ("VRB", "///") else int(m.group(1))
            o["vrb"] = m.group(1) == "VRB"
            o["wspd"] = round(int(m.group(2)) * k)
            o["wgst"] = round(int(m.group(3)) * k) if m.group(3) else 0
            continue
        if re.fullmatch(r"\d{3}V\d{3}", w):          # variable-direction range
            continue
        # visibility
        if w.endswith("SM"):
            body = w[:-2]
            if body.startswith("M"):                  # "less than"
                body = body[1:]
                o["vis_less"] = True
            if vis_frac is not None:
                o["vis"] = vis_frac + _frac(body)
                vis_frac = None
            else:
                o["vis"] = _frac(body)
            continue
        if re.fullmatch(r"\d", w) and i < len(t) and t[i].endswith("SM") and "/" in t[i]:
            vis_frac = float(w)                       # the "1" of "1 1/2SM"
            continue
        if re.fullmatch(r"\d{4}", w) and o["vis"] is None and not cavok:
            metres = int(w)
            o["vis"] = 10.0 if metres >= 9999 else round(metres / 1609.34, 2)
            continue
        if re.fullmatch(r"(\d{4}|////)(N|NE|E|SE|S|SW|W|NW)", w):
            continue
        if w.startswith("R") and "/" in w:            # runway visual range
            continue
        # cloud
        m = re.fullmatch(r"(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(CB|TCU)?", w)
        if m:
            base = None if m.group(2) == "///" else int(m.group(2)) * 100
            o["clouds"].append((m.group(1), base))
            continue
        if w in ("SKC", "CLR", "NSC", "NCD"):
            continue
        # temperature / dew point
        m = re.fullmatch(r"(M?\d{2})/(M?\d{2})?", w)
        if m:
            o["temp"] = -int(m.group(1)[1:]) if m.group(1).startswith("M") else int(m.group(1))
            if m.group(2):
                o["dewp"] = -int(m.group(2)[1:]) if m.group(2).startswith("M") else int(m.group(2))
            continue
        # altimeter
        m = re.fullmatch(r"A(\d{4})", w)
        if m:
            o["altim"] = int(m.group(1)) / 100.0
            continue
        m = re.fullmatch(r"Q(\d{4})", w)
        if m:
            o["altim"] = round(int(m.group(1)) * 0.0295300, 2)
            continue
        if _WX_RE.match(w) and len(w) <= 9:
            o["wx"] = (o["wx"] + " " + w).strip()
    if cavok:
        o["vis"] = o["vis"] or 10.0
    if o["vis"] is None:
        o["vis"] = 10.0
    if o["altim"] is None:
        o["altim"] = 29.92
    if o["wdir"] is None:
        o["wdir"], o["wspd"] = 0, 0
    o["wgst"] = max(o["wgst"], o["wspd"] or 0) if o["wgst"] else 0
    return o


def _frac(s):
    """'1/2' or '10' -> a number."""
    s = s.strip()
    if "/" in s:
        a, _, b = s.partition("/")
        return _f(a, 0) / max(1.0, _f(b, 1))
    return _f(s, 10.0)


# ==========================================================================
# Source 1: the METARs that were actually filed
# ==========================================================================
def _station_ids(ident):
    """What the archive might call this airport: ICAO first, then the bare US id."""
    ident = (ident or "").strip().upper()
    out = [ident]
    if len(ident) == 4 and ident[0] in "KPC":
        out.append(ident[1:])
    return [x for x in out if x]


def asos_day(ident, date, lat=None, lon=None, timeout=30, url=None):
    """Every METAR that station filed on this UTC day. [] if it filed none."""
    nxt = date + dt.timedelta(days=1)
    for sid in _station_ids(ident):
        q = urllib.parse.urlencode({
            "station": sid, "data": "metar", "tz": "UTC", "format": "onlycomma",
            "latlon": "yes", "missing": "empty", "trace": "empty",
            "report_type": ["3", "4"],          # routine and special - SPECIs are the interesting ones
            "year1": date.year, "month1": date.month, "day1": date.day,
            "year2": nxt.year, "month2": nxt.month, "day2": nxt.day}, doseq=True)
        text = _get((url or ASOS_URL) + "?" + q, timeout)
        out = []
        for line in text.splitlines()[1:]:
            parts = line.split(",", 4)
            if len(parts) < 5 or not parts[4].strip():
                continue
            try:
                when = dt.datetime.strptime(parts[1].strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if when.date() != date:
                continue
            o = parse_metar(parts[4].strip('" '), ident=ident,
                            lat=_f(parts[3], lat), lon=_f(parts[2], lon), when=when)
            if o:
                o["source"] = "asos"
                out.append(o)
        if out:
            return out
    return []


# ==========================================================================
# Source 2: reanalysis, for everywhere else
# ==========================================================================
def lcl_ft(temp_c, dew_c):
    """Cloud base above the ground, the spread rule every student learns."""
    if temp_c is None or dew_c is None:
        return 4000.0
    return max(200.0, min(14000.0, (temp_c - dew_c) * 400.0))


def guess_vis(temp, dew, rh, precip_mm, snow_cm):
    """ERA5 doesn't do visibility, so this is a rule of thumb, and says so."""
    v = 10.0
    if rh is not None:
        if rh >= 99.5:
            v = 0.4
        elif rh >= 98:
            v = 1.5
        elif rh >= 96:
            v = 4.0
        elif rh >= 92:
            v = 7.0
    if temp is not None and dew is not None:
        spread = temp - dew
        if spread <= 0.3:
            v = min(v, 0.4)
        elif spread <= 1.0:
            v = min(v, 2.0)
        elif spread <= 2.0:
            v = min(v, 5.0)
    if snow_cm:
        v = min(v, 3.0 if snow_cm < 0.5 else 1.0 if snow_cm < 2 else 0.4)
    elif precip_mm:
        v = min(v, 7.0 if precip_mm < 1 else 4.0 if precip_mm < 4 else 2.0)
    return round(v, 2)


def _era5_wx(temp, precip_mm, snow_cm, vis):
    if snow_cm and snow_cm > 0.05:
        return ("+SN" if snow_cm > 2 else "SN" if snow_cm > 0.5 else "-SN")
    if precip_mm and precip_mm > 0.05:
        heavy = "+" if precip_mm > 4 else "" if precip_mm > 1 else "-"
        if temp is not None and temp <= 0.5:
            return heavy + "FZRA"
        return heavy + "RA"
    if vis is not None and vis < 0.7:
        return "FG"
    if vis is not None and vis < 5:
        return "BR"
    return ""


def era5_day(lat, lon, date, ident="", timeout=30, url=None):
    """24 hourly pseudo-observations for any point on earth."""
    q = urllib.parse.urlencode({
        "latitude": round(float(lat), 4), "longitude": round(float(lon), 4),
        "start_date": date.isoformat(), "end_date": date.isoformat(),
        "hourly": ERA5_FIELDS, "timezone": "UTC",
        "wind_speed_unit": "kn", "temperature_unit": "celsius", "precipitation_unit": "mm"})
    data = json.loads(_get((url or ERA5_URL) + "?" + q, timeout))
    h = data.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        return []
    out = []
    for i, stamp in enumerate(times):
        def v(name):
            col = h.get(name) or []
            return _f(col[i]) if i < len(col) else None
        temp, dew, rh = v("temperature_2m"), v("dew_point_2m"), v("relative_humidity_2m")
        precip, snow = v("precipitation"), v("snowfall")
        base = lcl_ft(temp, dew)
        clouds = []
        for name, hgt in (("cloud_cover_low", base), ("cloud_cover_mid", 12000.0),
                          ("cloud_cover_high", 24000.0)):
            frac = (v(name) or 0) / 100.0
            code = cover_code(frac)
            if code:
                clouds.append((code, int(round(hgt / 100.0) * 100)))
        vis = guess_vis(temp, dew, rh, precip, snow)
        spd = v("wind_speed_10m") or 0.0
        gust = v("wind_gusts_10m") or 0.0
        msl = v("pressure_msl")
        try:
            when = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        o = {"id": ident or "ERA5", "lat": lat, "lon": lon, "clouds": clouds,
             "wdir": int(round(v("wind_direction_10m") or 0)) % 360,
             "wspd": round(spd), "wgst": round(gust) if gust > spd + 2 else 0,
             "vis": vis, "temp": round(temp) if temp is not None else None,
             "dewp": round(dew) if dew is not None else None,
             "altim": round((msl or 1013.25) * 0.02953, 2),
             "wx": _era5_wx(temp, precip, snow, vis), "cat": "", "source": "era5",
             "time": when.replace(tzinfo=dt.timezone.utc).timestamp(),
             "when": when.strftime("%Y-%m-%d %H:%MZ"),
             "raw": "", "estimated": True}
        o["raw"] = as_metar(o)
        out.append(o)
    return out


def as_metar(o):
    """Write an observation back out as a METAR, so a modelled hour reads like one."""
    when = o.get("when") or ""
    day = when[8:10] if len(when) >= 10 else "01"
    hhmm = (when[11:16] or "0000").replace(":", "")
    bits = [o.get("id") or "____", f"{day}{hhmm}Z"]
    spd = int(o.get("wspd") or 0)
    if spd == 0:
        bits.append("00000KT")
    else:
        g = f"G{int(o['wgst']):02d}" if o.get("wgst") else ""
        bits.append(f"{int(o.get('wdir') or 0):03d}{spd:02d}{g}KT")
    vis = o.get("vis")
    if vis is not None:
        bits.append(f"{vis:g}SM" if vis < 10 else "10SM")
    if o.get("wx"):
        bits.append(o["wx"])
    if o.get("clouds"):
        bits += [f"{c}{int(b) // 100:03d}" for c, b in o["clouds"] if b is not None]
    else:
        bits.append("CLR")
    t, d = o.get("temp"), o.get("dewp")
    if t is not None:
        bits.append(f"{'M' if t < 0 else ''}{abs(int(t)):02d}/"
                    + (f"{'M' if d < 0 else ''}{abs(int(d)):02d}" if d is not None else ""))
    bits.append(f"A{int(round((o.get('altim') or 29.92) * 100)):04d}")
    return " ".join(bits)


# ==========================================================================
# A day
# ==========================================================================
class Day:
    """One date at one place: every hour that was reported or modelled."""

    def __init__(self, ident, name, lat, lon, date, obs, source, note=""):
        self.ident, self.name = ident, name
        self.lat, self.lon = lat, lon
        self.date = date
        self.obs = sorted(obs, key=lambda o: o.get("time") or 0)
        self.source = source                      # "asos" or "era5"
        self.note = note

    # -- where the hours are -------------------------------------------------
    @property
    def estimated(self):
        return self.source != "asos"

    def offset_h(self):
        """Rough local-time offset, straight off the longitude. No politics."""
        return round((self.lon or 0) / 15.0)

    def utc_hour(self, o):
        t = o.get("time")
        if not t:
            return 0
        return dt.datetime.fromtimestamp(t, dt.timezone.utc).hour

    def local_hour(self, o):
        return (self.utc_hour(o) + self.offset_h()) % 24

    def by_local_hour(self):
        """24 slots, each the observation nearest the top of that local hour."""
        slots = [None] * 24
        for o in self.obs:
            t = o.get("time") or 0
            when = dt.datetime.fromtimestamp(t, dt.timezone.utc)
            local = (when.hour + when.minute / 60.0 + self.offset_h()) % 24
            h = int(round(local)) % 24
            cur = slots[h]
            if cur is None or abs(local - h) < abs(cur[1] - h):
                slots[h] = (o, local)
        return [s[0] if s else None for s in slots]

    def at_local(self, hour):
        """The observation to use for this local hour, reaching to the nearest one."""
        slots = self.by_local_hour()
        h = int(hour) % 24
        for step in range(0, 13):
            for k in ((h - step) % 24, (h + step) % 24):
                if slots[k]:
                    return slots[k]
        return self.obs[0] if self.obs else None

    # -- words ---------------------------------------------------------------
    def timeline(self, wx_mod):
        """One line per local hour, for scrubbing through the day."""
        out = []
        for h, o in enumerate(self.by_local_hour()):
            if not o:
                out.append((h, "", "", ""))
                continue
            f = wx_mod._finish(dict(o))
            ceil = f"{f['ceiling']:,.0f} ft" if f.get("ceiling") else "no ceiling"
            wind = "calm" if not o.get("wspd") else f"{o['wdir']:03.0f} at {o['wspd']:.0f}" + (
                f"G{o['wgst']:.0f}" if o.get("wgst") else "")
            bits = f"{ceil}, {o['vis']:g} SM, {wind}"
            if o.get("wx"):
                said = getattr(wx_mod, "decode_wx", lambda c: "")(o["wx"])
                bits += f", {said or o['wx']}"
            if o.get("temp") is not None:
                bits += f", {o['temp']:.0f}°C"
            out.append((h, f.get("cat") or "", bits, o.get("raw") or ""))
        return out

    def summary(self, wx_mod):
        """What kind of day this was, in one line."""
        cats, gust, vis, ceil = [], 0, [], []
        for o in self.obs:
            f = wx_mod._finish(dict(o))
            cats.append(f.get("cat") or "")
            gust = max(gust, o.get("wgst") or o.get("wspd") or 0)
            if o.get("vis") is not None:
                vis.append(o["vis"])
            if f.get("ceiling"):
                ceil.append(f["ceiling"])
        worst = next((c for c in ("LIFR", "IFR", "MVFR", "VFR") if c in cats), "?")
        bits = [f"{len(self.obs)} reports" if self.source == "asos" else f"{len(self.obs)} modelled hours",
                f"worst {worst}"]
        if vis:
            bits.append(f"visibility down to {min(vis):g} SM")
        if ceil:
            bits.append(f"lowest ceiling {min(ceil):,.0f} ft")
        if gust:
            bits.append(f"wind to {gust:.0f} kt")
        return " · ".join(bits)

    def where(self):
        return self.name or self.ident or f"{self.lat:.3f}, {self.lon:.3f}"

    def title(self):
        return f"{self.where()} – {self.date.strftime('%d %B %Y')}"

    def day_of_year(self):
        return self.date.timetuple().tm_yday

    # -- keeping it ----------------------------------------------------------
    def to_dict(self):
        return {"v": 1, "ident": self.ident, "name": self.name, "lat": self.lat, "lon": self.lon,
                "date": self.date.isoformat(), "source": self.source, "note": self.note,
                "obs": [{k: v for k, v in o.items() if k != "cb"} for o in self.obs]}

    @classmethod
    def from_dict(cls, d):
        obs = []
        for o in d.get("obs") or ():
            o = dict(o)
            o["clouds"] = [tuple(c) for c in o.get("clouds") or ()]
            obs.append(o)
        return cls(d.get("ident", ""), d.get("name", ""), d.get("lat"), d.get("lon"),
                   dt.date.fromisoformat(d["date"]), obs, d.get("source", "era5"), d.get("note", ""))


def cache_key(ident, lat, lon, date):
    who = (ident or "").strip().upper() or f"{float(lat):.2f}_{float(lon):.2f}"
    return re.sub(r"[^A-Z0-9_.-]", "_", f"{who}_{date.isoformat()}")


def fetch_day(ident, name, lat, lon, date, cache_dir=None, timeout=30, prefer_station=True,
              urls=None, on_status=None):
    """A whole day at one place. Cache first, then the station, then reanalysis."""
    say = on_status or (lambda s: None)
    urls = urls or {}
    if date > dt.date.today():
        raise ValueError("That date hasn't happened yet - this only looks backwards.")
    if date.year < EARLIEST:
        raise ValueError(f"The archives start in {EARLIEST}. Before that nobody was writing it down "
                         f"in a form a computer can read.")
    p = None
    if cache_dir:
        p = cache_dir / (cache_key(ident, lat, lon, date) + ".json")
        if p.is_file():
            try:
                say("Already had that day saved.")
                return Day.from_dict(json.loads(p.read_text()))
            except Exception:
                pass
    obs, source, note = [], "", ""
    err = []
    reached = False
    if prefer_station and ident:
        say(f"Asking the ASOS archive what {ident} filed that day...")
        try:
            obs = asos_day(ident, date, lat, lon, timeout, urls.get("asos"))
            reached = True
            if obs:
                source = "asos"
        except Exception as e:
            err.append(f"the METAR archive ({e})")
    if not obs:
        if ident and prefer_station and reached:
            note = f"{ident} filed nothing that day, so this is reanalysis."
            say(f"Nothing from {ident}. Falling back to the worldwide reanalysis...")
        elif ident and prefer_station:
            note = "The METAR archive couldn't be reached, so this is reanalysis."
            say("Couldn't reach the METAR archive. Trying the worldwide reanalysis...")
        else:
            say("Asking the worldwide reanalysis...")
        try:
            obs = era5_day(lat, lon, date, ident, timeout, urls.get("era5"))
            source = "era5"
        except Exception as e:
            err.append(f"the reanalysis archive ({e})")
    if not obs:
        raise ValueError("Couldn't get that day from " + " or ".join(err or ["either archive"])
                         + ". Both are free public services, so this is usually the internet, "
                           "not you - the rest of the app carries on working.")
    day = Day(ident, name, lat, lon, date, obs, source, note)
    if p is not None:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(day.to_dict()))
        except OSError:
            pass
    return day


# ==========================================================================
# Days worth keeping
# ==========================================================================
class Days:
    """The days you liked enough to fly again."""

    def __init__(self, path):
        self.path = path
        self.items = []
        try:
            self.items = json.loads(self.path.read_text())
        except Exception:
            self.items = []

    def save(self):
        try:
            self.path.write_text(json.dumps(self.items[:200], indent=1))
        except OSError:
            pass

    def add(self, day: Day, label="", hour=None):
        d = day.to_dict()
        d["label"] = label or day.title()
        d["hour"] = hour
        self.items = [x for x in self.items if not (x.get("ident") == d["ident"]
                                                    and x.get("date") == d["date"])]
        self.items.insert(0, d)
        self.save()
        return d

    def remove(self, i):
        if 0 <= i < len(self.items):
            self.items.pop(i)
            self.save()

    def day(self, i):
        return Day.from_dict(self.items[i]) if 0 <= i < len(self.items) else None

    def label(self, i):
        d = self.items[i]
        return d.get("label") or f"{d.get('ident') or '?'} {d.get('date')}"


# ==========================================================================
# Days that are famous for their weather
# ==========================================================================
NOTABLE = [
    ("KORD", "Chicago O'Hare", 41.978, -87.905, "1979-01-13", 12,
     "The blizzard that buried Chicago and cost a mayor his job."),
    ("KDEN", "Denver", 39.862, -104.673, "2003-03-18", 15,
     "Four feet of snow on the Front Range. Nothing moved for two days."),
    ("KSTL", "St Louis", 38.748, -90.370, "2012-04-28", 21,
     "A night of supercells across Missouri."),
    ("KBOS", "Boston", 42.363, -71.006, "1978-02-06", 14,
     "The Blizzard of '78 - hurricane-force wind and snow on an easterly."),
    ("KLGA", "New York LaGuardia", 40.777, -73.872, "2012-10-29", 18,
     "Sandy coming ashore."),
    ("EGLL", "London Heathrow", 51.478, -0.461, "1987-10-16", 3,
     "The Great Storm. Gusts over 90 kt across southern England."),
    ("KASE", "Aspen", 39.223, -106.869, "2021-12-31", 10,
     "New Year's Eve in the Colorado mountains."),
    ("PANC", "Anchorage", 61.174, -149.996, "2012-01-15", 9,
     "The winter Alaska ran out of places to put the snow."),
    ("KSFO", "San Francisco", 37.619, -122.375, "2017-02-20", 8,
     "An atmospheric river straight into the Bay."),
    ("KMIA", "Miami", 25.793, -80.290, "1992-08-24", 6,
     "Hurricane Andrew's morning."),
    ("BIKF", "Keflavik", 63.985, -22.605, "2015-12-07", 12,
     "An Icelandic low at its worst: wind, snow and no daylight to speak of."),
    ("NZQN", "Queenstown", -45.021, 168.739, "2020-02-03", 14,
     "A clear summer afternoon in the Southern Alps, for when you want the opposite."),
]


def notable():
    """(ident, name, lat, lon, date, hour, why) for days worth a look."""
    out = []
    for ident, name, lat, lon, iso, hour, why in NOTABLE:
        out.append((ident, name, lat, lon, dt.date.fromisoformat(iso), hour, why))
    return out
