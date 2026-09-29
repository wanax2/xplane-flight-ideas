"""
xp_coach.py - reads your logbook back to you.

The app has been recording every landing you make: how fast you were coming down,
how far past the threshold you touched, how far off the centreline, what the
weather was, whether it was night, what kind of flight it was. Until now nothing
ever read any of it.

This does two things with it.

`findings` looks for the patterns you wouldn't notice yourself - the conditions
you're measurably worse in, the places you keep going back to, the kinds of flying
you've quietly stopped doing - and for each one describes the flight that would
fix it, in a form the app can build.

`currency` does the rolling counts a real pilot has to keep: landings in ninety
days, night landings, instrument approaches in six months. It is modelled on the
FAA's rules because they are the ones most people know, and it is a simulator
scoreboard, not a legal record - nothing you do here counts towards anything.

Everything is stated with the numbers behind it, so you can disagree with it.
"""
from __future__ import annotations

import time

DAY = 86400.0

# Rolling currency, FAA-shaped. (key, name, window in days, how many, what counts)
CURRENCY = [
    ("landings", "Three landings in 90 days", 90, 3,
     "Any three landings. Without them you shouldn't be carrying passengers."),
    ("night", "Three night landings in 90 days", 90, 3,
     "Landings between sunset and sunrise, to a full stop."),
    ("approaches", "Six instrument approaches in 6 months", 180, 6,
     "Approaches flown in instrument conditions, plus holding and tracking."),
    ("flight", "Flown at all in 30 days", 30, 1,
     "Not a rule, just a habit worth keeping."),
]


def _lands(entries):
    for e in entries:
        for l in e.get("landings") or ():
            yield e, l


def _recent(entries, days, now=None):
    now = now or time.time()
    return [e for e in entries if now - e.get("time", 0) <= days * DAY]


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ==========================================================================
# Currency
# ==========================================================================
def currency(entries, now=None):
    """Rolling counts, and what each one still needs."""
    now = now or time.time()
    out = []
    for key, name, days, need, what in CURRENCY:
        rec = _recent(entries, days, now)
        if key == "landings":
            have = sum(len(e.get("landings") or ()) for e in rec)
        elif key == "night":
            have = sum(len(e.get("landings") or ()) for e in rec if e.get("night"))
        elif key == "approaches":
            have = sum(1 for e in rec if e.get("ifr") or (e.get("rules") in ("IFR", "LIFR")))
        else:
            have = len(rec)
        newest = max((e.get("time", 0) for e in rec), default=None)
        out.append({"key": key, "name": name, "need": need, "have": have, "days": days,
                    "ok": have >= need, "short": max(0, need - have), "what": what,
                    "last": newest, "since": (now - newest) / DAY if newest else None})
    return out


def currency_lines(entries, now=None):
    L = []
    for c in currency(entries, now):
        mark = "ok  " if c["ok"] else "DUE "
        last = f", last one {c['since']:.0f} days ago" if c["since"] is not None else ", never"
        L.append(f"{mark}{c['name']}: {c['have']} of {c['need']}{last}")
    return L


# ==========================================================================
# Findings
# ==========================================================================
def _finding(key, title, detail, fix, severity=1):
    """fix: what the app should build. kind/conditions the GUI understands."""
    return {"key": key, "title": title, "detail": detail, "fix": fix, "severity": severity}


def findings(entries, now=None, missions=None):
    """What the logbook says you should go and practise. Strongest first."""
    now = now or time.time()
    out = []
    if len(entries) < 3:
        return [_finding("start", "Not enough in the logbook yet",
                         f"You have {len(entries)} flight(s) recorded. Fly a few with scoring switched "
                         f"on and this fills up - it needs a handful before any of it means anything.",
                         {"mission": "xc"}, 0)]

    pairs = list(_lands(entries))
    scores = [(e, l) for e, l in pairs if l.get("score") is not None]

    # --- wind ---------------------------------------------------------------
    windy = [l["score"] for e, l in scores if (e.get("wind_kt") or 0) >= 14]
    calm = [l["score"] for e, l in scores if (e.get("wind_kt") or 0) <= 6]
    if len(windy) >= 3 and len(calm) >= 3:
        a, b = _avg(windy), _avg(calm)
        if a is not None and b is not None and b - a >= 8:
            out.append(_finding(
                "wind", "Your landings fall apart in wind",
                f"In 14 kt or more your landings average {a:.0f}. In 6 kt or less they average "
                f"{b:.0f} - {b - a:.0f} points better. That gap is technique, not luck: "
                f"{len(windy)} windy landings against {len(calm)} calm ones.",
                {"hazard": "xwind"}, 3))

    # --- what the low scores have in common ---------------------------------
    if len(scores) >= 6:
        rate = [l for e, l in scores if l.get("rate_score") is not None]
        spot = [l for e, l in scores if l.get("spot_score") is not None]
        centre = [l for e, l in scores if l.get("centre_score") is not None]
        parts = [("rate_score", "how hard you arrive", _avg([l["rate_score"] for l in rate]), "rate"),
                 ("spot_score", "where you touch down", _avg([l["spot_score"] for l in spot]), "spot"),
                 ("centre_score", "keeping the centreline", _avg([l["centre_score"] for l in centre]), "centre")]
        parts = [p for p in parts if p[2] is not None]
        if len(parts) == 3:
            worst = min(parts, key=lambda p: p[2])
            best = max(parts, key=lambda p: p[2])
            if best[2] - worst[2] >= 12:
                fix = {"spot": {"mission": "shortfield"}, "centre": {"hazard": "xwind"},
                       "rate": {"approach": True}}[worst[3]]
                out.append(_finding(
                    "weakest", f"The weak part of your landing is {worst[1]}",
                    f"Averaged over {len(scores)} landings: {parts[0][1]} {parts[0][2]:.0f}, "
                    f"{parts[1][1]} {parts[1][2]:.0f}, {parts[2][1]} {parts[2][2]:.0f}. "
                    f"The other two are carrying you.",
                    fix, 3))

    # --- are you getting better or worse? -----------------------------------
    if len(scores) >= 10:
        recent = [l["score"] for e, l in scores[:5]]
        older = [l["score"] for e, l in scores[5:15]]
        r, o = _avg(recent), _avg(older)
        if r is not None and o is not None and o - r >= 7:
            out.append(_finding(
                "slipping", "You were landing better a while ago",
                f"Your last five landings average {r:.0f}. The ten before them averaged {o:.0f}. "
                f"Could be harder conditions, could be habits - either way it's worth a few circuits.",
                {"mission": "circuits"}, 2))

    # --- night ---------------------------------------------------------------
    night = [e for e in entries if e.get("night")]
    if not night and len(entries) >= 8:
        out.append(_finding(
            "night", "You have never flown at night",
            f"Not once in {len(entries)} flights. Night flying is a different skill - "
            f"no horizon, different illusions on the approach, and you find out how well you "
            f"actually know the cockpit.",
            {"mission": "night"}, 2))
    elif night:
        last = max(e.get("time", 0) for e in night)
        days = (now - last) / DAY
        if days > 60:
            out.append(_finding(
                "night_stale", "It has been a while since you flew at night",
                f"{days:.0f} days. You've flown {len(night)} night flights in total.",
                {"mission": "night"}, 1))

    # --- instrument ----------------------------------------------------------
    ifr = [e for e in entries if e.get("ifr") or e.get("rules") in ("IFR", "LIFR")]
    if len(entries) >= 8 and len(ifr) <= 1:
        out.append(_finding(
            "ifr", "Almost everything you fly is in good weather",
            f"{len(ifr)} of {len(entries)} flights were in instrument conditions. The weather "
            f"you avoid is the weather that catches people out.",
            {"hazard": "lowifr"}, 2))

    # --- the same airports over and over -------------------------------------
    visits = {}
    for e in entries:
        for a in e.get("route") or ():
            visits[a] = visits.get(a, 0) + 1
    if visits:
        top, n = max(visits.items(), key=lambda kv: kv[1])
        if n >= 6 and n >= 0.35 * len(entries):
            out.append(_finding(
                "rut", f"You keep going back to {top}",
                f"{top} appears in {n} of your {len(entries)} flights. Nothing wrong with a home "
                f"field, but you've {len(visits)} airports in the logbook and a whole planet outside it.",
                {"anywhere": True}, 2))

    # --- a familiar airport you've never seen in the dark ---------------------
    if visits:
        night_apts = {a for e in night for a in e.get("route") or ()}
        for apt, n in sorted(visits.items(), key=lambda kv: -kv[1])[:3]:
            if n >= 4 and apt not in night_apts:
                out.append(_finding(
                    "night_here", f"You have been to {apt} {n} times, never at night",
                    f"You know the place in daylight. It is a different airport with the lights on.",
                    {"mission": "night", "airport": apt}, 1))
                break

    # --- did you actually get there? ----------------------------------------
    done = [e for e in entries if e.get("landings")]
    missed = [e for e in done if e.get("arrived") is False]
    if len(done) >= 6 and len(missed) >= max(2, 0.25 * len(done)):
        out.append(_finding(
            "diverts", "You often end up somewhere other than the plan",
            f"{len(missed)} of your {len(done)} flights finished away from the planned destination. "
            f"That is sometimes good judgement. It is worth knowing which.",
            {"mission": "xc"}, 1))

    # --- kinds of flying never tried ----------------------------------------
    if missions:
        flown = {e.get("kind") for e in entries if e.get("kind")}
        never = [k for k in missions if k not in flown]
        if len(entries) >= 10 and len(never) >= 5:
            names = ", ".join(missions[k] for k in never[:4])
            out.append(_finding(
                "unflown", f"{len(never)} kinds of flight you have never tried",
                f"Including: {names}. The generator has been offering them and you have been "
                f"picking the same few.",
                {"mission": never[0]}, 1))

    # --- currency that has lapsed --------------------------------------------
    for c in currency(entries, now):
        if not c["ok"] and c["key"] != "flight":
            out.append(_finding(
                "cur_" + c["key"], c["name"] + " - short by " + str(c["short"]),
                c["what"] + f" You have {c['have']} of {c['need']} in the last {c['days']} days.",
                {"mission": "circuits"} if c["key"] != "approaches" else {"approach": True},
                2 if c["key"] != "approaches" else 3))

    out.sort(key=lambda f: -f["severity"])
    return out


def summary(entries, now=None):
    """One line about where you are."""
    if not entries:
        return "Nothing in the logbook yet. Fly something with scoring switched on."
    lands = [l for _, l in _lands(entries)]
    scored = [l["score"] for l in lands if l.get("score") is not None]
    days = (now or time.time() - 0) - max(e.get("time", 0) for e in entries)
    bits = [f"{len(entries)} flights", f"{len(lands)} landings"]
    if scored:
        bits.append(f"average landing {_avg(scored):.0f}")
    bits.append(f"last flown {days / DAY:.0f} days ago")
    return " · ".join(bits)
