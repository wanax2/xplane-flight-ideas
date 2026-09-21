"""
xp_acf.py - read an X-Plane aircraft file (.acf) and turn it into a flight profile.

.acf files are plain text: lines like  "P acf/_Vso 48.000000".  Only a handful of
properties are needed here, and the names differ a little between X-Plane
versions, so everything is matched loosely and every value is sanity-checked.
What comes out is the same kind of dict as the hand-written profiles in
xp_flight_ideas.AIRCRAFT, so the rest of the app doesn't care where it came from.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

KG_LB = 2.20462

FLOAT_WORDS = ("float", "amphib", "seaplane", "beaver", "goose", "icon a5", "widgeon", "albatross")
HELI_WORDS = ("helicopter", "heli", "r22", "r44", "r66", "s-76", "s76", "bell ", "206", "407", "ec13", "as350",
              "h125", "cabri", "sikorsky", "huey", "uh-", "md500", "chinook")
GLIDER_WORDS = ("glider", "sailplane", "ask ", "ask21", "asw", "discus", "ls8", "duo discus", "schleicher", "swift s1")
BUSH_WORDS = ("cub", "husky", "carbon", "savage", "kodiak", "porter", "otter", "maule", "scout", "bushmaster",
              "beaver", "citabria", "decathlon", "champ", "helio")


def parse_acf(path) -> dict:
    """All 'P key value' properties of an .acf file (values as strings)."""
    props = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.startswith("P "):
                    if line.startswith(("PROPERTIES_END", "ACF_END")):
                        break
                    continue
                parts = line[2:].rstrip("\n").split(None, 1)
                if parts:
                    props[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    except OSError:
        return {}
    return props


def _f(props, *patterns, lo=None, hi=None):
    """First numeric property whose key matches one of the regexes and passes the range check."""
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for k, v in props.items():
            if rx.search(k):
                try:
                    x = float(str(v).split()[0])
                except (ValueError, IndexError):
                    continue
                if lo is not None and x < lo:
                    continue
                if hi is not None and x > hi:
                    continue
                return x
    return None


def _s(props, *patterns):
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for k, v in props.items():
            if rx.search(k) and v:
                return str(v).strip()
    return ""


def describe(path, rel=""):
    """Everything worth knowing about one aircraft file."""
    p = parse_acf(path)
    name = _s(p, r"acf/_name$", r"/_name$") or Path(path).stem
    text = f"{rel} {name}".lower()
    d = {
        "name": name,
        "icao": _s(p, r"acf/_ICAO$"),
        "author": _s(p, r"acf/_author$"),
        "vso": _f(p, r"_Vso$", r"_Vso_", lo=15, hi=200),
        "vs": _f(p, r"_Vs$", lo=15, hi=250),
        "vno": _f(p, r"_Vno$", lo=40, hi=500),
        "vne": _f(p, r"_Vne$", lo=50, hi=700),
        "vle": _f(p, r"_Vle$", lo=40, hi=500),
        "engines": int(_f(p, r"_num_engn$", lo=0, hi=12) or 0),
        "tanks": int(_f(p, r"_num_tanks$", lo=0, hi=12) or 0),
        "fuel_kg": _f(p, r"_m_fuel_tot$", r"_m_fuel$", lo=1, hi=200000),
        "empty_kg": _f(p, r"_m_empty$", lo=50, hi=400000),
        "max_kg": _f(p, r"_m_max$", r"_m_displaced$", lo=100, hi=600000),
        "retract": bool(_f(p, r"_gear_retract$", lo=0.5)),
        "cg_z": _f(p, r"_cgZ$", r"_cg_z$", lo=-50, hi=50),
        "cg_fwd": _f(p, r"_cgZ_fwd", r"_cg_fwd", lo=-50, hi=50),
        "cg_aft": _f(p, r"_cgZ_aft", r"_cg_aft", lo=-50, hi=50),
        "press": bool(_f(p, r"_max_press_diff$", lo=0.5)),
        "jet": False, "turbine": False, "heli": False, "glider": False, "float": False,
    }
    etype = _f(p, r"_engn/0/_type$", r"_engn_type", lo=0, hi=12)
    # X-Plane engine types: 0-1 recip, 2 electric, 3 rocket, 4-5 turboprop/free turbine, 6+ jet/turbofan
    if etype is not None:
        d["turbine"] = etype >= 4
        d["jet"] = etype >= 6
    d["heli"] = any(w in text for w in HELI_WORDS) or bool(_f(p, r"_is_hm|_num_rotors|_is_helicopter", lo=0.5))
    d["glider"] = any(w in text for w in GLIDER_WORDS) or d["engines"] == 0
    d["float"] = any(w in text for w in FLOAT_WORDS)
    d["bush"] = any(w in text for w in BUSH_WORDS)
    return d


def profile_from_acf(path, rel="", fallback_name=None) -> dict:
    """A flight profile (same shape as xp_flight_ideas.AIRCRAFT entries) read from the .acf."""
    d = describe(path, rel)
    vso, vno, vne = d["vso"], d["vno"], d["vne"]
    if d["glider"]:
        cruise = 60
    elif vno:
        cruise = vno * 0.88
    elif vne:
        cruise = vne * (0.72 if not d["jet"] else 0.8)
    elif vso:
        cruise = vso * 2.4
    else:
        cruise = 120
    if d["jet"]:
        cruise = max(cruise, 250)
    if d["heli"]:
        cruise = min(cruise or 110, 150)
    cruise = int(max(45, min(520, cruise)))

    if vso:
        min_rwy = int(max(400, round((vso ** 2) * 0.62 + 200, -1)))
    else:
        min_rwy = 2500 if d["jet"] else 1800
    if d["bush"]:
        min_rwy = int(min_rwy * 0.65)
    if d["heli"]:
        min_rwy = 0

    # endurance: fuel mass and a rough specific consumption, else a sensible default
    hours = 4.0
    if d["fuel_kg"] and d["engines"]:
        lb = d["fuel_kg"] * KG_LB
        per_eng = 55 if d["jet"] else 40 if d["turbine"] else 9.5     # lb/hour per engine, cruise-ish, very rough
        scale = max(0.6, cruise / 120)
        hours = lb / max(1.0, per_eng * d["engines"] * scale)
    hours = max(1.5, min(9.0, hours))
    rng = int(max(120, min(4000, cruise * hours * 0.85)))

    surfaces = {"paved"}
    if not d["retract"] and cruise < 200:
        surfaces |= {"grass", "dirt", "gravel"}
    if d["bush"]:
        surfaces |= {"grass", "dirt", "gravel", "snow", "lakebed"}
    ceiling = 31000 if d["jet"] else 28000 if d["turbine"] else 20000 if d["press"] else \
        10000 if d["heli"] else 25000 if d["glider"] else 15000
    xwind = int(max(10, min(35, (vso or 50) * 0.32)))
    return dict(name=d["name"] or (fallback_name or Path(path).stem), cruise=cruise, range=rng, min_rwy=min_rwy,
                surfaces=surfaces, xwind=xwind, ceiling=ceiling,
                night=not d["glider"], ifr=bool(d["retract"] or d["turbine"] or d["jet"] or (vne or 0) > 150),
                water=d["float"], heli=d["heli"], multi=d["engines"] > 1, glider=d["glider"],
                match=[], acf=d)


def summary(prof) -> str:
    d = prof.get("acf") or {}
    bits = [f"{prof['cruise']} kt cruise", f"~{prof['range']} nm", f"min runway {prof['min_rwy']:,} ft"]
    if d.get("engines"):
        bits.append(f"{d['engines']} x " + ("jet" if d.get("jet") else "turbine" if d.get("turbine") else "piston"))
    if d.get("glider"):
        bits.append("glider")
    if d.get("heli"):
        bits.append("helicopter")
    if prof.get("water"):
        bits.append("floats")
    if d.get("vso"):
        bits.append(f"Vso {d['vso']:.0f} kt")
    if d.get("max_kg"):
        bits.append(f"MTOW {d['max_kg'] * KG_LB:,.0f} lb")
    return ", ".join(bits)


def payload_capacity_kg(prof, fuel_fraction=0.7):
    d = prof.get("acf") or {}
    if not (d.get("max_kg") and d.get("empty_kg")):
        return None
    useful = d["max_kg"] - d["empty_kg"]
    return max(0.0, useful - (d.get("fuel_kg") or 0) * fuel_fraction)
