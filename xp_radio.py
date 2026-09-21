"""
xp_radio.py - what you'd hear and say on the radio, and places that aren't airports.

Two things live here:

  * an ATIS for the flight's weather, written the way a real one reads, and the
    radio calls you'd make on the way - towered or not;
  * "spots": your own lat/lon landing places (a gravel bar, a ridge, a ranch
    strip that isn't in the scenery) that the app can treat like airports.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

LETTERS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India",
           "Juliet", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
           "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray", "Yankee", "Zulu"]
DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
          "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "niner"}


def say_number(n, digits=True):
    n = int(round(n))
    sign = "minus " if n < 0 else ""
    s = str(abs(n))
    return sign + (" ".join(DIGITS.get(c, c) for c in s) if digits else s)


VIS_WORDS = {0.25: "one quarter", 0.5: "one half", 0.75: "three quarters", 1.0: "one",
             1.25: "one and one quarter", 1.5: "one and one half", 1.75: "one and three quarters",
             2.0: "two", 2.5: "two and one half", 3.0: "three", 4.0: "four", 5.0: "five",
             6.0: "six", 7.0: "seven", 8.0: "eight", 9.0: "niner"}


def say_vis(sm):
    if sm >= 10:
        return "one zero"
    for k, v in VIS_WORDS.items():
        if abs(sm - k) < 0.02:
            return v
    return say_number(sm)


def say_ident(ident):
    out = []
    for ch in str(ident).upper():
        if ch.isdigit():
            out.append(DIGITS[ch])
        elif ch.isalpha():
            out.append(LETTERS[ord(ch) - 65])
        else:
            out.append(ch)
    return " ".join(out)


def say_altitude(ft):
    ft = int(round(ft / 100.0) * 100)
    if ft >= 18000:
        return f"flight level {int(ft / 100)}"
    th, hu = divmod(ft, 1000)
    bits = []
    if th:
        bits.append(f"{say_number(th)} thousand")
    if hu:
        bits.append(f"{say_number(hu // 100)} hundred")
    return " ".join(bits) or "sea level"


def say_altimeter(inhg):
    return " ".join(DIGITS[c] for c in f"{inhg:.2f}".replace(".", ""))


def sky_phrase(wx):
    """The cloud part of the weather, without the visibility tacked on."""
    txt = wx.sky_text
    txt = re.sub(r",?\s*(vis[^,]*|[\d/ ]+SM[^,]*)$", "", txt, flags=re.I).strip(" ,")
    return txt or "clear"


def dew_point(wx):
    """A plausible dew point for this visibility - real METARs don't come with one here."""
    spread = 0 if wx.vis < 1 else 1 if wx.vis < 3 else 2 if wx.vis < 5 else 4 if wx.vis < 10 else 6
    return wx.temp - spread


def best_runway(apt, wx, core):
    best = None
    for end, hdg, r in core.runway_ends(apt):
        ang = math.radians(wx.wind_dir - hdg)
        head = wx.wind_spd * math.cos(ang)
        if best is None or head > best[1]:
            best = (end, head)
    return best[0] if best else None


def atis(apt, wx, core, letter_index=0):
    """A spoken-style ATIS for this airport in this weather."""
    letter = LETTERS[letter_index % 26]
    if apt.get("spot"):
        return {"letter": letter, "runway": None, "rules": wx.flight_rules(),
                "text": (f"{apt['name']} is your own spot - there is no ATIS and nobody to talk to.\n"
                         f"Weather there: {wx.describe()}.\n"
                         f"Look it over from the air first, note the wind, and plan your escape.")}
    rwy = best_runway(apt, wx, core)
    wind = ("calm" if wx.wind_spd <= 2 else
            f"{say_number(wx.wind_dir or 360)} at {say_number(wx.wind_spd)}"
            + (f", gusts {say_number(wx.wind_spd + wx.gust)}" if wx.gust else ""))
    vis = say_vis(wx.vis)
    lines = [f"{apt['name']} information {letter}.",
             f"Wind {wind}. Visibility {vis}. {sky_phrase(wx)}.",
             f"Temperature {say_number(wx.temp)}, dew point {say_number(dew_point(wx))}. "
             f"Altimeter {say_altimeter(wx.altimeter)}.",
             f"Landing and departing runway {say_ident(rwy)}." if rwy else "Landing and departing the active runway."]
    rules = wx.flight_rules()
    if rules in ("IFR", "LIFR"):
        lines.append(("Ceiling " + say_altitude(wx.ceiling) + " overcast. " if wx.ceiling else "")
                     + "Instrument approaches in use.")
    elif rules == "MVFR":
        lines.append("Marginal VFR conditions.")
    lines.append(f"Advise on initial contact you have information {letter}.")
    return {"letter": letter, "runway": rwy, "text": "\n".join(lines), "rules": rules}


def calls(idea, ac, core, callsign="November one two three four five", letter=None, wx=None):
    """The radio calls for this flight, in order, with a note on each."""
    s = idea.stops
    dep, arr = s[0], s[-1]
    wx = wx or idea.wx
    info = letter or atis(dep, wx, core)["letter"]
    dep_rwy = best_runway(dep, wx, core)
    out = []
    cruise = core.cruise_alt(s, ac, idea.ifr)
    nxt = s[1] if len(s) > 1 else arr
    prev = s[-2] if len(s) > 1 else dep
    if idea.ifr:
        out.append(("Clearance",
                    f"{short(dep)} clearance, {callsign}, IFR to {say_dest(arr)}, ready to copy."))
    if dep["tower"]:
        out.append(("Taxi (ground)",
                    f"{short(dep)} ground, {callsign}, at the ramp with information {info}, "
                    f"{'IFR' if idea.ifr else 'VFR'} to {say_dest(arr)}, request taxi."))
        out.append(("Ready (tower)",
                    f"{short(dep)} tower, {callsign}, holding short runway "
                    f"{say_ident(dep_rwy) if dep_rwy else 'the active'}, ready for departure, "
                    f"{compass(core.crs(dep, nxt))}bound."))
    else:
        out.append(("Taxi (CTAF)",
                    f"{short(dep)} traffic, {callsign}, taxiing to runway "
                    f"{say_ident(dep_rwy) if dep_rwy else 'the active'}, {short(dep)}."))
        out.append(("Departing (CTAF)",
                    f"{short(dep)} traffic, {callsign}, departing runway "
                    f"{say_ident(dep_rwy) if dep_rwy else 'the active'}, departing to the "
                    f"{compass(core.crs(dep, nxt))}, {short(dep)}."))
    out.append(("En route",
                f"{callsign}, level {say_altitude(cruise)}." if idea.ifr else
                f"Centre, {callsign}, {say_dest(dep)} to {say_dest(arr)}, "
                f"{say_altitude(cruise)}, request flight following."))
    for j, mid in enumerate(s[1:-1], start=1):
        out.append((f"Overhead stop {j}",
                    f"{short(mid)} traffic, {callsign}, overhead at {say_altitude(cruise)}, "
                    f"{'landing' if mid['id'] not in getattr(idea, 'overfly', ()) else 'transiting'}, "
                    f"{short(mid)}."))
    if arr.get("spot"):
        out.append(("Arriving at your spot",
                    f"Nobody to call. Tell Centre you're cancelling flight following, then have a good "
                    f"look at {short(arr)}: wind, slope, surface, and where you'd go if you didn't like it."))
        return out
    if arr["tower"]:
        out.append(("10 nm out (tower)",
                    f"{short(arr)} tower, {callsign}, one zero miles "
                    f"{compass(core.crs(arr, prev))}, {say_altitude(cruise)}, with information {info}, "
                    f"inbound to land."))
        out.append(("On the ground",
                    f"{short(arr)} ground, {callsign}, clear of runway, taxi to parking."))
    else:
        out.append(("10 nm out (CTAF)",
                    f"{short(arr)} traffic, {callsign}, one zero miles "
                    f"{compass(core.crs(arr, prev))}, inbound for the pattern, {short(arr)}."))
        out.append(("Downwind", f"{short(arr)} traffic, {callsign}, left downwind runway "
                                f"{say_ident(best_runway(arr, wx, core) or '')}, {short(arr)}."))
        out.append(("Base", f"{short(arr)} traffic, {callsign}, left base, {short(arr)}."))
        out.append(("Final", f"{short(arr)} traffic, {callsign}, final, full stop, {short(arr)}."))
        out.append(("Clear of the runway",
                    f"{short(arr)} traffic, {callsign}, clear of the active, {short(arr)}."))
    return out


def say_dest(apt):
    """How you'd name a destination on the radio."""
    return short(apt) if apt.get("spot") else say_ident(apt["id"])


def short(apt):
    """The name you'd actually say on the radio."""
    n = apt["name"]
    for junk in (" Regional", " Rgnl", " Municipal", " Muni", " International", " Intl",
                 " Airport", " Field", " Fld", " County", " Co"):
        n = n.replace(junk, "")
    return n.strip() or apt["id"]


def compass(deg):
    names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    return names[int((deg % 360) / 45 + 0.5) % 8]


# ==========================================================================
# Your own landing spots
# ==========================================================================
class Spots:
    """Places that aren't airports: gravel bars, ridges, meadows, oil rigs."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.items = []
        try:
            self.items = json.loads(self.path.read_text())
        except Exception:
            pass

    def save(self):
        try:
            self.path.write_text(json.dumps(self.items, indent=1))
        except OSError:
            pass

    def add(self, name, lat, lon, elev=0, surface="dirt", length=0, notes=""):
        ident = self._ident(name)
        self.items = [x for x in self.items if x["id"] != ident]
        self.items.append({"id": ident, "name": name, "lat": float(lat), "lon": float(lon),
                           "elev": int(elev), "surface": surface, "len": int(length), "notes": notes})
        self.items.sort(key=lambda x: x["name"].lower())
        self.save()
        return self.items[-1]

    def remove(self, item):
        self.items = [x for x in self.items if x["id"] != item["id"]]
        self.save()

    @staticmethod
    def _ident(name):
        base = "".join(ch for ch in name.upper() if ch.isalnum())[:6] or "SPOT"
        return "*" + base

    def as_airports(self):
        """The same shape as an X-Plane airport, so the rest of the app can use them."""
        out = []
        for x in self.items:
            rw = [{"e": ["00", "18"], "len": x["len"] or 1200, "w": 40, "s": x["surface"],
                   "lit": False, "h": 0,
                   "lat": x["lat"], "lon": x["lon"]}] if x["surface"] != "water" else \
                 [{"e": ["00", "18"], "len": x["len"] or 3000, "w": 200, "s": "water",
                   "lit": False, "h": 0, "lat": x["lat"], "lon": x["lon"]}]
            out.append({"id": x["id"], "name": x["name"], "kind": "spot", "elev": x["elev"],
                        "lat": x["lat"], "lon": x["lon"], "rwys": rw, "ramps": [], "tower": False,
                        "atis": False, "ils": [], "pack": None, "spot": True,
                        "city": "", "state": "", "country": "", "iso": "",
                        "notes": x.get("notes", "")})
        return out
