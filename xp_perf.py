"""
xp_perf.py - the numbers you'd work out before a flight.

Takeoff and landing distances, density altitude, crosswind components, fuel with
reserves, and weight and balance read from the aircraft file.

IMPORTANT, and the app says so on screen: these are rule-of-thumb estimates built
from the aircraft's stall speed and weights, calibrated against a Cessna 172's
published figures. They are NOT the numbers from your aircraft's flight manual.
Use them the way you'd use a mental rule of thumb - to see whether a strip is
comfortable, marginal or silly - not as performance data.
"""
from __future__ import annotations

import math

KG_LB = 2.20462
LB_KG = 0.453592
GAL_LB = 6.0            # avgas, lb per US gallon
JETA_LB = 6.7

# Cessna 172S at 2,550 lb, sea level, standard day, paved and level:
REF = {"vso": 48.0, "to_roll": 960.0, "to_50": 1685.0, "ldg_roll": 575.0, "ldg_50": 1335.0}


def isa_temp_c(alt_ft):
    return 15.0 - 1.98 * alt_ft / 1000.0


def density_alt(elev_ft, oat_c, altimeter_inhg=29.92):
    """Density altitude - the pressure altitude corrected for temperature."""
    pa = elev_ft + (29.92 - altimeter_inhg) * 1000.0
    return pa + 118.8 * (oat_c - isa_temp_c(pa))


def sigma(da_ft):
    """Density ratio for a density altitude (standard atmosphere)."""
    return max(0.25, (1 - 6.87535e-6 * da_ft) ** 4.256)


def wind_components(runway_hdg, wind_dir, wind_kt):
    """(headwind, crosswind) in knots. Headwind is negative when it's a tailwind."""
    ang = math.radians((wind_dir - runway_hdg + 540) % 360 - 180)
    return wind_kt * math.cos(ang), abs(wind_kt * math.sin(ang))


SURFACE_FACTOR = {"paved": 1.0, "grass": 1.20, "dirt": 1.25, "gravel": 1.15,
                  "snow": 1.35, "lakebed": 1.10, "water": 1.30, "helipad": 1.0}


def takeoff(ac, elev_ft, oat_c, altimeter=29.92, weight_frac=1.0, headwind_kt=0.0,
            surface="paved", slope_pct=0.0, wet=False):
    """Estimated takeoff ground roll and distance over a 50 ft obstacle, in feet."""
    return _run(ac, elev_ft, oat_c, altimeter, weight_frac, headwind_kt, surface, slope_pct, wet,
                REF["to_roll"], REF["to_50"], landing=False)


def landing(ac, elev_ft, oat_c, altimeter=29.92, weight_frac=1.0, headwind_kt=0.0,
            surface="paved", slope_pct=0.0, wet=False):
    return _run(ac, elev_ft, oat_c, altimeter, weight_frac, headwind_kt, surface, slope_pct, wet,
                REF["ldg_roll"], REF["ldg_50"], landing=True)


def _run(ac, elev_ft, oat_c, altimeter, weight_frac, headwind_kt, surface, slope_pct, wet,
         ref_roll, ref_50, landing):
    d = ac.get("acf") or {}
    vso = d.get("vso") or ac.get("vso") or REF["vso"]
    da = density_alt(elev_ft, oat_c, altimeter)
    # distance scales with the square of the speed you need, and with how thin the air is
    wf = max(0.3, weight_frac)
    speed2 = (vso / REF["vso"]) ** 2 * (wf ** (1.6 if landing else 2.0))
    if landing:
        # landing distance tracks air density closely
        dens = (1.0 / sigma(da)) ** 0.85
    else:
        # taking off you lose lift AND engine power: about 8% per 1,000 ft of DENSITY
        # altitude for a normally-aspirated piston (matches the 172 tables), less for a turbine
        per_1000 = 1.05 if (d.get("turbine") or d.get("jet")) else 1.08
        dens = per_1000 ** (da / 1000.0)
    roll, fifty = ref_roll * speed2 * dens, ref_50 * speed2 * dens
    v_ref = vso * (1.3 if landing else 1.2) * math.sqrt(max(0.3, weight_frac))
    hw = max(-0.25 * v_ref, min(0.35 * v_ref, headwind_kt))
    wind = (1 - hw / v_ref) ** 1.85 if hw >= 0 else (1 + abs(hw) / v_ref * 1.6)
    roll *= wind
    fifty *= (1 + (wind - 1) * 0.8)
    f = SURFACE_FACTOR.get(surface, 1.1)
    if landing and surface in ("grass", "dirt", "gravel", "snow"):
        f = 1.0 + (f - 1.0) * 0.6       # soft ground helps you stop
    roll *= f
    fifty *= (1 + (f - 1) * 0.7)
    slope = 1 + (slope_pct / 100.0) * (7.0 if not landing else -5.0)
    roll *= max(0.6, slope)
    fifty *= max(0.7, 1 + (slope - 1) * 0.6)
    if wet:
        roll *= 1.15 if not landing else 1.35
        fifty *= 1.10 if not landing else 1.25
    return {"roll": int(round(roll / 10) * 10), "over50": int(round(fifty / 10) * 10),
            "da": int(round(da / 10) * 10), "vref": round(v_ref), "headwind": round(hw)}


def runway_check(ac, apt, rwy_len_ft, elev_ft, oat_c, altimeter, weight_frac, headwind, surface, wet=False):
    """Is this runway comfortable, tight or too short? Uses a 1.5x safety margin, as most people do."""
    t = takeoff(ac, elev_ft, oat_c, altimeter, weight_frac, headwind, surface, wet=wet)
    l = landing(ac, elev_ft, oat_c, altimeter, weight_frac, headwind, surface, wet=wet)
    need = max(t["over50"], l["over50"])
    ratio = rwy_len_ft / max(1, need)
    if ratio >= 1.8:
        verdict, why = "comfortable", "plenty of room"
    elif ratio >= 1.4:
        verdict, why = "fine", "normal margins"
    elif ratio >= 1.05:
        verdict, why = "tight", "little margin - be on speed and on the numbers"
    else:
        verdict, why = "too short", "the estimate says you don't have the room"
    return {"takeoff": t, "landing": l, "need": need, "have": int(rwy_len_ft),
            "verdict": verdict, "why": why, "ratio": round(ratio, 2)}


# ==========================================================================
# Fuel
# ==========================================================================
def fuel_plan(ac, distance_nm, groundspeed_kt=None, night=False, ifr=False, alternate_nm=0.0,
              taxi_min=10, gph=None):
    """Gallons and pounds needed: trip + taxi + alternate + reserve."""
    from xp_export import fuel_gph
    gph = gph or fuel_gph(ac)
    gs = groundspeed_kt or ac["cruise"]
    trip_h = distance_nm / max(30.0, gs)
    alt_h = alternate_nm / max(30.0, gs) if alternate_nm else 0.0
    res_min = 45 if (night or ifr) else 30
    taxi = gph * taxi_min / 60.0
    trip, alt, res = gph * trip_h, gph * alt_h, gph * res_min / 60.0
    total = taxi + trip + alt + res
    d = ac.get("acf") or {}
    per_gal = JETA_LB if (d.get("jet") or d.get("turbine")) else GAL_LB
    cap_gal = (d.get("fuel_kg") * KG_LB / per_gal) if d.get("fuel_kg") else None
    return {"gph": round(gph, 1), "trip_h": trip_h, "taxi": taxi, "trip": trip, "alternate": alt,
            "reserve": res, "reserve_min": res_min, "total": total, "lb": total * per_gal,
            "kg": total * per_gal * LB_KG, "capacity_gal": cap_gal,
            "fits": (cap_gal is None or total <= cap_gal),
            "endurance_h": (cap_gal / gph) if cap_gal else None, "per_gal_lb": per_gal}


# ==========================================================================
# Weight and balance
# ==========================================================================
def weight_balance(ac, fuel_gal=None, payload_kg=0.0, fuel_frac=0.7):
    """Weights from the .acf, and the CG if the file gives limits."""
    d = ac.get("acf") or {}
    empty = d.get("empty_kg")
    mtow = d.get("max_kg")
    fuel_cap_kg = d.get("fuel_kg")
    per_gal = JETA_LB if (d.get("jet") or d.get("turbine")) else GAL_LB
    if fuel_gal is None:
        fuel_kg = (fuel_cap_kg or 0) * fuel_frac
    else:
        fuel_kg = fuel_gal * per_gal * LB_KG
    out = {"empty_kg": empty, "fuel_kg": fuel_kg, "payload_kg": max(0.0, payload_kg),
           "mtow_kg": mtow, "fuel_cap_kg": fuel_cap_kg, "cg": None, "cg_fwd": None, "cg_aft": None,
           "cg_ok": None, "per_gal_lb": per_gal}
    if empty is None or mtow is None:
        out["total_kg"] = None
        out["over_kg"] = None
        return out
    total = empty + fuel_kg + max(0.0, payload_kg)
    out["total_kg"] = total
    out["over_kg"] = total - mtow
    out["useful_kg"] = mtow - empty
    cg, fwd, aft = d.get("cg_z"), d.get("cg_fwd"), d.get("cg_aft")
    if cg is not None and fwd is not None and aft is not None and aft != fwd:
        # the .acf gives arms in feet behind the datum; shift with load, roughly
        shift = 0.0
        if out["useful_kg"]:
            shift = (fuel_kg * 0.15 + payload_kg * 0.55) / out["useful_kg"] * (aft - fwd)
        pos = cg + shift
        out.update(cg=pos, cg_fwd=fwd, cg_aft=aft, cg_ok=fwd <= pos <= aft,
                   cg_pct=100.0 * (pos - fwd) / (aft - fwd))
    return out


def summary_lines(ac, apt, wx, core, weight_frac=1.0, rwy=None, wet=False):
    """A few plain-English lines for the briefing or the kneeboard."""
    oat = wx.temp
    da = density_alt(apt["elev"], oat, wx.altimeter)
    lines = [f"Density altitude at {apt['id']}: {da:,.0f} ft "
             f"({'above' if da > apt['elev'] else 'below'} the field's {apt['elev']:,} ft)."]
    ends = core.runway_ends(apt)
    if ends:
        best = None
        for end, hdg, r in ends:
            hw, xw = wind_components(hdg, wx.wind_dir, wx.wind_spd)
            if best is None or hw > best[1]:
                best = (end, hw, xw, r)
        end, hw, xw, r = best
        lines.append(f"Runway {end}: {hw:+.0f} kt headwind, {xw:.0f} kt crosswind"
                     + (f" (gusting, add {wx.gust} kt)" if wx.gust else "") + ".")
        chk = runway_check(ac, apt, r["len"], apt["elev"], oat, wx.altimeter, weight_frac, hw,
                           r["s"], wet)
        lines.append(f"Estimated takeoff over 50 ft {chk['takeoff']['over50']:,} ft, "
                     f"landing {chk['landing']['over50']:,} ft, runway {r['len']:,} ft - "
                     f"{chk['verdict']}, {chk['why']}.")
    return lines
