"""
xp_link.py - talk to a running X-Plane 12 through its built-in local Web API.

 * Starting a flight (aircraft, position, time, weather) needs X-Plane 12.4.0+
   (POST /api/v3/flight).  Reading/writing datarefs needs 12.1.1+.
 * The Web API must be allowed in X-Plane: Settings > Network > "Web API"
   (default port 8086, local connections only).
 * Loading the route into the GPS/FMS is done by the companion XPPython3 plugin
   (PI_FlightIdeas.py) - X-Plane's Web API has no flight-plan endpoint.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FAILURE_DATAREFS = {
    "engine":     ["sim/operation/failures/rel_engfai0"],
    "engine2":    ["sim/operation/failures/rel_engfai1"],
    "roughness":  ["sim/operation/failures/rel_engfir0"],
    "vacuum":     ["sim/operation/failures/rel_vacuum"],
    "radio":      ["sim/operation/failures/rel_com1", "sim/operation/failures/rel_com2"],
    "electrics":  ["sim/operation/failures/rel_genera0", "sim/operation/failures/rel_batter0"],
    "alternator": ["sim/operation/failures/rel_genera0"],
    "pitot":      ["sim/operation/failures/rel_pitot"],
    "static":     ["sim/operation/failures/rel_static"],
    "asi":        ["sim/operation/failures/rel_ss_asi"],
    "attitude":   ["sim/operation/failures/rel_ss_ahz"],
    "altimeter":  ["sim/operation/failures/rel_ss_alt"],
    "gyro":       ["sim/operation/failures/rel_ss_dgy"],
    "gear":       ["sim/operation/failures/rel_landing_gear"],
    "brakes":     ["sim/operation/failures/rel_lbrake", "sim/operation/failures/rel_rbrake"],
    "fuelpump":   ["sim/operation/failures/rel_fuepmp0"],
    "flaps":      ["sim/operation/failures/rel_flap"],
    "gps":        ["sim/operation/failures/rel_gps"],
    "autopilot":  ["sim/operation/failures/rel_servo_ail"],
}

# What each one means for the pilot, and what a good response looks like.
EMERGENCIES = {
    "engine":     ("Engine failure", "Best glide, pick a field, restart drill, mayday, secure."),
    "roughness":  ("Rough-running engine", "Carb heat, mixture, mags, fuel pump - and start looking for a field."),
    "vacuum":     ("Vacuum failure", "Attitude and heading gyros are lying. Cover them, fly needle-ball-airspeed."),
    "radio":      ("Radio failure", "Squawk 7600, fly the last clearance, light-gun signals on arrival."),
    "electrics":  ("Electrical failure", "Shed load, save the battery for the gear and the flaps, land soon."),
    "alternator": ("Alternator failure", "Battery only now - turn off what you don't need and land."),
    "pitot":      ("Pitot blocked", "Airspeed is unreliable - fly attitude and power settings."),
    "static":     ("Static port blocked", "Altimeter, ASI and VSI all wrong - use the alternate static source."),
    "asi":        ("Airspeed indicator failed", "Pitch and power. You know what 75% and level looks like."),
    "attitude":   ("Attitude indicator failed", "Partial panel - turn coordinator, altimeter, compass."),
    "altimeter":  ("Altimeter failed", "Use GPS altitude as a cross-check and get VFR if you can."),
    "gyro":       ("Directional gyro failed", "Wet compass - remember it lags and leads in turns."),
    "gear":       ("Gear problem", "Manual extension, fly-by for a check, plan a long final."),
    "brakes":     ("Brake failure", "Land on the longest runway into wind, minimum speed, use the whole strip."),
    "fuelpump":   ("Fuel pump failure", "Switch tanks, boost pump, be ready for it to quit."),
    "flaps":      ("Flaps jammed", "Flapless approach - faster, flatter, and much more runway."),
    "gps":        ("GPS failure", "Dead reckoning and the radios. Where were you at the last fix?"),
    "autopilot":  ("Autopilot servo failure", "Hand-fly it - and watch the trim."),
}
FAIL_NOW = 6   # X-Plane failure enum: 6 = inoperative
FIXED = 0

POS_REFS = ["sim/flightmodel/position/latitude", "sim/flightmodel/position/longitude",
            "sim/flightmodel/position/y_agl", "sim/flightmodel/position/groundspeed"]

REQUEST_FILE = "_flight_ideas_request.json"   # picked up by PI_FlightIdeas.py


class XPlaneError(Exception):
    pass


class XPlaneAPI:
    def __init__(self, host="127.0.0.1", port=8086, timeout=6):
        self.base = f"http://{host}:{int(port)}"
        self.timeout = timeout
        self._ids = {}

    # ---- low level ----------------------------------------------------------
    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read())
                msg = j.get("error_message") or j.get("message") or json.dumps(j)
            except Exception:
                msg = str(e)
            raise XPlaneError(f"X-Plane said: {msg} (HTTP {e.code})") from None
        except (urllib.error.URLError, OSError) as e:
            raise XPlaneError("Can't reach X-Plane's Web API at "
                              f"{self.base}. Is X-Plane running, and is the Web API enabled in "
                              f"Settings > Network? ({getattr(e, 'reason', e)})") from None

    # ---- info ---------------------------------------------------------------
    def capabilities(self):
        return self._req("GET", "/api/capabilities")

    def check(self):
        """Returns (can_start_flights, message)."""
        try:
            c = self.capabilities()
        except XPlaneError as e:
            return False, str(e)
        vers = c.get("api", {}).get("versions", [])
        xv = c.get("x-plane", {}).get("version", "?")
        if "v3" in vers:
            return True, f"Connected to X-Plane {xv} (Web API {', '.join(vers)})"
        return False, (f"Connected to X-Plane {xv}, but starting flights needs X-Plane 12.4.0 or newer "
                       f"(this one offers Web API {', '.join(vers) or 'v1'}). Update X-Plane, or set up the "
                       f"flight manually - the .fms route can still be loaded.")

    # ---- flights --------------------------------------------------------------
    def start_flight(self, flight: dict):
        return self._req("POST", "/api/v3/flight", {"data": flight})

    # ---- datarefs / commands ----------------------------------------------------
    def dataref_id(self, name):
        if name not in self._ids:
            q = urllib.parse.urlencode({"filter[name]": name})
            j = self._req("GET", f"/api/v2/datarefs?{q}")
            items = j.get("data") or []
            if not items:
                raise XPlaneError(f"Dataref not found: {name}")
            self._ids[name] = items[0]["id"]
        return self._ids[name]

    def get(self, name):
        return self._req("GET", f"/api/v2/datarefs/{self.dataref_id(name)}/value").get("data")

    def set(self, name, value):
        self._req("PATCH", f"/api/v2/datarefs/{self.dataref_id(name)}/value", {"data": value})

    def set_index(self, name, index, value):
        self._req("PATCH", f"/api/v2/datarefs/{self.dataref_id(name)}/value?index={int(index)}",
                  {"data": value})

    def set_fuel_kg(self, total_kg, tanks=None):
        """Put this much fuel in the tanks, split evenly. Returns how many tanks were set."""
        n = tanks
        if not n:
            try:
                n = int(float(self.get("sim/aircraft/overflow/acf_num_tanks")))
            except Exception:
                n = 2
        n = max(1, min(9, n or 2))
        per = float(total_kg) / n
        try:
            self.set("sim/flightmodel/weight/m_fuel", [per] * n)
            return n
        except Exception:
            for i in range(n):
                self.set_index("sim/flightmodel/weight/m_fuel", i, per)
            return n

    def command(self, name, duration=0.0):
        q = urllib.parse.urlencode({"filter[name]": name})
        items = self._req("GET", f"/api/v2/commands?{q}").get("data") or []
        if not items:
            raise XPlaneError(f"Command not found: {name}")
        self._req("POST", f"/api/v2/command/{items[0]['id']}/activate", {"duration": duration})

    def position(self):
        lat, lon, agl, gs = (self.get(n) for n in POS_REFS)
        return float(lat), float(lon), float(agl) * 3.28084, float(gs) * 1.94384

    def fail(self, kind, fixed=False):
        for n in FAILURE_DATAREFS[kind]:
            self.set(n, FIXED if fixed else FAIL_NOW)

    def repair_all(self):
        for kind in FAILURE_DATAREFS:
            try:
                self.fail(kind, fixed=True)
            except XPlaneError:
                pass


# ==========================================================================
# Building the flight-initialization JSON
# ==========================================================================
def build_flight(acf_rel_path, livery=None, start=None, local_time=None, weather=None,
                 engines_running=True, time_enum=None, system_time=False):
    """
    start      : one of
                 {"runway_start": {...}} / {"ramp_start": {...}} / {"lle_air_start": {...}} /
                 {"lle_ground_start": {...}}   (already shaped like X-Plane wants)
    local_time : (day_of_year, hour_float) or None
    weather    : "use_real_weather", a preset name ("vfr_few_clouds"...), a full weather dict, or None
    """
    f = {"aircraft": {"path": acf_rel_path.replace("\\", "/")}}
    if livery:
        f["aircraft"]["livery"] = livery
    f.update(start or {})
    if system_time:
        f["use_system_time"] = True
    elif local_time:
        f["local_time"] = {"day_of_year": int(local_time[0]), "time_in_24_hours": round(float(local_time[1]), 2)}
    elif time_enum:
        f["time_enum"] = time_enum
    if weather == "use_real_weather":
        f["weather"] = "use_real_weather"
    elif isinstance(weather, str) and weather:
        f["weather"] = {"definition": weather}
    elif isinstance(weather, dict):
        f["weather"] = weather
    f["engine_status"] = {"all_engines": {"running": bool(engines_running)}}
    return f


def runway_start(icao, runway, final_nm=None):
    s = {"airport_id": icao, "runway": runway}
    if final_nm:
        s["final_distance_in_nautical_miles"] = float(final_nm)
    return {"runway_start": s}


def ramp_start(icao, ramp):
    return {"ramp_start": {"airport_id": icao, "ramp": ramp}}


def ground_start(lat, lon, heading):
    return {"lle_ground_start": {"latitude": lat, "longitude": lon, "heading_true": round(heading, 1)}}


def air_start(lat, lon, alt_ft, heading, speed_kt):
    return {"lle_air_start": {"latitude": lat, "longitude": lon, "elevation_in_meters": round(alt_ft / 3.28084, 1),
                              "heading_true": round(heading, 1), "speed_in_meters_per_second": round(speed_kt * 0.51444, 1),
                              "pitch_in_degrees": 0.0}}


def send_route_to_plugin(xplane_root, fms_text, wait_for_new_flight=True):
    """Drop the flight plan where PI_FlightIdeas.py will load it into the GPS/FMS."""
    d = Path(xplane_root) / "Output" / "FMS plans"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (REQUEST_FILE + ".tmp")
    tmp.write_text(json.dumps({"fms": fms_text, "time": time.time(), "wait_for_new_flight": wait_for_new_flight}))
    tmp.replace(d / REQUEST_FILE)


def send_message_to_plugin(xplane_root, lines):
    """Ask the companion plugin to show these lines inside X-Plane."""
    d = Path(xplane_root) / "Output" / "FMS plans"
    d.mkdir(parents=True, exist_ok=True)
    (d / "_flight_ideas_message.json").write_text(json.dumps({"time": time.time(), "lines": list(lines)}))


def plugin_status(xplane_root):
    """(installed?, last-ack text) for the companion plugin."""
    root = Path(xplane_root)
    installed = (root / "Resources" / "plugins" / "PythonPlugins" / "PI_FlightIdeas.py").exists()
    ack = root / "Output" / "FMS plans" / "_flight_ideas_ack.json"
    try:
        a = json.loads(ack.read_text())
        return installed, a
    except Exception:
        return installed, None


# ==========================================================================
# In-flight monitor: arms "twist" failures at the right spot, reports progress
# ==========================================================================
def _nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(a)))


class FlightMonitor(threading.Thread):
    def __init__(self, api: XPlaneAPI, stops, failure=None, on_status=None, interval=2.0,
                 random_failure=None, on_event=None, failure_pool=None):
        """random_failure: (min_minutes, max_minutes) - something breaks at a random time in that window."""
        super().__init__(daemon=True)
        self.api, self.stops, self.failure = api, stops, failure
        self.on_event = on_event or (lambda s: None)
        self.random_failure = random_failure
        self.failure_pool = list(failure_pool or ["engine", "vacuum", "radio"])
        self.fired_kind = None          # what actually broke, for the debrief
        self.fired_at = None            # (lat, lon, agl, time)
        self._rand_at = None
        self._rand_done = False
        self.on_status = on_status or (lambda s: None)
        self.interval = interval
        self._halt = threading.Event()
        self.fired = False
        self.leg = 1

    def stop(self):
        self._halt.set()

    def fail_now(self, kind):
        self.api.fail(kind)

    def run(self):
        import random as _rnd
        time.sleep(8)   # give X-Plane time to load the new flight
        if self.random_failure:
            lo, hi = self.random_failure
            self._rand_at = time.time() + _rnd.uniform(lo, hi) * 60
        errors = 0
        while not self._halt.is_set():
            try:
                lat, lon, agl, gs = self.api.position()
                errors = 0
            except Exception as e:
                errors += 1
                self.on_status(f"Monitor: waiting for X-Plane ({e})" if errors < 5 else "Monitor: lost X-Plane")
                if errors > 30:
                    return
                self._halt.wait(self.interval * 2)
                continue
            # which stop are we heading to?
            while self.leg < len(self.stops) - 1 and \
                    _nm(lat, lon, self.stops[self.leg]["lat"], self.stops[self.leg]["lon"]) < 2 and gs < 60:
                self.leg += 1
            nxt = self.stops[min(self.leg, len(self.stops) - 1)]
            dn = _nm(lat, lon, nxt["lat"], nxt["lon"])
            msg = f"Next: {nxt['id']} {dn:.1f} nm  |  GS {gs:.0f} kt  |  {agl:,.0f} ft AGL"
            f = self.failure
            if f and not self.fired:
                df = _nm(lat, lon, f["lat"], f["lon"])
                if df <= f.get("radius", 3) and agl > 300:
                    try:
                        self.api.fail(f["type"])
                        self.fired = True
                        msg += f"  |  TWIST TRIGGERED: {f['desc']}"
                    except Exception as e:
                        msg += f"  |  couldn't trigger failure: {e}"
                        self.fired = True
                else:
                    msg += f"  |  twist armed ({df:.0f} nm away)"
            elif f and self.fired:
                msg += f"  |  twist active: {f['desc']}"
            if self._rand_at and not self._rand_done and time.time() > self._rand_at and agl > 500:
                kind = _rnd.choice(self.failure_pool or ["engine"])
                try:
                    self.fail_now(kind)
                    self._rand_done = True
                    self.fired_kind = kind
                    self.fired_at = (lat, lon, agl, time.time())
                    title, advice = EMERGENCIES.get(kind, (kind, ""))
                    self.on_event(f"EMERGENCY: {title}. {advice}")
                    msg += f"  |  {title.upper()}"
                except Exception as e:
                    self.on_event(f"Couldn't trigger the surprise failure: {e}")
                    self._rand_done = True
            elif self._rand_at and not self._rand_done:
                left = max(0, (self._rand_at - time.time()) / 60)
                msg += f"  |  surprise failure armed (~{left:.0f} min)"
            self.on_status(msg)
            self._halt.wait(self.interval)
