"""
xp_departure.py - the numbers for getting out, and what makes a field hard to leave.

The approach side of this app asks "will you see the runway". The departure side
asks the other question: will you out-climb what is in front of you. At a sea-level
field with a mile of concrete the answer is always yes and nobody thinks about it.
At 9,900 ft on a 4,800 ft strip in a bowl of granite on a warm afternoon it is the
whole flight, and it is decided before you release the brakes.

Everything here is an estimate built from the same rules of thumb as xp_perf, not
a flight manual and not the chart. The one hard number borrowed from the real world
is 200 ft/nm - the standard climb gradient a US departure procedure assumes unless
it prints a steeper one. If you can't make that, you can't fly the published DP.
"""
from __future__ import annotations

import math

#: what a standard instrument departure assumes you can do, in feet per nautical mile
STANDARD_GRADIENT = 200.0
#: and the margin a sensible person wants on top of it
WANT_MARGIN = 1.25

#: sea-level rate of climb, in fpm, when the aircraft file doesn't tell us
ROC_BY_CRUISE = ((95, 600), (120, 720), (150, 900), (200, 1200), (300, 2000), (10_000, 3000))


def roc_sea_level(ac):
    """Best rate of climb at sea level, from the aircraft if it says, else by class."""
    d = (ac.get("acf") or {}) if isinstance(ac, dict) else {}
    for key in ("roc", "climb_fpm", "vy_fpm"):
        v = d.get(key)
        if v and 100 <= float(v) <= 6000:
            return float(v)
    cruise = float(ac.get("cruise") or 110)
    for upto, fpm in ROC_BY_CRUISE:
        if cruise <= upto:
            return float(fpm)
    return 800.0


def climb_rate(ac, density_alt_ft):
    """Rate of climb at a density altitude, straight-lined to zero at the ceiling.

    Real aeroplanes lose climb very nearly linearly with density altitude, which is
    why the service ceiling is where it is. Below 100 fpm we call it nothing, because
    a number like "40 fpm available" is not a climb, it is a hazard.
    """
    ceiling = float(ac.get("ceiling") or 13000)
    sl = roc_sea_level(ac)
    left = 1.0 - (max(0.0, float(density_alt_ft)) / max(1000.0, ceiling))
    fpm = sl * max(0.0, left)
    return 0.0 if fpm < 100 else round(fpm)


def gradient(fpm, groundspeed_kt):
    """Feet per nautical mile, from a rate of climb and a groundspeed."""
    gs = max(20.0, float(groundspeed_kt or 0))
    return (float(fpm) * 60.0) / gs


def climb_speed(ac):
    """Vy, near enough: a bit under three-quarters of cruise for most light types."""
    return max(45.0, float(ac.get("cruise") or 110) * 0.72)


def needed_gradient(obstacle_ft_above_field, distance_nm, cross_by_ft=200.0):
    """The gradient that clears something that high, that far out, by that much."""
    d = max(0.2, float(distance_nm))
    return (float(obstacle_ft_above_field) + float(cross_by_ft)) / d


def assess(ac, apt, opt, wx, core, high_ft=None, weight_frac=1.0):
    """The climb numbers for one runway on one day.

    high_ft is the highest ground known within a few miles, if the caller has it.
    """
    import xp_perf
    elev = float(apt.get("elev") or 0)
    temp = float(getattr(wx, "temp", 15) or 15)
    altim = float(getattr(wx, "altimeter", 29.92) or 29.92)
    da = xp_perf.density_alt(elev, temp, altim)
    fpm = climb_rate(ac, da)
    vy = climb_speed(ac)
    head = float(opt.get("head") or 0) if opt else 0.0
    gs = max(25.0, vy - head)             # into wind you climb more steeply over the ground
    grad = gradient(fpm, gs) if fpm else 0.0
    out = {"da": int(round(da)), "fpm": int(fpm), "vy": int(round(vy)), "gs": int(round(gs)),
           "gradient": int(round(grad)), "standard": STANDARD_GRADIENT,
           "can_standard": bool(grad >= STANDARD_GRADIENT),
           "comfortable": bool(grad >= STANDARD_GRADIENT * WANT_MARGIN)}
    if high_ft is not None and high_ft > elev + 300:
        rise = float(high_ft) - elev
        out["terrain_ft"] = int(round(rise))
        out["terrain_top"] = int(round(float(high_ft)))
        # how far you'd have to be from it to clear it at the gradient you actually have
        out["terrain_nm_needed"] = round(needed_gradient(rise, 1.0) / max(1.0, grad), 1) if grad else None
    if opt:
        try:
            chk = xp_perf.runway_check(ac, apt, opt["len"], elev, temp, altim, weight_frac,
                                       head, opt.get("surface") or "paved")
            out["runway"] = chk
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------
# What makes a field interesting to leave
# --------------------------------------------------------------------------
def interest(apt, opts, ac, wx, core, high_ft=None, weight_frac=1.0):
    """(score, [reasons]) - how much the departure is the hard part here.

    Scored the way a pilot would look at it on the chart the night before: how much
    runway there is against how much you need, how thin the air is, what the ground
    does off the end, and whether you get a choice of direction.
    """
    if not opts:
        return 0.0, []
    best = opts[0]
    got = assess(ac, apt, best, wx, core, high_ft, weight_frac)
    score, why = 0.0, []
    chk = got.get("runway")
    if chk:
        ratio = chk["ratio"]
        if ratio < 1.05:
            score += 5.0
            why.append(f"the runway is shorter than the book wants ({chk['have']:,} ft "
                       f"against {chk['need']:,} needed)")
        elif ratio < 1.4:
            score += 3.0
            why.append(f"{chk['have']:,} ft is tight here - you need about {chk['need']:,}")
        elif ratio < 1.8:
            score += 1.0
            why.append(f"{chk['have']:,} ft, with normal margins and not much spare")
    da = got["da"]
    if da >= 9000:
        score += 4.0
        why.append(f"density altitude {da:,} ft - the air is barely holding you up")
    elif da >= 7000:
        score += 2.5
        why.append(f"density altitude {da:,} ft")
    elif da >= 5000:
        score += 1.2
        why.append(f"density altitude {da:,} ft")
    if not got["fpm"]:
        score += 5.0
        why.append("on paper this aeroplane will not climb at all today")
    elif not got["can_standard"]:
        score += 3.5
        why.append(f"{got['gradient']} ft/nm available, under the {int(STANDARD_GRADIENT)} "
                   f"a published departure assumes")
    elif not got["comfortable"]:
        score += 1.5
        why.append(f"{got['gradient']} ft/nm available - over the standard, but not by much")
    if got.get("terrain_ft"):
        rise = got["terrain_ft"]
        if rise >= 4000:
            score += 3.5
        elif rise >= 2000:
            score += 2.0
        else:
            score += 0.8
        why.append(f"ground {rise:,} ft above the field within a few miles")
    surf = (best.get("surface") or "paved").lower()
    if surf in ("grass", "dirt", "gravel", "snow", "sand"):
        score += 1.0
        why.append(f"{surf} surface")
    if surf == "water":
        score += 1.5
        why.append("water runway")
    usable = [o for o in opts if (o.get("len") or 0) >= 1 and o.get("surface") != "helipad"]
    if len(usable) <= 1:
        score += 1.0
        why.append("one runway, one direction - no choosing a better one")
    if best.get("head", 0) < -3:
        score += 1.5
        why.append(f"{abs(best['head']):.0f} kt of tailwind on the best runway available")
    return round(score, 1), why


def fms(apt, route, pos, top_ft=None):
    """An .fms 1100 plan that flies a departure's waypoints out of this airport.

    The waypoints go in as type 28 (plain lat/lon) rather than by name, because the
    GPS only knows the names in its own cycle and we already know where they are.
    Anything we have no position for is dropped - silently in the file, loudly in
    the briefing.
    """
    elev = float(apt.get("elev") or 0)
    top = float(top_ft or (elev + 6000))
    rows = [f"1 {apt['id']} ADEP {elev:.6f} {apt['lat']:.6f} {apt['lon']:.6f}"]
    got = [w for w in route if w in pos]
    for i, name in enumerate(got):
        la, lo = pos[name]
        rows.append(f"28 {name} {'ADES' if i == len(got) - 1 else 'DRCT'} "
                    f"{top:.6f} {la:.6f} {lo:.6f}")
    head = ["I", "1100 Version", "CYCLE 2409", f"ADEP {apt['id']}",
            f"ADES {got[-1] if got else apt['id']}", f"NUMENR {len(rows)}"]
    return "\n".join(head + rows) + "\n", got


def one_liner(score):
    if score >= 9:
        return "This one is the flight."
    if score >= 6:
        return "Getting out is the hard part here."
    if score >= 3:
        return "Worth thinking about before you push the throttle up."
    if score >= 1:
        return "Nothing difficult, but not nothing."
    return "Straightforward departure."


# --------------------------------------------------------------------------
# The briefing
# --------------------------------------------------------------------------
def brief(apt, opt, ac, wx, core, got=None, high_ft=None, sids=None, why=None, score=None):
    """The lines shown in the departure window."""
    got = got or assess(ac, apt, opt, wx, core, high_ft)
    elev = int(apt.get("elev") or 0)
    lines = []
    name = apt.get("name", "") or apt.get("id", "")
    lines.append(f"{apt.get('id', '')}  {name} - field elevation {elev:,} ft.")
    if opt:
        bits = [f"Runway {opt['end']}", f"{opt['len']:,} ft", (opt.get('surface') or 'paved')]
        if opt.get("lit"):
            bits.append("lit")
        lines.append(", ".join(bits) + ".")
        head = opt.get("head") or 0
        if abs(head) >= 1:
            lines.append(f"Wind on it: {head:+.0f} kt down the runway"
                         + (f", {opt['cross']:.0f} kt across" if opt.get("cross", 0) >= 1 else "") + ".")
        else:
            lines.append("Wind on it: calm.")
    lines.append("")
    lines.append(f"Density altitude {got['da']:,} ft. The aeroplane thinks it is starting "
                 f"{max(0, got['da'] - elev):,} ft higher than it is.")
    if not got["fpm"]:
        lines.append("Estimated climb: none. At this density altitude this aeroplane is at or "
                     "above its ceiling sitting still. Wait for the cool of the morning, take "
                     "fuel out, or fly something else.")
    else:
        lines.append(f"Estimated climb {got['fpm']:,} fpm at {got['vy']} kt, which over the ground "
                     f"at {got['gs']} kt is {got['gradient']} ft per nautical mile.")
        if got["can_standard"]:
            lines.append(f"That clears the {int(STANDARD_GRADIENT)} ft/nm a published departure "
                         f"assumes" + ("." if got["comfortable"] else ", but not by much."))
        else:
            lines.append(f"That is UNDER the {int(STANDARD_GRADIENT)} ft/nm a published departure "
                         f"assumes. You cannot fly a standard DP out of here today.")
    if got.get("terrain_ft"):
        lines.append(f"Highest ground known within a few miles: {got['terrain_top']:,} ft, "
                     f"{got['terrain_ft']:,} ft above the field.")
        need = needed_gradient(got["terrain_ft"], 5.0)
        lines.append(f"To clear that by 200 ft five miles out you want {need:.0f} ft/nm; "
                     f"you have {got['gradient']}.")
    chk = got.get("runway")
    if chk:
        t = chk["takeoff"]
        lines.append("")
        lines.append(f"Takeoff roll about {t['roll']:,} ft, {t['over50']:,} ft to clear 50 ft, "
                     f"and you have {chk['have']:,} ft - {chk['verdict']} ({chk['why']}).")
    if sids:
        lines.append("")
        lines.append("Published departures off this runway, from your own nav data: "
                     + ", ".join(sids[:8]) + ("..." if len(sids) > 8 else "") + ".")
    if why:
        lines.append("")
        lines.append((one_liner(score or 0) + " ") if score is not None else "")
        for w in why:
            lines.append("  - " + w)
    lines.append("")
    lines.append("These are rules of thumb from your aircraft's own numbers and today's air, "
                 "not the flight manual and not the departure plate. Fly the plate.")
    return [l for l in lines if l is not None]
