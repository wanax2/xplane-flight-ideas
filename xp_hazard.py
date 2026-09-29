"""
xp_hazard.py - inclement weather: what's in it, and what it does to you.

Two jobs.

The first is reading weather you've built or downloaded and saying what it actually
means: where the freezing level is, whether you'd pick up ice in those clouds, how
rough the air is at each level, how much the wind swings as you come down, and
which of those your aeroplane can't cope with.

The second is the other direction - you name a hazard and it builds the weather.
Thirteen of them, from a fog that won't lift to a thunderstorm you have no business
being near, each with the conditions to produce it and a note on what you're meant
to be practising.

None of this is a forecast. It's a sim, and the point is to fly things that would
be a bad idea in a real aeroplane.
"""
from __future__ import annotations

import math

LAPSE = 1.98            # degrees C per 1,000 ft, standard atmosphere


# ==========================================================================
# Reading the weather
# ==========================================================================
def freezing_level(temp_c, elev_ft=0):
    """Height AMSL of the 0 C isotherm. Below field elevation when it's freezing out."""
    return int(round(elev_ft + temp_c / LAPSE * 1000))


def temp_at(temp_c, elev_ft, height_ft):
    """Temperature at a height, from the surface temperature and the standard lapse rate."""
    return temp_c - LAPSE * (height_ft - elev_ft) / 1000.0


def icing_band(temp_c, elev_ft=0):
    """The height band where supercooled water is likely: 0 C down to about -20 C.

    Returns (zero_level_msl, minus20_level_msl). The band is everything between them;
    the -20 level is always the higher of the two.
    """
    zero = freezing_level(temp_c, elev_ft)
    minus20 = int(round(elev_ft + (temp_c + 20) / LAPSE * 1000))
    return zero, minus20


def precip_kind(wx):
    """rain / snow / none. X-Plane only has a precipitation ratio, so we read the words."""
    if wx.precip <= 0.05:
        return "none"
    t = (wx.sky_text or "").lower()
    if "snow" in t or "sleet" in t:
        return "snow"
    if wx.temp <= -6:
        return "snow"
    return "rain"


def icing_risk(wx, elev_ft=0):
    """Would you pick up ice in this? Returns (level, sentence).

    level is one of none / trace / light / moderate / severe. It is a rule of thumb
    for a sim, not an airframe icing forecast.
    """
    fz = freezing_level(wx.temp, elev_ft)
    zero, minus20 = icing_band(wx.temp, elev_ft)
    layers = [(t, c, elev_ft + b, elev_ft + b + th) for t, c, b, th in wx.layers if c >= 0.25]
    wet = bool(layers) or wx.precip > 0.05
    if not wet:
        return "none", (f"Freezing level {fz:,} ft. Nothing to pick ice up in - "
                        f"no cloud worth the name and no precipitation.")
    # A layer is in the band if it overlaps it at all: top above the 0 C level and
    # base below the -20 C level.
    inband = [L for L in layers if L[3] >= zero and L[2] <= minus20]
    if not inband and wx.precip <= 0.05:
        where = ("below the freezing level, in air that's above zero" if layers and
                 max(L[3] for L in layers) < zero else "above the -20 C level, too cold for "
                 "supercooled water")
        return "none", (f"Freezing level {fz:,} ft, and the cloud sits {where}. "
                        f"You'd stay out of the icing band.")
    # Freezing rain: liquid precipitation falling into air just below zero. Much colder
    # than about -5 and it is snow, which is a nuisance rather than an icing hazard.
    if wx.precip >= 0.25 and -5 <= wx.temp <= 1 and precip_kind(wx) == "rain":
        return "severe", (f"Freezing rain. It is {wx.temp} C on the ground and it's raining, which means "
                          f"a warm layer aloft and clear ice on everything the moment it touches. "
                          f"This is the one that kills aeroplanes - in the real world you do not "
                          f"go, and if you're in it you leave immediately, preferably downwards.")
    if precip_kind(wx) == "snow" and not inband:
        return "trace", (f"Freezing level {fz:,} ft - it is {wx.temp} C, so that precipitation is snow. "
                         f"Snow doesn't stick to a moving aeroplane the way rain does; the runway is "
                         f"the problem, not the airframe.")
    cb = any(t == "cumulonimbus" for t, *_ in inband)
    cu = any(t == "cumulus" for t, *_ in inband)
    deep = max((L[3] - L[2]) for L in inband) if inband else 0
    if cb:
        lvl = "severe"
        why = ("Convective cloud in the icing band - clear ice, and fast, on top of everything else "
               "a thunderstorm will do to you.")
    elif cu and deep > 4000:
        lvl = "moderate"
        why = "Deep convective cloud through the freezing level: mixed and clear ice, accumulating quickly."
    elif deep > 3000 or wx.precip > 0.3:
        lvl = "moderate"
        why = "A thick layer through the freezing level - the classic moderate rime icing setup."
    else:
        lvl = "light"
        why = "A thin layer in the icing band. Rime, slowly, if you sit in it."
    tops = max(L[3] for L in inband) if inband else fz
    out = (f"Freezing level {fz:,} ft, icing band {fz:,} to {minus20:,} ft. {why} "
           f"Cloud tops around {tops:,} ft")
    if tops - fz < 4000:
        out += " - climbing on top is the way out, if your aeroplane will get there."
    else:
        out += " - too deep to climb through in anything light; go down or go around."
    return lvl, out


TURB_WORDS = [(0.10, "smooth"), (0.25, "light"), (0.45, "moderate"),
              (0.85, "severe"), (1.01, "extreme")]


def turb_word(ratio):
    for lim, word in TURB_WORDS:
        if ratio < lim:
            return word
    return "extreme"


def turb_text(wx, elev_ft=0):
    t = wx.turbulence()
    names = ("at the surface", "in the middle levels", "up high")
    bits = [f"{turb_word(x)} {n}" for x, n in zip(t, names)]
    worst = max(t)
    s = "Turbulence: " + ", ".join(bits) + "."
    if worst >= 0.7:
        s += " Severe means structural - slow to manoeuvring speed and don't fight it."
    elif worst >= 0.45:
        s += " Moderate will spill your coffee and make the approach hard work."
    return s


def shear_text(wx):
    sh = wx.shear_deg()
    if not any(sh):
        return "Wind shear: none set - the wind holds its direction all the way down."
    s = (f"Wind shear: the wind swings {sh[0]}° in the surface layer, "
         f"{sh[1]}° in the middle, {sh[2]}° up high.")
    if sh[0] >= 30:
        s += (" That much down low will move you off the centreline on short final and change "
              "your headwind as you flare - carry a few extra knots and expect to work.")
    return s


def crosswind_note(wx, apt, ac, core):
    """The wind against the best runway here, and whether it's past what you accept."""
    if not apt or not core.runway_ends(apt):
        return ""
    best, comp = None, None
    for end, hdg, r in core.runway_ends(apt):
        ang = math.radians((wx.wind_dir - hdg + 540) % 360 - 180)
        head = wx.wind_spd * math.cos(ang)
        cross = abs(wx.wind_spd * math.sin(ang))
        if best is None or head > comp[0]:
            best, comp = end, (head, cross)
    head, cross = comp
    gust_cross = cross * (1 + wx.gust / max(1, wx.wind_spd)) if wx.gust else cross
    s = (f"Best runway here is {best}: {head:+.0f} kt down the runway, {cross:.0f} kt across"
         + (f" (up to {gust_cross:.0f} in the gusts)" if wx.gust else "") + ".")
    limit = ac.get("xwind")
    if limit and gust_cross > limit:
        s += f" Your limit is {limit} kt, so this is beyond it - that's the exercise."
    elif limit and gust_cross > limit * 0.75:
        s += f" Your limit is {limit} kt, so this is most of it."
    return s


def analyse(wx, elev_ft, ac, apt=None, core=None):
    """Everything worth saying about a set of conditions, as lines."""
    L = [f"{wx.flight_rules()}: {wx.describe()}"]
    ice, ice_txt = icing_risk(wx, elev_ft)
    L.append(ice_txt)
    L.append(turb_text(wx, elev_ft))
    L.append(shear_text(wx))
    if apt is not None and core is not None:
        note = crosswind_note(wx, apt, ac, core)
        if note:
            L.append(note)
    c = wx.ceiling
    if c is not None and c < 1000:
        L.append(f"A {c:,} ft ceiling means an instrument approach and a real chance of not getting in. "
                 f"Have somewhere else to go, and the fuel to get there.")
    if wx.vis < 1:
        L.append(f"{wx.vis:g} SM is below the visibility most approaches need. Expect to go around.")
    if not ac.get("ifr", True) and (wx.flight_rules() in ("IFR", "LIFR")):
        L.append("This aeroplane isn't set up for instrument flight. In the real world this is a "
                 "day to stay on the ground; in the sim it's a lesson in why.")
    if ice in ("moderate", "severe") and not (ac.get("acf") or {}).get("deice"):
        L.append("Nothing on this aeroplane removes ice once it's on. Height and temperature are "
                 "your only tools.")
    return L


# ==========================================================================
# Building the weather: thirteen ways to have a bad day
# ==========================================================================
# key: (name, what it is, what you're practising, builder)
def _wx(core, sky, **kw):
    return core.Wx(sky=sky, **kw)


HAZARDS = {
    "lowifr": dict(
        name="Low IFR to minimums",
        what="300 ft overcast, three quarters of a mile.",
        practise="The approach you either complete or go around from. No cheating with the outside view.",
        build=lambda core, r: core.Wx("ovc3", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(4, 12),
                                      temp=r.randint(2, 12)),
        tags="ceiling"),
    "fog": dict(
        name="Fog that won't lift",
        what="Vertical visibility 100 ft, a quarter of a mile, dead calm.",
        practise="Taxiing you can't see the end of, and an approach that is almost certainly a go-around.",
        build=lambda core, r: core.Wx("vv2", wind_dir=0, wind_spd=r.randint(0, 3),
                                      temp=r.randint(-2, 8)).set_vis(0.25).set_ceiling(100),
        tags="ceiling vis"),
    "mist": dict(
        name="Scud running",
        what="Broken at 900 ft, three miles in mist.",
        practise="The most dangerous weather there is for a VFR pilot, because it looks flyable.",
        build=lambda core, r: core.Wx("bkn28", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(6, 14),
                                      temp=r.randint(4, 14)).set_ceiling(900).set_vis(3),
        tags="ceiling vis"),
    "icing": dict(
        name="Airframe icing",
        what="Overcast from 1,200 ft, a few degrees below zero, light precipitation.",
        practise="Recognising it, and getting out - down into warmer air or up through the top.",
        build=lambda core, r: _icing(core, r),
        tags="ice"),
    "frzrain": dict(
        name="Freezing rain",
        what="Rain at minus one on the ground - a warm layer above, ice on everything below.",
        practise="Knowing why the answer is no. Then flying it anyway, once, to see how fast it goes wrong.",
        build=lambda core, r: core.Wx("ovc5ra", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(10, 20),
                                      temp=-1).set_ceiling(900),
        tags="ice"),
    "snow": dict(
        name="Heavy snow",
        what="Half a mile in snow, overcast at 700 ft, minus six.",
        practise="A contaminated runway, no visual references, and a landing distance that doubles.",
        build=lambda core, r: core.Wx("ovc4sn", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(8, 20),
                                      temp=r.randint(-12, -3)).set_vis(0.5).set_ceiling(700),
        tags="ice vis"),
    "ts": dict(
        name="Thunderstorm",
        what="Cumulonimbus to 35,000 ft, gusts to 45, severe turbulence, heavy rain.",
        practise="Not being there. Failing that, what the inside of one actually does to a light aircraft.",
        build=lambda core, r: _storm(core, r),
        tags="turb wind"),
    "xwind": dict(
        name="Crosswind at the limit",
        what="Clear and bright, and 25 knots gusting 35 straight across the runway.",
        practise="Wing down, top rudder, and the discipline to go around when it isn't working.",
        build=lambda core, r: core.Wx("few", wind_dir=r.randrange(0, 360, 10),
                                      wind_spd=r.randint(20, 28), gust=r.randint(8, 14),
                                      temp=r.randint(8, 20)),
        tags="wind"),
    "shear": dict(
        name="Wind shear on final",
        what="The wind 40 degrees different at 500 ft from what the tower is reporting.",
        practise="The sinking feeling at 200 ft, and having the power in before it matters.",
        build=lambda core, r: _shear(core, r),
        tags="wind"),
    "rotor": dict(
        name="Mountain rotor",
        what="Forty knots over the ridge, severe turbulence in the lee, and downdraughts you can't outclimb.",
        practise="Why you cross a ridge at an angle, high, in the morning.",
        build=lambda core, r: _rotor(core, r),
        tags="turb wind"),
    "front": dict(
        name="A front going through",
        what="Broken and ragged, wind veering and gusting, rain showers, dropping pressure.",
        practise="Weather that changes while you're in it - the wind on landing isn't the wind on take-off.",
        build=lambda core, r: core.Wx("sctbkn", wind_dir=r.randrange(0, 360, 10),
                                      wind_spd=r.randint(14, 24), gust=r.randint(8, 16),
                                      temp=r.randint(4, 14), altimeter=round(r.uniform(29.2, 29.6), 2)),
        tags="wind"),
    "hot": dict(
        name="Hot and high",
        what="Thirty-eight degrees, high field elevation, not a cloud anywhere.",
        practise="A density altitude that turns a short runway into a long one and a climb into a crawl.",
        build=lambda core, r: core.Wx("clear", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(0, 8),
                                      temp=r.randint(33, 41), altimeter=round(r.uniform(29.6, 29.9), 2)),
        tags="perf"),
    "dust": dict(
        name="Dust and smoke",
        what="A mile in blowing dust, no horizon, sun a dull orange.",
        practise="Flying on instruments in clear air, which is harder than it sounds.",
        build=lambda core, r: core.Wx("haze3", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(18, 30),
                                      gust=r.randint(6, 12), temp=r.randint(20, 35)).set_vis(1),
        tags="vis"),
}


def _icing(core, r):
    """A deep layer of cloud sitting through the freezing level - the classic rime setup."""
    w = core.Wx("ovc10", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(8, 18),
                temp=r.randint(-8, -2))
    base = r.choice([1200, 1500, 2000])
    w._layers = [("stratus", 1.0, base, r.choice([5000, 6500, 8000]))]
    w._precip, w.custom, w.sky = 0.0, True, "metar"
    w.vis = 4
    w._text = f"Overcast {base:,} ft AGL, thick"
    w.turb = [0.2, 0.25, 0.15]
    return w


def _storm(core, r):
    w = core.Wx("clear", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(18, 28),
                gust=r.randint(15, 22), temp=r.randint(16, 26), altimeter=round(r.uniform(29.3, 29.7), 2))
    w._layers = [("cumulus", 0.5, 1800, 2500), ("cumulonimbus", 0.9, 3500, 30000)]
    w._precip, w.custom, w.sky = 0.9, True, "metar"
    w._text = "Towering cumulonimbus, heavy rain"
    w.vis = 1.5
    w.turb = [0.75, 0.9, 0.8]
    w.shear = [45, 60, 30]
    return w


def _shear(core, r):
    d = r.randrange(0, 360, 10)
    w = core.Wx("bkn28", wind_dir=d, wind_spd=r.randint(12, 20), gust=r.randint(6, 12),
                temp=r.randint(6, 16))
    w.turb = [0.45, 0.35, 0.2]
    w.shear = [r.randint(35, 55), r.randint(20, 35), 10]
    return w


def _rotor(core, r):
    w = core.Wx("cu", wind_dir=r.randrange(0, 360, 10), wind_spd=r.randint(30, 42),
                gust=r.randint(12, 20), temp=r.randint(-4, 10))
    w.turb = [0.8, 0.7, 0.4]
    w.shear = [30, 40, 20]
    return w


def build(key, core, rng):
    """The weather for a named hazard."""
    h = HAZARDS.get(key)
    if not h:
        raise KeyError(f"No such hazard: {key}")
    w = h["build"](core, rng)
    w.extra = ""
    return w


def wants(key):
    """What sort of airport suits this hazard: a hint for the generator."""
    h = HAZARDS.get(key) or {}
    t = h.get("tags", "")
    return {"cold": "ice" in t, "high": "perf" in t, "instrument": "ceiling" in t or "vis" in t,
            "windy": "wind" in t or "turb" in t, "mountains": key == "rotor"}
