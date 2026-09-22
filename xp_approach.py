"""
xp_approach.py - setting up an approach, and knowing what you're being dropped into.

X-Plane will happily put you on final if you ask it to. What it won't tell you is
which runway you should have picked, how high you'll be when the sim unpauses, how
fast you'll need to come down, or whether the runway is long enough for what you're
flying. This works all that out first, so the moment the screen appears you already
know what you're looking at.

Everything in here is geometry and rules of thumb: a 3-degree path, 50 ft over the
threshold, 1.3 times the stall speed. The minimums are the *typical* ones for the
kind of approach, not the numbers off the real chart - if you're flying a real
procedure, use the real plate.
"""
from __future__ import annotations

import math

GLIDE = 3.0          # degrees - what almost every ILS and PAPI is set to
TCH = 50.0           # ft over the threshold at the aiming point
FT_PER_NM = 6076.12


# ==========================================================================
# The geometry of a straight-in approach
# ==========================================================================
def height_at(dist_nm, angle=GLIDE, tch=TCH):
    """Height above the runway, on the path, this far out. About 320 ft per mile."""
    return tch + dist_nm * FT_PER_NM * math.tan(math.radians(angle))


def dist_for_height(height_ft, angle=GLIDE, tch=TCH):
    """How far out you are when you're this high on the path."""
    h = max(0.0, height_ft - tch)
    return h / (FT_PER_NM * math.tan(math.radians(angle)))


def descent_fpm(gs_kt, angle=GLIDE):
    """Rate of descent needed to stay on the path at this groundspeed."""
    return gs_kt * FT_PER_NM * math.tan(math.radians(angle)) / 60.0


def vref(ac):
    """Approach speed: 1.3 Vso where we know it, otherwise a guess off the cruise."""
    vso = (ac.get("acf") or {}).get("vso")
    if vso:
        return 1.3 * float(vso)
    if ac.get("heli"):
        return 60.0
    return max(45.0, ac["cruise"] * 0.55)


def time_to_touchdown(dist_nm, gs_kt):
    return dist_nm / max(20.0, gs_kt) * 60.0        # minutes


# ==========================================================================
# Which runway?
# ==========================================================================
def runway_options(apt, wx, core):
    """Every runway end, with the wind on it and whether it has a localizer.

    Sorted best-first: instrument runways with a headwind come out on top.
    """
    ils = set(apt.get("ils") or ())
    info = apt.get("ils_info") or {}
    out = []
    wdir = getattr(wx, "wind_dir", 0) or 0
    wspd = getattr(wx, "wind_spd", 0) or 0
    for end, hdg, r in core.runway_ends(apt):
        ang = math.radians((wdir - hdg + 540) % 360 - 180)
        head = wspd * math.cos(ang)
        cross = abs(wspd * math.sin(ang))
        has_ils = end in ils
        out.append({"end": end, "hdg": hdg, "len": r["len"], "surface": r["s"], "lit": r.get("lit"),
                    "head": head, "cross": cross, "ils": has_ils,
                    "freq": (info.get(end) or {}).get("freq"),
                    "course": (info.get(end) or {}).get("crs"),
                    "ident": (info.get(end) or {}).get("ident"),
                    "kind": (info.get(end) or {}).get("name") or ("ILS" if has_ils else "")})
    out.sort(key=lambda o: (-(1 if o["ils"] else 0), -o["head"], -o["len"]))
    return out


def pick_runway(apt, wx, core, prefer_ils=True):
    """The runway we'd choose for you, and one line on why."""
    opts = runway_options(apt, wx, core)
    if not opts:
        return None, "This airport has no runway in your scenery."
    if not prefer_ils:
        opts = sorted(opts, key=lambda o: (-o["head"], -o["len"]))
    o = opts[0]
    why = []
    if o["ils"]:
        why.append("it's the instrument runway")
    if o["head"] > 1:
        why.append(f"{o['head']:.0f} kt of headwind")
    elif o["head"] < -1:
        why.append(f"{abs(o['head']):.0f} kt of TAILWIND - nothing better available")
    else:
        why.append("the wind doesn't care")
    if o["cross"] >= 8:
        why.append(f"{o['cross']:.0f} kt across")
    return o, "Runway " + o["end"] + ": " + ", ".join(why) + "."


# ==========================================================================
# Minimums - the usual ones for the kind of approach, not the real plate
# ==========================================================================
def _cap(t):
    return t[:1].upper() + t[1:] if t else t


def minimums(opt, elev_ft):
    """(height above the runway, visibility in statute miles, what to call it)."""
    if not opt:
        return 600, 2.0, "no approach"
    if opt["ils"] and "cat-ii" in (opt["kind"] or "").lower():
        return 100, 0.25, "ILS CAT II"
    if opt["ils"] and "cat-iii" in (opt["kind"] or "").lower():
        return 50, 0.15, "ILS CAT III"
    if opt["ils"]:
        return 200, 0.5, "ILS CAT I"
    if opt["lit"]:
        return 400, 1.0, "a non-precision approach"
    return 600, 1.0, "a circling approach"


def will_you_see_it(opt, elev_ft, wx):
    """Can you get in, in this weather? (verdict, sentence)"""
    dh, minvis, name = minimums(opt, elev_ft)
    ceil = getattr(wx, "ceiling", None)
    vis = getattr(wx, "vis", None)
    bits = []
    ok = True
    if ceil is not None:
        if ceil < dh:
            ok = False
            bits.append(f"the ceiling is {ceil:,.0f} ft and {name} gets you down to {dh} ft - "
                        f"you will not see the runway")
        elif ceil < dh + 300:
            bits.append(f"the ceiling is {ceil:,.0f} ft against a {dh} ft minimum - it'll be close")
        else:
            bits.append(f"you should break out around {ceil:,.0f} ft, well above the {dh} ft minimum")
    if vis is not None:
        if vis < minvis:
            ok = False
            bits.append(f"visibility {vis:g} SM is below the {minvis:g} SM you'd need")
        elif vis < minvis * 2:
            bits.append(f"visibility {vis:g} SM is legal but tight")
    if not bits:
        return True, f"{_cap(name)} - the weather isn't the problem today."
    txt = "; ".join(bits) + "."
    return ok, ("Go-around likely: " + txt) if not ok else _cap(txt)


# ==========================================================================
# The briefing
# ==========================================================================
def brief(apt, opt, dist_nm, ac, wx, core, perf=None):
    """The lines to show next to the distance box."""
    if not opt:
        return ["Pick a runway first."]
    elev = apt["elev"]
    h = height_at(dist_nm)
    va = vref(ac)
    gs = max(25.0, va - opt["head"])          # headwind slows the groundspeed
    fpm = descent_fpm(gs)
    mins = minimums(opt, elev)
    L = []
    L.append(f"You appear {dist_nm:g} nm out on the extended centreline of runway {opt['end']}, "
             f"about {h:,.0f} ft above the runway ({elev + h:,.0f} ft on the altimeter).")
    L.append(f"On the path you want {fpm:,.0f} fpm at {va:.0f} kt indicated "
             f"({gs:.0f} kt over the ground), and you have "
             f"{time_to_touchdown(dist_nm, gs):.1f} minutes before the threshold.")
    if opt["head"] >= 1:
        wind = f"{opt['head']:.0f} kt headwind"
    elif opt["head"] <= -1:
        wind = f"{abs(opt['head']):.0f} kt TAILWIND"
    else:
        wind = "no useful headwind"
    L.append(f"Wind on the runway: {wind}, {opt['cross']:.0f} kt across"
             + (f" - that's past the {ac['xwind']} kt you normally accept."
                if opt["cross"] > ac.get("xwind", 99) else "."))
    if opt["ils"]:
        f = f"{opt['freq']:.2f}" if opt.get("freq") else "see the chart"
        crs = f"{opt['course']:.0f}°" if opt.get("course") else f"{opt['hdg']:.0f}°"
        L.append(f"Localizer {opt.get('ident') or ''} on {f}, course {crs}. "
                 f"{mins[2]}: down to {mins[0]} ft above the runway, {mins[1]:g} SM needed.")
    else:
        L.append(f"No localizer on this end, so it's {mins[2]}: {mins[0]} ft and {mins[1]:g} SM "
                 f"is about as low as you should take it.")
    L.append(f"Runway {opt['end']} is {opt['len']:,} ft of {opt['surface']}"
             + (", lit." if opt["lit"] else ", unlit."))
    if mins[0] < 200 and opt["ils"]:
        L.append(f"The scenery calls this {mins[2]}, but flying it that low needs equipment, "
                 f"a crew and training your aeroplane almost certainly doesn't have. "
                 f"Treat 200 ft as your floor.")
    elif not ac.get("ifr", True):
        L.append("This aeroplane isn't set up for instrument flying, so treat the whole thing as "
                 "a visual approach - stay out of cloud and keep the runway in sight.")
    if perf:
        L.append(perf)
    ok, why = will_you_see_it(opt, elev, wx)
    L.append(why)
    return L


def intercept_hint(dist_nm):
    """What kind of approach this distance actually is."""
    if dist_nm <= 1.5:
        return "Very short final - you are already committed. Good for practising the flare."
    if dist_nm <= 4:
        return "Short final: configured, on speed, runway in sight. The landing, and nothing else."
    if dist_nm <= 8:
        return "Final approach fix territory - the whole approach from glideslope intercept."
    if dist_nm <= 13:
        return "Intermediate segment: you'll have time to configure, slow down and get stable."
    return "A long way out - more of an arrival than an approach. Expect to be high at first."
