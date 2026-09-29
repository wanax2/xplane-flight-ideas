"""
xp_checkride.py - manoeuvres, watched and graded while you fly them.

The landing grader in xp_score has been marking your arrivals for a while. This
does the same thing for the flying in between: you tell it which manoeuvre you
are about to fly, you fly it, and it watches the sim's own numbers and tells you
afterwards where you were outside tolerance and by how much.

The tolerances are the FAA private-pilot ACS ones, because they are the numbers
most people have heard of - 45 degrees of bank plus or minus 5, altitude plus or
minus 100 feet, heading plus or minus 10. Commercial tolerances are tighter and
you can switch to them. Nothing here is a real checkride and nothing you do here
counts towards anything: it is a stopwatch and a ruler, not an examiner.

Two halves, deliberately kept apart:

  * the `Task` classes are pure - hand one a list of samples and it gives you a
    score. No network, no threads, so they can be tested with made-up flights.
  * `Watcher` is the thread that collects those samples from the Web API,
    decides when the manoeuvre has started and finished, and hands them over.

The grading curve is the same everywhere: full marks up to half tolerance, 80 at
exactly tolerance, sliding to nothing at the bust value. So a pass looks like 80
and anything above that is polish.
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

M_FT = 3.28084
MS_KT = 1.94384

REFS = {
    "lat": "sim/flightmodel/position/latitude",
    "lon": "sim/flightmodel/position/longitude",
    "alt": "sim/flightmodel/position/elevation",          # metres MSL
    "agl": "sim/flightmodel/position/y_agl",
    "ias": "sim/flightmodel/position/indicated_airspeed",
    "vs": "sim/flightmodel/position/vh_ind_fpm",
    "roll": "sim/flightmodel/position/phi",
    "pitch": "sim/flightmodel/position/theta",
    "hdg": "sim/flightmodel/position/psi",
    "gnd": "sim/flightmodel/failures/onground_any",
    "g": "sim/flightmodel/forces/g_nrml",
}
WATCH = ("alt", "agl", "ias", "vs", "roll", "pitch", "hdg", "gnd", "g")

# Tolerances, by standard. (altitude ft, heading deg, speed kt, bank deg)
STANDARDS = {
    "private": {"alt": 100, "hdg": 10, "ias": 10, "bank": 5,
                "name": "Private pilot", "why": "The everyday standard - what a PPL checkride asks for."},
    "commercial": {"alt": 50, "hdg": 5, "ias": 5, "bank": 5,
                   "name": "Commercial", "why": "Half the altitude and heading slack. Unforgiving, and it shows."},
}


# ==========================================================================
# Scoring curve
# ==========================================================================
def band(dev, tol, bust=None):
    """100 at half tolerance, 80 at tolerance, 0 at the bust value."""
    dev, tol = abs(float(dev)), float(tol)
    bust = float(bust if bust is not None else tol * 3.0)
    if dev <= tol / 2.0:
        return 100.0
    if dev <= tol:
        return 100.0 - 20.0 * (dev - tol / 2.0) / (tol / 2.0)
    if dev >= bust:
        return 0.0
    return 80.0 * (1.0 - (dev - tol) / (bust - tol))


def ang_diff(a, b):
    """Signed smallest difference a - b, in degrees."""
    return (float(a) - float(b) + 540.0) % 360.0 - 180.0


def _max_dev(samples, key, target):
    return max((abs(s[key] - target) for s in samples), default=0.0)


def _max_ang_dev(samples, key, target):
    return max((abs(ang_diff(s[key], target)) for s in samples), default=0.0)


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _settled(samples, secs=2.0, lim=200.0):
    """Has the vertical speed been near zero for a couple of seconds?"""
    t = samples[-1]["t"] - secs
    tail = [s for s in samples if s["t"] >= t]
    return len(tail) >= 4 and all(abs(s["vs"]) < lim for s in tail)


def _part(name, dev, tol, unit, note=""):
    return {"name": name, "dev": dev, "tol": tol, "unit": unit,
            "score": round(band(dev, tol)), "ok": abs(dev) <= tol, "note": note}


def _fmt_dev(p):
    d, u = p["dev"], p["unit"]
    s = f"{d:,.0f}" if u in ("ft", "fpm") else f"{d:.1f}".rstrip("0").rstrip(".")
    return f"{s} {u}"


# ==========================================================================
# Tasks
# ==========================================================================
class Task:
    """One manoeuvre. Subclasses say how to start it, when it ends, how it scores."""

    key = "task"
    name = "Manoeuvre"
    what = ""
    setup = ""
    min_s = 10.0
    max_s = 240.0
    needs_air = True
    min_agl = 1500

    def __init__(self, std=None, ac=None):
        self.std = std if std in STANDARDS else "private"
        self.tol = dict(STANDARDS[self.std])
        self.ac = ac or {}

    # -- entry -------------------------------------------------------------
    def entry(self, s):
        """The state the manoeuvre is measured against - captured when it begins."""
        return {"alt": s["alt"], "hdg": s["hdg"], "ias": s["ias"], "t": s["t"]}

    def ready(self, s):
        """(ok, why not) - is the aeroplane in a fit state to begin?"""
        if self.needs_air and s.get("gnd", 0) > 0.5:
            return False, "You are on the ground. Get airborne first."
        if self.needs_air and s["agl"] < self.min_agl:
            return False, (f"You are {s['agl']:,.0f} ft above the ground. This wants at least "
                           f"{self.min_agl:,} ft underneath you.")
        return True, ""

    # -- progress ----------------------------------------------------------
    def status(self, samples, e):
        """One live line while it runs."""
        el = samples[-1]["t"] - e["t"]
        return f"{el:.0f} s"

    def done(self, samples, e):
        """(finished, why). Called on every sample."""
        return (samples[-1]["t"] - e["t"] >= self.min_s), "Time."

    # -- grading -----------------------------------------------------------
    def window(self, samples, e):
        """The part of the recording that actually counts."""
        return samples

    def parts(self, samples, e):
        raise NotImplementedError

    def grade(self, samples, e):
        w = self.window(samples, e) or samples
        parts = [p for p in self.parts(w, e) if p]
        score = round(_avg([p["score"] for p in parts]) or 0)
        busts = [p for p in parts if not p["ok"]]
        return {"key": self.key, "name": self.name, "score": score, "parts": parts,
                "pass": score >= 80 and not busts, "seconds": round(samples[-1]["t"] - e["t"], 1),
                "time": time.time(), "standard": self.std, "busts": [p["name"] for p in busts]}


class SteepTurn(Task):
    key = "steep"
    name = "Steep turn"
    what = ("A full 360 at 45 degrees of bank, back on the heading you started on. Roll in smoothly, "
            "hold the bank, hold the altitude, and roll out where you rolled in.")
    setup = "Cruise speed or a little below, wings level, at least 1,500 ft AGL."
    min_s = 15.0
    max_s = 180.0
    TARGET_BANK = 45.0

    def entry(self, s):
        e = Task.entry(self, s)
        e["turned"] = 0.0
        e["last_hdg"] = s["hdg"]
        return e

    def _track(self, samples, e):
        """Accumulated heading change through the whole recording."""
        acc, last = 0.0, e["hdg"]
        out = []
        for s in samples:
            acc += ang_diff(s["hdg"], last)
            last = s["hdg"]
            out.append(acc)
        return out

    def status(self, samples, e):
        acc = self._track(samples, e)[-1]
        return f"{abs(acc):.0f} of 360 turned, {abs(samples[-1]['roll']):.0f} deg of bank"

    def done(self, samples, e):
        acc = self._track(samples, e)
        if abs(acc[-1]) >= 355 and abs(samples[-1]["roll"]) < 12:
            return True, "Round and wings level."
        if abs(acc[-1]) >= 420:
            return True, "Past a full circle."
        return False, ""

    def window(self, samples, e):
        """Ignore the roll-in and roll-out - the turn is graded while it is established."""
        acc = self._track(samples, e)
        return [s for s, a in zip(samples, acc) if 25 <= abs(a) <= 335] or samples

    def parts(self, samples, e):
        bank = _max_dev(samples, "roll", math.copysign(self.TARGET_BANK, _avg([s["roll"] for s in samples]) or 1))
        return [
            _part("Bank", bank, self.tol["bank"], "deg", "45 degrees, held."),
            _part("Altitude", _max_dev(samples, "alt", e["alt"]), self.tol["alt"], "ft",
                  "The back pressure has to come in with the bank."),
            _part("Airspeed", _max_dev(samples, "ias", e["ias"]), self.tol["ias"], "kt"),
        ]

    def grade(self, samples, e):
        g = Task.grade(self, samples, e)
        out = abs(ang_diff(samples[-1]["hdg"], e["hdg"]))
        p = _part("Rollout heading", out, self.tol["hdg"], "deg", "Where you finished against where you began.")
        g["parts"].append(p)
        g["score"] = round(_avg([x["score"] for x in g["parts"]]))
        if not p["ok"]:
            g["busts"].append(p["name"])
        g["pass"] = g["score"] >= 80 and not g["busts"]
        return g


class SlowFlight(Task):
    key = "slow"
    name = "Slow flight"
    what = ("Hold the aeroplane just above the stall - stall warning on and off - straight, level and on "
            "heading for 30 seconds. Power and pitch are doing each other's jobs down here.")
    setup = "Configured as you like, at least 1,500 ft AGL, on a heading you can hold."
    min_s = 30.0
    max_s = 180.0
    HOLD = 30.0

    def target_ias(self):
        vso = (self.ac.get("acf") or {}).get("vso")
        return round(1.15 * float(vso)) if vso else None

    def entry(self, s):
        e = Task.entry(self, s)
        e["target"] = self.target_ias() or round(s["ias"])
        return e

    def status(self, samples, e):
        el = samples[-1]["t"] - e["t"]
        return f"{el:.0f} of {self.HOLD:.0f} s, {samples[-1]['ias']:.0f} kt (want {e['target']:.0f})"

    def done(self, samples, e):
        return (samples[-1]["t"] - e["t"] >= self.HOLD), "Held."

    def parts(self, samples, e):
        return [
            _part("Airspeed", _max_dev(samples, "ias", e["target"]), self.tol["ias"], "kt",
                  f"Target {e['target']:.0f} kt, about 15 per cent above the stall."),
            _part("Altitude", _max_dev(samples, "alt", e["alt"]), self.tol["alt"], "ft"),
            _part("Heading", _max_ang_dev(samples, "hdg", e["hdg"]), self.tol["hdg"], "deg",
                  "Rudder work - there is a lot of it at this speed."),
        ]


class PowerOffStall(Task):
    key = "stall"
    name = "Power-off stall"
    what = ("Power to idle, hold the nose up until it breaks, then recover: nose down, power up, wings level. "
            "Graded on how much height the recovery costs and how straight it stays.")
    setup = "At least 3,000 ft AGL. Clear the area first - it is your neck."
    min_s = 8.0
    max_s = 180.0
    min_agl = 3000

    def _stalled(self, samples):
        """The break: the lowest speed reached, once it has actually got slow."""
        if len(samples) < 4:
            return None
        lo = min(range(len(samples)), key=lambda i: samples[i]["ias"])
        return lo if samples[lo]["ias"] < samples[0]["ias"] * 0.75 else None

    def status(self, samples, e):
        s = samples[-1]
        return f"{s['ias']:.0f} kt, {s['alt'] - e['alt']:+,.0f} ft, {s['vs']:+,.0f} fpm"

    def done(self, samples, e):
        i = self._stalled(samples)
        if i is None:
            return False, ""
        after = samples[i:]
        if len(after) < 5:
            return False, ""
        s = samples[-1]
        # recovered: flying again, climbing or at worst level, wings near level
        if s["ias"] > samples[i]["ias"] + 15 and s["vs"] > -100 and abs(s["roll"]) < 15:
            return True, "Recovered."
        return False, ""

    def parts(self, samples, e):
        i = self._stalled(samples)
        if i is None:
            return [{"name": "The stall", "dev": 0, "tol": 1, "unit": "", "score": 0, "ok": False,
                     "note": "It never stalled. The speed never got low enough to call it one."}]
        peak = max(s["alt"] for s in samples[:i + 1])
        trough = min(s["alt"] for s in samples[i:])
        lost = peak - trough
        after = samples[i:]
        return [
            _part("Height lost", lost, 200, "ft",
                  f"From {peak:,.0f} ft down to {trough:,.0f} ft. A clean recovery costs under 200."),
            _part("Wings level", max(abs(s["roll"]) for s in after), 10, "deg",
                  "A wing dropping at the break is how a stall becomes a spin."),
            _part("Heading", _max_ang_dev(after, "hdg", e["hdg"]), self.tol["hdg"] * 2, "deg",
                  "Rudder keeps it straight - not aileron."),
        ]


class EmergencyDescent(Task):
    key = "emdesc"
    name = "Emergency descent"
    what = ("Get down, fast, without breaking anything: 3,000 ft off in a hurry, speed under control, "
            "then level off on an altitude. This is the fire-in-the-cabin drill.")
    setup = "At least 4,000 ft AGL with 3,000 ft of room underneath."
    min_s = 20.0
    max_s = 300.0
    min_agl = 4000
    DROP = 3000.0

    def vne(self):
        acf = self.ac.get("acf") or {}
        return float(acf.get("vne") or (self.ac.get("cruise", 110) * 1.45))

    def entry(self, s):
        e = Task.entry(self, s)
        e["floor"] = s["alt"] - self.DROP
        e["vne"] = self.vne()
        return e

    def status(self, samples, e):
        s = samples[-1]
        return f"{s['alt'] - e['floor']:+,.0f} ft to run, {s['vs']:+,.0f} fpm, {s['ias']:.0f} kt"

    def done(self, samples, e):
        s = samples[-1]
        if s["alt"] <= e["floor"] + 200 and _settled(samples, 2.0, 300):
            return True, "Levelled off."
        if s["alt"] <= e["floor"] - 400:
            return True, "Through the altitude."
        return False, ""

    def parts(self, samples, e):
        fastest = min(s["vs"] for s in samples)
        over = max(0.0, max(s["ias"] for s in samples) - e["vne"])
        lowest = min(s["alt"] for s in samples)
        end = samples[-1]["alt"]
        return [
            _part("Rate of descent", max(0.0, 1500.0 + fastest), 300, "fpm",
                  f"Best {abs(fastest):,.0f} fpm. An emergency descent wants 1,500 or better."),
            _part("Never-exceed speed", over, 0.1, "kt",
                  f"Vne about {e['vne']:.0f} kt. You reached {max(s['ias'] for s in samples):.0f}."),
            _part("Level-off", abs(end - e["floor"]), self.tol["alt"], "ft",
                  f"Stopping on the altitude, not through it - you went to {lowest:,.0f} ft."),
        ]


class StraightLevel(Task):
    key = "level"
    name = "Straight and level"
    what = ("Two minutes of holding altitude, heading and speed exactly. Dull, and the thing every "
            "instrument rating is actually made of.")
    setup = "Trimmed out, at least 1,000 ft AGL. Try it on instruments alone."
    min_s = 120.0
    max_s = 300.0
    min_agl = 1000
    HOLD = 120.0

    def status(self, samples, e):
        s = samples[-1]
        return (f"{samples[-1]['t'] - e['t']:.0f} of {self.HOLD:.0f} s, {s['alt'] - e['alt']:+,.0f} ft, "
                f"{ang_diff(s['hdg'], e['hdg']):+.0f} deg")

    def done(self, samples, e):
        return (samples[-1]["t"] - e["t"] >= self.HOLD), "Two minutes."

    def parts(self, samples, e):
        return [
            _part("Altitude", _max_dev(samples, "alt", e["alt"]), self.tol["alt"], "ft"),
            _part("Heading", _max_ang_dev(samples, "hdg", e["hdg"]), self.tol["hdg"], "deg"),
            _part("Airspeed", _max_dev(samples, "ias", e["ias"]), self.tol["ias"], "kt"),
        ]


class ClimbLevelOff(Task):
    key = "climb"
    name = "Climb and level off"
    what = ("Climb 1,000 ft on a constant heading and stop exactly on the altitude. Most altitude busts "
            "happen in the last hundred feet of a climb.")
    setup = "Any altitude with 1,000 ft of air above you."
    min_s = 20.0
    max_s = 420.0
    min_agl = 500
    CLIMB = 1000.0

    def entry(self, s):
        e = Task.entry(self, s)
        e["ceiling"] = s["alt"] + self.CLIMB
        return e

    def status(self, samples, e):
        s = samples[-1]
        return f"{e['ceiling'] - s['alt']:+,.0f} ft to go, {s['vs']:+,.0f} fpm"

    def done(self, samples, e):
        s = samples[-1]
        if s["alt"] >= e["ceiling"] - 150 and _settled(samples):
            return True, "Level."
        if s["alt"] >= e["ceiling"] + 400:
            return True, "Through the altitude."
        return False, ""

    def parts(self, samples, e):
        top = max(s["alt"] for s in samples)
        climbing = [s for s in samples if s["vs"] > 200] or samples
        return [
            _part("Level-off", abs(samples[-1]["alt"] - e["ceiling"]), self.tol["alt"], "ft",
                  f"You peaked at {top:,.0f} ft against {e['ceiling']:,.0f} asked for."),
            _part("Heading", _max_ang_dev(samples, "hdg", e["hdg"]), self.tol["hdg"], "deg"),
            _part("Climb speed", max(abs(s["ias"] - _avg([x["ias"] for x in climbing])) for s in climbing),
                  self.tol["ias"], "kt", "Holding one speed all the way up, whatever speed you chose."),
        ]


class Descent(Task):
    key = "descent"
    name = "Constant-rate descent"
    what = ("Down 1,000 ft at 500 feet a minute, on heading and on speed, and level off on the number. "
            "The rate is the point: not 700 then 300.")
    setup = "At least 1,500 ft AGL - you need 1,000 ft of it to give away."
    min_s = 30.0
    max_s = 420.0
    min_agl = 1500
    DROP = 1000.0
    RATE = -500.0

    def entry(self, s):
        e = Task.entry(self, s)
        e["floor"] = s["alt"] - self.DROP
        return e

    def status(self, samples, e):
        s = samples[-1]
        return f"{s['alt'] - e['floor']:+,.0f} ft to go, {s['vs']:+,.0f} fpm (want {self.RATE:+,.0f})"

    def done(self, samples, e):
        s = samples[-1]
        if s["alt"] <= e["floor"] + 150 and _settled(samples):
            return True, "Level."
        if s["alt"] <= e["floor"] - 400:
            return True, "Through the altitude."
        return False, ""

    def parts(self, samples, e):
        going = [s for s in samples if s["vs"] < -100] or samples
        return [
            _part("Rate", max(abs(s["vs"] - self.RATE) for s in going), 200, "fpm",
                  "500 fpm, steady."),
            _part("Level-off", abs(samples[-1]["alt"] - e["floor"]), self.tol["alt"], "ft"),
            _part("Heading", _max_ang_dev(samples, "hdg", e["hdg"]), self.tol["hdg"], "deg"),
        ]


class Hold(Task):
    key = "hold"
    name = "Rate-one turn"
    what = ("A 180 at rate one - three degrees a second, so it takes a minute - holding altitude "
            "throughout. The turn every hold and every procedure turn is built from.")
    setup = "At least 1,500 ft AGL, trimmed, any heading."
    min_s = 30.0
    max_s = 180.0

    def entry(self, s):
        e = Task.entry(self, s)
        e["turn_to"] = (s["hdg"] + 180.0) % 360.0
        return e

    def _track(self, samples, e):
        acc, last = 0.0, e["hdg"]
        out = []
        for s in samples:
            acc += ang_diff(s["hdg"], last)
            last = s["hdg"]
            out.append(acc)
        return out

    def status(self, samples, e):
        return f"{abs(self._track(samples, e)[-1]):.0f} of 180 turned"

    def done(self, samples, e):
        acc = self._track(samples, e)
        if abs(acc[-1]) >= 175 and abs(samples[-1]["roll"]) < 8:
            return True, "Round and level."
        return (abs(acc[-1]) >= 230), "Past it."

    def parts(self, samples, e):
        turning = [s for s in samples if abs(s["roll"]) > 5] or samples
        secs = turning[-1]["t"] - turning[0]["t"]
        rate = 180.0 / secs if secs > 1 else 0.0
        return [
            _part("Rate of turn", abs(rate - 3.0), 0.5, "deg/s",
                  f"{secs:.0f} seconds for the 180 - rate one is 60."),
            _part("Altitude", _max_dev(samples, "alt", e["alt"]), self.tol["alt"], "ft"),
            _part("Rollout heading", abs(ang_diff(samples[-1]["hdg"], e["turn_to"])), self.tol["hdg"], "deg"),
        ]


TASKS = [SteepTurn, SlowFlight, PowerOffStall, EmergencyDescent, StraightLevel, ClimbLevelOff, Descent, Hold]
BY_KEY = {t.key: t for t in TASKS}

# The sequence a full ride flies, in the order that makes sense in the air.
RIDE = ["level", "climb", "steep", "hold", "slow", "stall", "descent", "emdesc"]


def make(key, std=None, ac=None):
    return BY_KEY[key](std=std, ac=ac)


# ==========================================================================
# Watching one manoeuvre happen
# ==========================================================================
class Watcher(threading.Thread):
    """Samples the sim while one manoeuvre is flown, then grades it.

    on_status(text)   - a live line, several times a second
    on_done(result)   - the grade dict, or None if it was abandoned
    """

    def __init__(self, api, task: Task, on_status=None, on_done=None, rate=0.25, on_sample=None):
        super().__init__(daemon=True)
        self.api, self.task = api, task
        self.on_status = on_status or (lambda s: None)
        self.on_done = on_done or (lambda r: None)
        self.on_sample = on_sample or (lambda s: None)
        self.rate = rate
        self._halt = threading.Event()
        self.samples, self.e, self.result = [], None, None
        self.error = None
        self._give_up = False

    def stop(self, grade=False):
        """Abandon the manoeuvre. Nothing is graded or logged unless you ask for it."""
        self._give_up = not grade
        self._halt.set()

    def sample(self):
        d = {k: float(self.api.get(REFS[k])) for k in WATCH}
        d["alt"] *= M_FT
        d["agl"] *= M_FT
        d["t"] = time.time()
        return d

    def run(self):
        try:
            s = self.sample()
        except Exception as ex:
            self.error = str(ex)
            self.on_status(f"Can't read the sim: {ex}")
            return self.on_done(None)
        ok, why = self.task.ready(s)
        if not ok:
            self.on_status(why)
            return self.on_done(None)
        self.e = self.task.entry(s)
        self.samples = [s]
        self.on_status(f"{self.task.name}: go.")
        errors = 0
        while not self._halt.is_set():
            self._halt.wait(self.rate)
            if self._halt.is_set():
                break
            try:
                s = self.sample()
                errors = 0
            except Exception as ex:
                errors += 1
                if errors > 12:
                    self.error = str(ex)
                    self.on_status(f"Lost the sim: {ex}")
                    return self.on_done(None)
                continue
            self.samples.append(s)
            self.on_sample(s)
            el = s["t"] - self.e["t"]
            fin, why = self.task.done(self.samples, self.e)
            if fin and el >= min(self.task.min_s, 5.0):
                break
            if el > self.task.max_s:
                why = "Out of time."
                break
            self.on_status(f"{self.task.name} - {self.task.status(self.samples, self.e)}")
        if self._give_up:
            self.on_status(f"{self.task.name} abandoned - nothing graded.")
            return self.on_done(None)
        if len(self.samples) < 4:
            self.on_status("Stopped before there was anything to grade.")
            return self.on_done(None)
        try:
            self.result = self.task.grade(self.samples, self.e)
        except Exception as ex:
            self.error = str(ex)
            self.on_status(f"Couldn't grade that: {ex}")
            return self.on_done(None)
        self.on_done(self.result)


# ==========================================================================
# Words
# ==========================================================================
def verdict(score):
    return ("textbook" if score >= 95 else "sharp" if score >= 88 else "a pass" if score >= 80 else
            "outside tolerance" if score >= 60 else "well outside tolerance")


def card(result, std="private"):
    """The grade card for one manoeuvre."""
    if not result:
        return "Nothing graded."
    std = result.get("standard") or std
    L = [f"{result['name'].upper()} - {result['score']}/100, {verdict(result['score'])}",
         f"{result['seconds']:.0f} seconds, {STANDARDS[std]['name'].lower()} tolerances", ""]
    for p in result["parts"]:
        mark = "ok " if p["ok"] else "OUT"
        L.append(f"  {mark}  {p['name']:<18} worst {_fmt_dev(p):<12} "
                 f"(tolerance {p['tol']:g} {p['unit']})  {p['score']}/100")
        if p.get("note"):
            L.append(f"          {p['note']}")
    L.append("")
    if result["busts"]:
        L.append("Outside tolerance: " + ", ".join(result["busts"]) + ".")
    else:
        L.append("Everything inside tolerance.")
    return "\n".join(L)


def ride_card(results, std="private"):
    """The card for a whole sequence."""
    done = [r for r in results if r]
    if not done:
        return "Nothing flown yet."
    std = done[0].get("standard") or std
    avg = _avg([r["score"] for r in done])
    L = [f"CHECKRIDE - {len(done)} manoeuvre(s), {STANDARDS[std]['name'].lower()} tolerances", ""]
    for r in done:
        mark = "PASS" if r["pass"] else "FAIL"
        bust = (" - " + ", ".join(r["busts"])) if r["busts"] else ""
        L.append(f"  {mark}  {r['name']:<24} {r['score']:>3}/100{bust}")
    fails = [r for r in done if not r["pass"]]
    L += ["", f"Average {avg:.0f}/100."]
    if not fails:
        L.append("Every manoeuvre inside tolerance. That is the ride.")
    elif len(fails) == 1:
        L.append(f"One outside tolerance: {fails[0]['name'].lower()}. Fly that one again.")
    else:
        L.append(f"{len(fails)} outside tolerance: "
                 + ", ".join(r["name"].lower() for r in fails) + ".")
    return "\n".join(L)


class Rides:
    """Every manoeuvre you have ever been graded on, kept in one small file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.items = []
        try:
            self.items = json.loads(self.path.read_text())
        except Exception:
            self.items = []

    def save(self):
        try:
            self.path.write_text(json.dumps(self.items[:400], indent=1))
        except OSError:
            pass

    def add(self, result, aircraft="", std="private"):
        if not result:
            return None
        r = dict(result, aircraft=aircraft)
        r.setdefault("standard", std)
        self.items.insert(0, r)
        self.save()
        return r

    def best(self, key):
        xs = [r["score"] for r in self.items if r.get("key") == key]
        return max(xs) if xs else None

    def last(self, key):
        for r in self.items:
            if r.get("key") == key:
                return r
        return None

    def history(self, key, n=10):
        return [r["score"] for r in self.items if r.get("key") == key][:n]

    def line(self, key):
        """One line about how you have done at this manoeuvre before."""
        h = self.history(key, 50)
        if not h:
            return "Never flown."
        bits = [f"{len(h)} flown", f"best {max(h)}", f"last {h[0]}"]
        if len(h) >= 4:
            recent, older = _avg(h[:3]), _avg(h[3:])
            if recent and older and recent - older >= 6:
                bits.append("improving")
            elif recent and older and older - recent >= 6:
                bits.append("slipping")
        return " · ".join(bits)
