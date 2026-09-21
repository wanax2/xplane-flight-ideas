"""
xp_kneeboard.py - checklists, speech, and the always-on-top kneeboard window.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- checklists
GENERIC = {
    "Before start": ["Preflight walk-around done", "Weight and balance / payload set", "Fuel checked and sufficient",
                     "Controls free and correct", "Seat belts and doors secure", "Avionics off, brakes set"],
    "Start": ["Mixture rich / condition lever set", "Throttle cracked", "Fuel pump on (if fitted)",
              "Prop area clear - shout 'clear prop'", "Starter engage", "Oil pressure rising within 30 s",
              "Avionics on, altimeter set"],
    "Before takeoff": ["Run-up: mags, carb heat, prop, gauges green", "Flight controls free", "Trim set for takeoff",
                       "Flaps set", "Fuel on the fullest tank", "Instruments and heading bug set",
                       "Departure briefing: abort point, engine failure plan", "Transponder on, lights on"],
    "Cruise": ["Power and mixture set / leaned", "Engine gauges green", "Fuel burn and tank switch time noted",
               "Position and next waypoint checked", "Destination weather checked",
               "Nearest airport in mind at all times"],
    "Descent / approach": ["Destination weather and runway chosen", "Altimeter set", "Mixture enriched as needed",
                           "Approach briefing: circuit direction, go-around plan", "Landing lights on",
                           "Speed and flaps as per schedule"],
    "Before landing": ["Fuel on the fullest tank, pump on", "Mixture rich", "Gear down (if retractable) - confirm",
                       "Flaps as required", "Speed on target, stabilised by 500 ft",
                       "Runway clear, go-around decision made"],
    "After landing / shutdown": ["Flaps up, lights set", "Clear of the runway before doing anything else",
                                 "Mixture idle cut-off / condition lever off", "Mags and master off",
                                 "Control lock, chocks, log the flight"],
}
TURBINE_EXTRA = {"Start": ["Ignition on, starter engage, watch ITT/TOT", "Fuel flow at the right N1/Ng",
                           "Generators on after start"],
                 "Before takeoff": ["Torque/power check", "Anti-ice as required", "Autofeather / prop sync set"]}
HELI_EXTRA = {"Before takeoff": ["Hover check: power required vs available", "Loose articles secure",
                                 "Escape route for autorotation from the hover"],
              "Cruise": ["Height/velocity diagram in mind", "Autorotation spot always chosen"]}
GLIDER = {"Before takeoff": ["Controls, Ballast, Straps, Instruments, Trim, Canopy, Brakes (CB SIFT CB)",
                             "Release checked, cable/tow briefing", "Wind and launch failure plan"],
          "Cruise": ["Centre the thermal, stay within glide of a field", "Water ballast as needed",
                     "Final glide computed with margin"],
          "Before landing": ["Circuit joined at the planned height", "Airbrakes checked", "Undercarriage down",
                             "Approach speed = 1.5 Vs + half the wind"]}


def checklist_for(profile):
    """A phase -> items dict suited to this aircraft."""
    d = (profile.get("acf") or {})
    out = {k: list(v) for k, v in GENERIC.items()}
    if profile.get("glider") or d.get("glider"):
        out = {k: list(v) for k, v in GENERIC.items() if k in ("Before start", "Cruise")}
        out.update({k: list(v) for k, v in GLIDER.items()})
    elif profile.get("heli") or d.get("heli"):
        for k, extra in HELI_EXTRA.items():
            out.setdefault(k, []).extend(extra)
    elif d.get("turbine") or d.get("jet"):
        for k, extra in TURBINE_EXTRA.items():
            out.setdefault(k, []).extend(extra)
    if profile.get("multi"):
        out["Before takeoff"].append("Engine failure after takeoff: blue line speed, feather drill briefed")
    if profile.get("water"):
        out["Before landing"].append("Water landing: gear UP for water, DOWN for land - say it out loud")
    return out


# ---------------------------------------------------------------- speech
def speak(text, wait=False):
    """Say something out loud using whatever the operating system provides."""
    text = (text or "").replace('"', "'")[:1200]
    if not text.strip():
        return

    def run():
        try:
            if sys.platform.startswith("win"):
                ps = ("Add-Type -AssemblyName System.Speech; "
                      "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\"%s\")" % text)
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000,
                               capture_output=True, timeout=120)
            elif sys.platform == "darwin":
                subprocess.run(["say", text], capture_output=True, timeout=120)
            else:
                subprocess.run(["espeak", text], capture_output=True, timeout=120)
        except Exception:
            pass
    if wait:
        run()
    else:
        threading.Thread(target=run, daemon=True).start()


def briefing_speech(idea, ac):
    from xp_flight_ideas import d as dist
    legs = " then ".join(f"{b['id']}" for b in idea.stops[1:])
    total = sum(dist(a, b) for a, b in zip(idea.stops, idea.stops[1:]))
    return (f"{idea.title}. Flying the {ac['name']} from {idea.stops[0]['name']} to {legs}. "
            f"{total:.0f} nautical miles. {idea.wx.describe()}. {idea.mission}"
            + (f" Twist: {idea.twist}" if idea.twist else ""))


# ---------------------------------------------------------------- kneeboard
class Kneeboard(tk.Toplevel):
    """Small always-on-top window with the mission, the next waypoint and a checklist."""

    def __init__(self, master, idea, profile, on_close=None):
        super().__init__(master)
        self.theme = getattr(master, "theme", None)
        if self.theme:
            self.theme.track(self, "window")
        self.title("Kneeboard")
        self.attributes("-topmost", True)
        self.geometry("380x560+40+40")
        self.on_close = on_close
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.idea, self.profile = idea, profile
        head = ttk.Frame(self, padding=6)
        head.pack(fill="x")
        self.l_title = ttk.Label(head, text=idea.title, wraplength=350,
                                 font=(self.theme.family, 11, "bold") if self.theme
                                 else ("TkDefaultFont", 11, "bold"))
        self.l_title.pack(anchor="w")
        self.v_live = tk.StringVar(value="(no live data yet)")
        ttk.Label(head, textvariable=self.v_live,
                  font=self.theme.mono if self.theme else ("Consolas", 10),
                  foreground=self.theme.c["ok"] if self.theme else "#0a5").pack(anchor="w")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        t1 = ttk.Frame(nb, padding=4)
        nb.add(t1, text="Mission")
        txt = tk.Text(t1, wrap="word", height=10,
                      font=(self.theme.family, 10) if self.theme else ("TkDefaultFont", 10))
        if self.theme:
            self.theme.track(txt, "text")
        txt.pack(fill="both", expand=True)
        body = [idea.mission, "", idea.when_text(), idea.sun_text(), idea.wx.describe()]
        body += [""] + [f"- {n}" for n in idea.notes]
        if idea.twist:
            body += ["", "TWIST: " + idea.twist]
        route = " -> ".join(a["id"] for a in idea.stops)
        body += ["", "Route: " + route]
        txt.insert("1.0", "\n".join(body))
        txt.config(state="disabled")
        t2 = ttk.Frame(nb, padding=4)
        nb.add(t2, text="Checklist")
        self.phase = tk.StringVar()
        lists = checklist_for(profile)
        self.lists = lists
        cb = ttk.Combobox(t2, textvariable=self.phase, values=list(lists), state="readonly")
        cb.pack(fill="x")
        cb.current(0)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill_checklist())
        self.box = ttk.Frame(t2)
        self.box.pack(fill="both", expand=True, pady=4)
        self.fill_checklist()
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        ttk.Button(bar, text="Read it to me", command=lambda: speak(briefing_speech(idea, profile))).pack(side="left")
        ttk.Button(bar, text="Close", command=self.close).pack(side="right")

    def fill_checklist(self):
        for w in self.box.winfo_children():
            w.destroy()
        for item in self.lists.get(self.phase.get(), []):
            v = tk.BooleanVar()
            ttk.Checkbutton(self.box, text=item, variable=v).pack(anchor="w")

    def update_live(self, text):
        try:
            self.v_live.set(text)
        except tk.TclError:
            pass

    def close(self):
        if self.on_close:
            self.on_close()
        self.destroy()
