"""
PI_FlightIdeas.py - XPPython3 companion plugin for the X-Plane Flight Ideas app.

Loads the route chosen in xp_flight_ideas_gui.py into the aircraft's GPS / FMS
(G1000, GNS 430/530, Laminar FMS...) using X-Plane's XPLMLoadFMSFlightPlan.

Install
  1. Install XPPython3 (https://xppython3.readthedocs.io) for your X-Plane 12.
  2. Copy this file to  X-Plane 12/Resources/plugins/PythonPlugins/
     (the GUI's "Install GPS plugin" button does this for you).
  3. Restart X-Plane (or Plugins > XPPython3 > Reload scripts).

How it works
  The GUI writes  Output/FMS plans/_flight_ideas_request.json . This plugin
  checks for it once a second; after a new flight finishes loading it loads the
  route into the pilot (and co-pilot) GPS/FMS and writes _flight_ideas_ack.json.
  Menu: Plugins > Flight Ideas > "Reload route into GPS" to push it again
  (e.g. if your avionics were still booting).
"""
import json
import os
import time

from XPPython3 import xp

SETTLE_SECONDS = 5.0      # wait after a flight loads before touching the avionics
WAIT_FOR_FLIGHT_MAX = 90  # if no "flight loaded" message arrives, load anyway after this


class PythonInterface:
    def __init__(self):
        self.Name = "Flight Ideas route loader"
        self.Sig = "flightideas.routeloader"
        self.Desc = "Loads routes sent by the Flight Ideas app into the GPS/FMS."
        self.loop = None
        self.menu = None
        self.last_loaded = None
        self.flight_loaded_at = time.time()
        self.fms_dir = ""

    # ---- lifecycle ------------------------------------------------------------
    def XPluginStart(self):
        self.fms_dir = os.path.join(xp.getSystemPath(), "Output", "FMS plans")
        self.req = os.path.join(self.fms_dir, "_flight_ideas_request.json")
        self.msg = os.path.join(self.fms_dir, "_flight_ideas_message.json")
        self.last_msg = 0
        self.ack = os.path.join(self.fms_dir, "_flight_ideas_ack.json")
        # ignore requests left over from an earlier session
        try:
            if time.time() - os.path.getmtime(self.req) > 600:
                self.last_loaded = os.path.getmtime(self.req)
        except OSError:
            pass
        self.loop = xp.createFlightLoop(self.tick)
        xp.scheduleFlightLoop(self.loop, 1.0, 1)
        self.menu = xp.createMenu("Flight Ideas", handler=self.on_menu)
        xp.appendMenuItem(self.menu, "Reload route into GPS", "reload")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.loop:
            xp.destroyFlightLoop(self.loop)
        if self.menu:
            xp.destroyMenu(self.menu)

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        if inMessage in (xp.MSG_PLANE_LOADED, xp.MSG_AIRPORT_LOADED, xp.MSG_SCENERY_LOADED):
            self.flight_loaded_at = time.time()

    # ---- work -------------------------------------------------------------------
    def on_menu(self, menuRef, itemRef):
        if itemRef == "reload":
            self.load(force=True)

    def tick(self, sinceLast, elapsedTime, counter, refCon):
        try:
            self.load()
            self.messages()
        except Exception as e:  # never let an exception kill the flight loop
            xp.log(f"FlightIdeas: {e}")
        return 1.0

    def messages(self):
        """Show anything the app wants to say on X-Plane's own message line."""
        if not os.path.exists(self.msg):
            return
        m = os.path.getmtime(self.msg)
        if m == self.last_msg:
            return
        self.last_msg = m
        if time.time() - m > 120:
            return
        with open(self.msg, "r", encoding="utf-8") as f:
            data = json.load(f)
        for line in (data.get("lines") or [])[:6]:
            xp.speakString(str(line)[:250])

    def load(self, force=False):
        if not os.path.exists(self.req):
            return
        mtime = os.path.getmtime(self.req)
        if not force:
            if mtime == self.last_loaded:
                return
            with open(self.req, "r", encoding="utf-8") as f:
                req = json.load(f)
            now = time.time()
            if req.get("wait_for_new_flight") and self.flight_loaded_at < mtime and now - mtime < WAIT_FOR_FLIGHT_MAX:
                return  # the new flight hasn't loaded yet
            if now - self.flight_loaded_at < SETTLE_SECONDS:
                return
        else:
            with open(self.req, "r", encoding="utf-8") as f:
                req = json.load(f)
        plan = req["fms"]
        xp.loadFMSFlightPlan(0, plan)
        try:
            xp.loadFMSFlightPlan(1, plan)
        except Exception:
            pass
        self.last_loaded = mtime
        first = next((l for l in plan.splitlines() if l.startswith("ADEP")), "")
        last = next((l for l in plan.splitlines() if l.startswith("ADES")), "")
        msg = f"Route loaded into GPS/FMS: {first[5:]} -> {last[5:]}"
        xp.log(f"FlightIdeas: {msg}")
        with open(self.ack, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "request_time": req.get("time"), "message": msg}, f)
