"""
xp_career.py - pilot progression: hours, ratings, badges, and the challenge of the day.

All of it is worked out from the logbook, so nothing extra has to be tracked.
"""
from __future__ import annotations

import hashlib
import time

from xp_wx import CONTINENTS, in_area

# name, hours needed, landings needed, what it unlocks / means
RATINGS = [
    ("Student", 0, 0, "Everyone starts here."),
    ("Private pilot", 5, 20, "Cross-countries and $100 hamburgers."),
    ("Mountain pilot", 15, 60, "High strips, density altitude, valley approaches."),
    ("Bush pilot", 30, 120, "Short unpaved strips and cargo runs."),
    ("Instrument pilot", 50, 200, "Low IFR approaches to minimums."),
    ("Commercial pilot", 100, 400, "Mail runs, ferry flights, paying passengers."),
    ("Airline transport", 250, 800, "Anything, anywhere."),
    ("Legend", 500, 1500, "You should probably go outside."),
]

BADGES = [
    ("First flight", lambda s: s["flights"] >= 1, "Fly and log one flight."),
    ("Greaser", lambda s: (s["best_fpm"] or 999) <= 80, "Touch down at 80 fpm or softer."),
    ("Butter", lambda s: (s["best_fpm"] or 999) <= 40, "Touch down at 40 fpm or softer."),
    ("Perfect approach", lambda s: s["best_landing"] >= 95, "Score 95+ on a landing."),
    ("Ten in the book", lambda s: s["flights"] >= 10, "Log 10 flights."),
    ("Century", lambda s: s["flights"] >= 100, "Log 100 flights."),
    ("Night owl", lambda s: s["night"] >= 3, "Fly three night missions."),
    ("Hard IFR", lambda s: s["ifr"] >= 3, "Fly three low-IFR missions."),
    ("Weather hunter", lambda s: s["realwx"] >= 3, "Fly three live-weather missions."),
    ("Bush rat", lambda s: s["backcountry"] + s["cargo"] >= 5, "Five backcountry or cargo flights."),
    ("Sightseer", lambda s: s["scenic"] >= 5, "Five scenic flights."),
    ("Globetrotter", lambda s: s["continents"] >= 3, "Land on three continents."),
    ("World tour", lambda s: s["continents"] >= 5, "Land on five continents."),
    ("Airport collector", lambda s: s["airports"] >= 50, "Visit 50 different airports."),
    ("Airport hoarder", lambda s: s["airports"] >= 200, "Visit 200 different airports."),
    ("Long haul", lambda s: s["longest_nm"] >= 500, "Fly a 500 nm flight."),
    ("Marathon", lambda s: s["hours"] >= 100, "Log 100 hours."),
    ("Hangar full", lambda s: s["aircraft"] >= 5, "Fly five different aircraft."),
    ("Straight A's", lambda s: s["avg_score"] >= 85 and s["flights"] >= 10, "Average 85+ over 10 flights."),
    ("Postman", lambda s: s["mail"] >= 3, "Three mail runs delivered."),
]


def career(logbook, airports_by_id=None):
    e = logbook.entries
    st = logbook.stats()
    kinds = {}
    for x in e:
        kinds[x.get("kind", "")] = kinds.get(x.get("kind", ""), 0) + 1
    visited = {a for x in e for a in (x.get("flown_to") or x.get("route") or [])}
    conts = set()
    if airports_by_id:
        for i in visited:
            a = airports_by_id.get(i)
            if a:
                for k in CONTINENTS:
                    if k != "Whole world" and in_area(a, k):
                        conts.add(k)
                        break
    best_landing = max((l.get("score", 0) for x in e for l in x.get("landings", [])), default=0)
    s = {"flights": st["flights"], "hours": st["hours"], "nm": st["nm"], "landings": st["landings"],
         "airports": len(visited), "avg_score": st["avg_score"], "best_fpm": st["best_fpm"],
         "aircraft": st["aircraft"], "best_landing": best_landing, "continents": len(conts),
         "longest_nm": max((x.get("distance_nm", 0) for x in e), default=0),
         "night": kinds.get("night", 0), "ifr": kinds.get("ifr", 0), "realwx": kinds.get("realwx", 0),
         "backcountry": kinds.get("backcountry", 0), "cargo": kinds.get("cargo", 0),
         "scenic": kinds.get("scenic", 0) + kinds.get("sightsee", 0), "mail": kinds.get("mail", 0),
         "visited": visited, "continent_names": sorted(conts)}
    rating, nxt = RATINGS[0], None
    for i, (name, h, l, desc) in enumerate(RATINGS):
        if s["hours"] >= h and s["landings"] >= l:
            rating = (name, h, l, desc)
        elif nxt is None:
            nxt = (name, h, l, desc)
    earned = [(n, d) for n, cond, d in BADGES if _safe(cond, s)]
    locked = [(n, d) for n, cond, d in BADGES if not _safe(cond, s)]
    s["rating"], s["next_rating"], s["badges"], s["locked"] = rating, nxt, earned, locked
    if nxt:
        need_h, need_l = max(0.0, nxt[1] - s["hours"]), max(0, nxt[2] - s["landings"])
        s["next_text"] = (f"Next: {nxt[0]} - {need_h:.1f} more hours and {need_l} more landings"
                          if need_h or need_l else f"Next: {nxt[0]}")
    else:
        s["next_text"] = "Top rating reached."
    return s


def _safe(cond, s):
    try:
        return bool(cond(s))
    except Exception:
        return False


def daily_seed(when=None):
    d = time.strftime("%Y-%m-%d", time.localtime(when or time.time()))
    return int(hashlib.sha256(d.encode()).hexdigest()[:8], 16), d


def summary_text(s):
    L = [f"Rating: {s['rating'][0]}  -  {s['rating'][3]}", s["next_text"], "",
         f"{s['flights']} flights, {s['hours']:.1f} hours, {s['nm']:,.0f} nm, {s['landings']} landings",
         f"{s['airports']} airports on {len(s['continent_names']) or '?'} continent(s), "
         f"{s['aircraft']} aircraft, average score {s['avg_score']:.0f}", ""]
    if s["badges"]:
        L.append("Badges earned: " + ", ".join(n for n, _ in s["badges"]))
    if s["locked"]:
        L.append("")
        L.append("Still to earn:")
        L += [f"  {n} - {d}" for n, d in s["locked"][:10]]
    return "\n".join(L)
