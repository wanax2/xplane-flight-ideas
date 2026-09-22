#!/usr/bin/env python3
"""
xp_flight_ideas_gui.py - point-and-click X-Plane flight idea generator.

  * Generates general-aviation flight ideas from your own X-Plane scenery.
  * Starts the flight in X-Plane 12.4+ through its local Web API: aircraft and
    livery, starting position (runway, parking spot, on final, in the air),
    date/time and weather.
  * Loads the route into the GPS/FMS (needs the small XPPython3 plugin
    PI_FlightIdeas.py - use the "Install GPS plugin" button).
  * Optionally watches the flight and triggers the idea's "twist" failure
    (engine, vacuum, radios) at the right place.

Run:  python xp_flight_ideas_gui.py      (Python 3.8+, nothing else to install)
"""
from __future__ import annotations

import json
import os
import queue
import random
import re
import shutil
import sys
import zipfile
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import xp_flight_ideas as core          # noqa: E402
import xp_link as link                  # noqa: E402
import xp_images as pics                # noqa: E402
import xp_wx as livewx                  # noqa: E402
import xp_theme                        # noqa: E402
import xp_scenery                      # noqa: E402
import xp_perf                         # noqa: E402
import xp_radio                        # noqa: E402
import xp_web                          # noqa: E402
import xp_qr                           # noqa: E402
import xp_scenic as scenic              # noqa: E402
import xp_wonders as wonders            # noqa: E402
import xp_acf                           # noqa: E402
import xp_score                         # noqa: E402
import xp_export as exp                 # noqa: E402
import xp_career as career              # noqa: E402
import xp_kneeboard as kb               # noqa: E402
import xp_terrain                       # noqa: E402
import xp_online                        # noqa: E402

COUNTRY_NAMES = {
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BO": "Bolivia",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CD": "DR Congo",
    "CH": "Switzerland",
    "CI": "Cote d'Ivoire",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cape Verde",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FO": "Faroe Islands",
    "FR": "France",
    "GB": "United Kingdom",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GP": "Guadeloupe",
    "GR": "Greece",
    "GT": "Guatemala",
    "GU": "Guam",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LK": "Sri Lanka",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MG": "Madagascar",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macau",
    "MQ": "Martinique",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PR": "Puerto Rico",
    "PT": "Portugal",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "Reunion",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SN": "Senegal",
    "SR": "Suriname",
    "SV": "El Salvador",
    "SY": "Syria",
    "TC": "Turks and Caicos",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Turkey",
    "TT": "Trinidad and Tobago",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VC": "St Vincent",
    "VE": "Venezuela",
    "VG": "British Virgin Islands",
    "VI": "US Virgin Islands",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WS": "Samoa",
    "YE": "Yemen",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}
AUTO_PROF = "Auto (read from the aircraft file)"
NA_PRESETS = {
    "All of North America": dict(country="ANY", continent="North America & Caribbean"),
    "United States": dict(country="US"),
    "Canada": dict(country="CA"),
    "Mexico": dict(country="MX"),
    "Alaska": dict(country="US", box=(51, 72, -170, -129)),
    "Hawaii": dict(country="US", box=(18.5, 22.5, -161, -154)),
    "Caribbean": dict(country="ANY", box=(8, 27.5, -90, -58)),
    "Central America": dict(country="ANY", box=(7, 19, -93, -77)),
    "US Rockies": dict(country="US", box=(35, 49.5, -117, -104)),
    "US East Coast": dict(country="US", box=(24, 47, -83, -66)),
    "US West Coast": dict(country="US", box=(32, 49.5, -125, -117)),
}
AREAS = {"world": "Whole world", "continent": "A continent", "country": "A country",
         "state": "A state / province", "near": "Near an airport"}
XP_PRESETS = ["vfr_few_clouds", "vfr_scattered", "vfr_broken", "marginal_vfr_overcast",
              "ifr_non_precision", "ifr_precision", "convective", "large_cell_thunderstorm"]
MONO = ("Consolas", 10) if sys.platform.startswith("win") else ("Courier", 10)


def scan_aircraft(root: Path):
    """Relative paths of every .acf under X-Plane/Aircraft."""
    out = []
    base = root / "Aircraft"
    if not base.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d.lower() not in ("liveries", "objects", "plugins", "cockpit_3d",
                                                                   "sounds", "airfoils", "weapons", "manuals")]
        for fn in filenames:
            if fn.lower().endswith(".acf"):
                out.append(str(Path(dirpath, fn).relative_to(root)).replace("\\", "/"))
        if dirpath.count(os.sep) - str(base).count(os.sep) > 4:
            dirnames[:] = []
    return sorted(out, key=lambda p: (0 if "Laminar Research" in p else 1, p.lower()))


def acf_label(rel):
    p = Path(rel)
    return f"{p.parent.name}  ({p.stem})"


def liveries(root: Path, rel):
    d = (root / rel).parent / "liveries"
    try:
        return sorted(x.name for x in d.iterdir() if x.is_dir())
    except OSError:
        return []


class ScrollFrame(ttk.Frame):
    """A frame that grows a scrollbar when its contents don't fit."""

    def __init__(self, master, theme, width=300):
        super().__init__(master, style="Bg.TFrame")
        self.cv = tk.Canvas(self, highlightthickness=0, borderwidth=0, width=width,
                            background=theme.c["bg"])
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self._scrolled)
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.cv, style="Bg.TFrame")
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._fit)
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind_all(seq, self._wheel, add="+")
        theme.on_change(lambda: self.cv.configure(background=theme.c["bg"]))

    def _fit(self, _e=None):
        self.cv.configure(scrollregion=self.cv.bbox("all"))

    def _scrolled(self, lo, hi):
        self.sb.set(lo, hi)

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self.cv or w is self.inner:
                break
            w = getattr(w, "master", None)
        if w is None:
            return
        step = -1 if getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4 else 1
        self.cv.yview_scroll(step, "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"X-Plane Flight Ideas {core.VERSION}")
        self._want_geometry = (1500, 900)
        self.cfg = core.load_config()
        self.q = queue.Queue()
        self.airports = None
        self.gen = None
        self.ideas = []
        self.idea = None
        self.acfs = []
        self.monitor = None
        self.revealed = set()
        self._build()
        w, h = self._want_geometry
        w, h = self.theme.px(w), self.theme.px(h)
        w = min(w, self.winfo_screenwidth() - 60)
        h = min(h, self.winfo_screenheight() - 80)
        self.geometry(f"{w}x{h}")
        self.minsize(min(self.theme.px(1000), w), min(self.theme.px(640), h))
        self.after(100, self._pump)
        self.protocol("WM_DELETE_WINDOW", self._close)
        root = core.find_xplane(self.cfg.get("xplane_root"))
        if root:
            self.v_root.set(str(root))
            self.load_xplane()
        else:
            self.log("Couldn't find X-Plane automatically - choose its folder at the top left.")

    # ======================================================================
    # Layout
    # ======================================================================
    def _build(self):
        self.theme = xp_theme.init(self, self.cfg.get("theme", "light"))
        global MONO
        MONO = self.theme.mono

        # --- title strip ---
        top = ttk.Frame(self, style="Bg.TFrame", padding=(10, 8, 10, 2))
        top.pack(fill="x")
        ttk.Label(top, text="X-Plane Flight Ideas", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"v{core.VERSION}", style="MutedBg.TLabel").pack(side="left", padx=(8, 0), pady=(4, 0))
        self.v_theme = tk.StringVar(value="Dark mode" if not self.theme.dark else "Light mode")
        ttk.Button(top, textvariable=self.v_theme, style="Quiet.TButton",
                   command=self.switch_theme).pack(side="right")

        pw = ttk.PanedWindow(self, orient="horizontal", style="TPanedwindow")
        pw.pack(fill="both", expand=True, padx=10, pady=(4, 0))
        leftwrap = ScrollFrame(pw, self.theme, width=self.theme.px(322))
        left = leftwrap.inner
        rpw = ttk.PanedWindow(pw, orient="vertical", style="TPanedwindow")
        pw.add(leftwrap, weight=0)
        pw.add(rpw, weight=1)
        mid = ttk.Frame(rpw, style="Bg.TFrame", padding=(0, 0, 0, 6))
        right = ttk.Frame(rpw, style="Bg.TFrame")
        rpw.add(mid, weight=0)
        rpw.add(right, weight=1)
        left.configure(padding=(0, 0, 10, 8))
        self._build_left(left)
        self._build_mid(mid)
        self._build_right(right)

        self.v_status = tk.StringVar(value="Starting...")
        bar = ttk.Frame(self, style="Bg.TFrame", padding=(12, 6))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.v_status, anchor="w", style="Status.TLabel").pack(side="left",
                                                                                           fill="x", expand=True)

    def switch_theme(self):
        mode = self.theme.toggle()
        self.v_theme.set("Light mode" if mode == "dark" else "Dark mode")
        core.save_config(theme=mode)
        self.log(f"Switched to {mode} mode.")
        if self.idea:
            self.show_pictures()

    def _build_left(self, f):
        c = self.cfg
        # --- X-Plane ---
        g = ttk.LabelFrame(f, text="X-Plane folder", padding=8)
        g.pack(fill="x")
        self.v_root = tk.StringVar(value=c.get("xplane_root", ""))
        ttk.Entry(g, textvariable=self.v_root, width=24).grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(g, text="Browse...", style="Quiet.TButton",
                   command=self.browse_root).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(g, text="Rescan scenery", style="Quiet.TButton",
                   command=lambda: self.load_xplane(rebuild=True)).grid(row=1, column=1, sticky="e", pady=(6, 0))
        self.l_scenery = ttk.Label(g, text="", style="Muted.TLabel", wraplength=self.theme.px(280),
                                   justify="left")
        self.l_scenery.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.v_scpref = tk.IntVar(value=int(c.get("scenery_pref", 1)))
        sr = ttk.Frame(g)
        sr.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(sr, text="Use my add-ons:").pack(side="left")
        for txt, val in (("ignore", 0), ("favour", 1), ("only", 2)):
            ttk.Radiobutton(sr, text=txt, value=val, variable=self.v_scpref).pack(side="left", padx=(4, 0))
        ttk.Button(g, text="My scenery...", style="Quiet.TButton",
                   command=self.scenery_window).grid(row=4, column=0, columnspan=2, sticky="e", pady=(4, 0))
        g.columnconfigure(0, weight=1)

        # --- Aircraft ---
        g = ttk.LabelFrame(f, text="Aircraft", padding=8)
        g.pack(fill="x", pady=8)
        ttk.Label(g, text="Plane:").grid(row=0, column=0, sticky="w")
        self.v_acf = tk.StringVar()
        self.cb_acf = ttk.Combobox(g, textvariable=self.v_acf, state="readonly", width=24)
        self.cb_acf.grid(row=0, column=1, sticky="ew")
        self.cb_acf.bind("<<ComboboxSelected>>", lambda e: self.on_acf())
        ttk.Label(g, text="Livery:").grid(row=1, column=0, sticky="w")
        self.v_livery = tk.StringVar(value="(default)")
        self.cb_livery = ttk.Combobox(g, textvariable=self.v_livery, state="readonly", width=24)
        self.cb_livery.grid(row=1, column=1, sticky="ew", pady=2)
        self.cb_livery.bind("<<ComboboxSelected>>", lambda e: self.show_plane())
        ttk.Label(g, text="Flies like:").grid(row=2, column=0, sticky="w")
        pk = c.get("profile", "auto")
        self.v_prof = tk.StringVar(value=AUTO_PROF if pk == "auto" else
                                   core.AIRCRAFT.get(pk, core.AIRCRAFT["c172"])["name"])
        self.cb_prof = ttk.Combobox(g, textvariable=self.v_prof, state="readonly", width=24,
                                    values=[AUTO_PROF] + [p["name"] for p in core.AIRCRAFT.values()])
        self.cb_prof.grid(row=2, column=1, sticky="ew")
        self.cb_prof.bind("<<ComboboxSelected>>", lambda e: self.on_profile())
        self.l_perf = ttk.Label(g, text="", style="Muted.TLabel", wraplength=250, justify="left")
        self.l_perf.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(g, text="Edit performance...", style="Quiet.TButton",
                   command=self.edit_profile).grid(row=4, column=0, columnspan=2, sticky="e", pady=(4, 0))
        g.columnconfigure(1, weight=1)

        # --- Where ---
        g = ttk.LabelFrame(f, text="Where", padding=8)
        g.pack(fill="x")
        area0 = c.get("area") or ("near" if c.get("near") else "state" if c.get("state") else "country")
        self.v_area = tk.StringVar(value=AREAS.get(area0, AREAS["country"]))
        self.v_continent = tk.StringVar(value=c.get("continent", "Europe"))
        cc = c.get("country", "US")
        self.v_country = tk.StringVar(value="United States (US)" if cc == "US" else cc)
        self.v_state = tk.StringVar(value=c.get("state", ""))
        self.v_from = tk.StringVar(value=c.get("from", ""))
        self.v_near = tk.StringVar(value=c.get("near", ""))
        self.v_radius = tk.StringVar(value=str(int(c.get("radius", 150))))
        self.v_maxleg = tk.StringVar(value=str(int(c.get("max_leg", 0))))
        self.v_private = tk.BooleanVar(value=c.get("private", True))
        g.columnconfigure(4, weight=1)
        ttk.Label(g, text="Area:").grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(g, textvariable=self.v_area, values=list(AREAS.values()), state="readonly", width=20)
        cb.grid(row=0, column=1, columnspan=4, sticky="ew")
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_area())
        self.wl_cont = ttk.Label(g, text="Continent:")
        self.wl_cont.grid(row=1, column=0, sticky="w", pady=1)
        self.cb_cont = ttk.Combobox(g, textvariable=self.v_continent, state="readonly", width=24,
                                    values=[k for k in core.CONTINENTS if k != "Whole world"])
        self.cb_cont.grid(row=1, column=1, columnspan=4, sticky="ew")
        self.wl_country = ttk.Label(g, text="Country:")
        self.wl_country.grid(row=2, column=0, sticky="w", pady=1)
        self.cb_country = ttk.Combobox(g, textvariable=self.v_country, width=24)
        self.cb_country.grid(row=2, column=1, columnspan=4, sticky="ew")
        self.cb_country.bind("<<ComboboxSelected>>", lambda e: self.on_country())
        self.cb_country.bind("<FocusOut>", lambda e: self.on_country())
        self.wl_state = ttk.Label(g, text="State/prov.:")
        self.wl_state.grid(row=3, column=0, sticky="w", pady=1)
        self.cb_state = ttk.Combobox(g, textvariable=self.v_state, width=24)
        self.cb_state.grid(row=3, column=1, columnspan=4, sticky="ew")
        self.wl_near = ttk.Label(g, text="Near:")
        self.wl_near.grid(row=4, column=0, sticky="w", pady=1)
        self.e_near = ttk.Entry(g, textvariable=self.v_near, width=7)
        self.e_near.grid(row=4, column=1, sticky="w")
        self.wl_within = ttk.Label(g, text="within nm:")
        self.wl_within.grid(row=4, column=2, sticky="e", padx=(6, 2))
        self.sp_radius = ttk.Spinbox(g, textvariable=self.v_radius, from_=10, to=1000, increment=10, width=5)
        self.sp_radius.grid(row=4, column=3, columnspan=2, sticky="w")
        self.wl_nm = ttk.Label(g, text="")
        ttk.Label(g, text="Depart from:").grid(row=5, column=0, sticky="w", pady=1)
        ttk.Entry(g, textvariable=self.v_from, width=7).grid(row=5, column=1, sticky="w")
        ttk.Label(g, text="always (optional)", style="Muted.TLabel").grid(row=5, column=2, columnspan=3,
                                                                          sticky="w")
        ttk.Label(g, text="Max leg nm:").grid(row=6, column=0, sticky="w", pady=1)
        ttk.Spinbox(g, textvariable=self.v_maxleg, from_=0, to=1000, increment=10, width=5).grid(row=6, column=1, sticky="w")
        ttk.Checkbutton(g, text="private strips", variable=self.v_private).grid(row=6, column=2, columnspan=3,
                                                                                sticky="w", padx=(6, 0))
        self.on_area()

        # --- Missions ---
        g = ttk.LabelFrame(f, text="Mission types", padding=8)
        g.pack(fill="x", pady=8)
        chosen = set(c.get("missions", [k for k in core.MISSIONS
                                        if k not in core.NOT_GENERATED and k != "realwx"]))
        self.v_miss = {k: tk.BooleanVar(value=k in chosen)
                       for k in core.MISSIONS if k not in core.NOT_GENERATED}
        self.l_miss = ttk.Label(g, text="", style="Muted.TLabel", wraplength=250, justify="left")
        self.l_miss.pack(fill="x", anchor="w")
        row = ttk.Frame(g)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Choose missions...", command=self.choose_missions).pack(side="left")
        ttk.Button(row, text="All", width=5, style="Quiet.TButton",
                   command=lambda: self.set_missions(list(self.v_miss))).pack(side="right")
        for v in self.v_miss.values():
            v.trace_add("write", lambda *a: self.update_miss_label())
        self.update_miss_label()

        # --- Options ---
        g = ttk.LabelFrame(f, text="Options", padding=8)
        g.pack(fill="x")
        self.v_count = tk.StringVar(value=str(c.get("count", 8)))
        self.v_twist = tk.IntVar(value=int(c.get("twist", 40)))
        self.v_seed = tk.StringVar(value="")
        ttk.Label(g, text="Ideas:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_count, from_=1, to=40, width=4).grid(row=0, column=1, sticky="w")
        ttk.Label(g, text="Seed:").grid(row=0, column=2, sticky="e", padx=(10, 4))
        ttk.Entry(g, textvariable=self.v_seed, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(g, text="Twists:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.l_twist = ttk.Label(g, text=f"{self.v_twist.get()}%", width=5, style="Muted.TLabel")
        ttk.Scale(g, from_=0, to=100, variable=self.v_twist, orient="horizontal",
                  command=lambda v: self.l_twist.config(text=f"{int(float(v))}%")).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 6))
        self.l_twist.grid(row=1, column=3, sticky="w", pady=(6, 0))
        g.columnconfigure(2, weight=1)

        ttk.Button(f, text="Generate ideas", style="Big.TButton",
                   command=self.generate).pack(fill="x", pady=(10, 6))

        qb = ttk.Frame(f, style="Bg.TFrame")
        qb.pack(fill="x")
        for i, (txt, cmd) in enumerate([("Scenic surprise", self.scenic_surprise),
                                        ("Anywhere on earth", self.anywhere),
                                        ("Bad weather now", self.dangerous_weather),
                                        ("Today's challenge", self.daily_challenge),
                                        ("Browse airports", self.open_picker),
                                        ("Wonders near me", self.wonders_near)]):
            ttk.Button(qb, text=txt, style="Quiet.TButton", command=cmd).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=(0, 4) if i % 2 == 0 else 0, pady=2)
        qb.columnconfigure(0, weight=1)
        qb.columnconfigure(1, weight=1)

        g = ttk.LabelFrame(f, text="Or fly your own route", padding=8)
        g.pack(fill="x", pady=(8, 0))
        self.v_custom = tk.StringVar(value=c.get("custom", ""))
        e = ttk.Entry(g, textvariable=self.v_custom)
        e.pack(fill="x")
        Tooltip(e, "Airport codes separated by spaces, e.g.  KBJC KLXV KASE")
        row = ttk.Frame(g)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Use route", command=self.custom_route).pack(side="left")
        ttk.Button(row, text="Paste share code", style="Quiet.TButton",
                   command=self.import_share).pack(side="right")
        ttk.Button(row, text="My spots...", style="Quiet.TButton",
                   command=self.spots_window).pack(side="right", padx=4)

    # ---- mission chooser -------------------------------------------------
    def set_missions(self, keys):
        keys = set(keys)
        for k, v in self.v_miss.items():
            v.set(k in keys)

    def update_miss_label(self):
        on = [k for k, v in self.v_miss.items() if v.get()]
        if not on:
            self.l_miss.config(text="Nothing chosen - every mission type will be used.")
            return
        names = [core.MISSION_NAMES.get(k, k) for k in on]
        shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        self.l_miss.config(text=f"{len(on)} chosen: {shown}")

    def choose_missions(self):
        win = tk.Toplevel(self)
        win.title("Mission types")
        win.transient(self)
        self.theme.track(win, "window")
        head = ttk.Frame(win, style="Bg.TFrame", padding=(12, 10, 12, 4))
        head.pack(fill="x")
        ttk.Label(head, text="What kind of flying?", style="Head.TLabel").pack(side="left")
        ttk.Label(head, text="Hover a line to see what it means.",
                  style="MutedBg.TLabel").pack(side="left", padx=10)
        body = ttk.Frame(win, style="Bg.TFrame", padding=(8, 0, 8, 4))
        body.pack(fill="both", expand=True)
        for i, (title, keys) in enumerate(core.MISSION_GROUPS.items()):
            col, row = i % 3, i // 3
            box = ttk.LabelFrame(body, text=title, padding=8)
            box.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            for k in keys:
                if k not in self.v_miss:
                    continue
                cb = ttk.Checkbutton(box, text=core.MISSION_NAMES.get(k, k), variable=self.v_miss[k])
                cb.pack(anchor="w")
                Tooltip(cb, core.MISSIONS[k])
        for col in range(3):
            body.columnconfigure(col, weight=1)
        foot = ttk.Frame(win, style="Bg.TFrame", padding=(12, 4, 12, 12))
        foot.pack(fill="x")
        ttk.Label(foot, text="Quick picks:", style="MutedBg.TLabel").pack(side="left", padx=(0, 6))
        for name, keys in core.MISSION_PRESETS.items():
            ttk.Button(foot, text=name, style="Quiet.TButton",
                       command=lambda ks=keys: self.set_missions(ks)).pack(side="left", padx=2)
        ttk.Button(foot, text="None", style="Quiet.TButton",
                   command=lambda: self.set_missions([])).pack(side="left", padx=2)
        ttk.Button(foot, text="Done", style="Big.TButton",
                   command=lambda: (self.save_cfg(), self.theme.forget(win), win.destroy())).pack(side="right")

    def _build_mid(self, f):
        head = ttk.Frame(f, style="Bg.TFrame")
        head.pack(fill="x", pady=(0, 4))
        ttk.Label(head, text="Ideas", style="Head.TLabel").pack(side="left")
        self.l_ideas = ttk.Label(head, text="press Generate ideas", style="MutedBg.TLabel")
        self.l_ideas.pack(side="left", padx=8)
        box = ttk.Frame(f, style="Card.TFrame")
        box.pack(fill="both", expand=True)
        self.lb = tk.Listbox(box, exportselection=False, height=5)
        self.theme.track(self.lb, "list")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.lb.yview)
        self.lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lb.pack(fill="both", expand=True, padx=1, pady=1)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.on_select())

    def _build_right(self, f):
        nb = ttk.Notebook(f)
        nb.pack(fill="both", expand=True)
        self.nb = nb
        # --- Briefing tab ---
        t1 = ttk.Frame(nb, padding=4)
        nb.add(t1, text="Briefing")
        bb = ttk.Frame(t1)
        bb.pack(side="bottom", fill="x", pady=4)
        bp = ttk.PanedWindow(t1, orient="horizontal")
        bp.pack(fill="both", expand=True)
        tf = ttk.Frame(bp)
        self.txt = ScrolledText(tf, wrap="word", font=MONO, height=20, width=60)
        self.theme.track(self.txt, "text")
        self.txt.pack(fill="both", expand=True)
        self.txt.config(state="disabled")
        pf = ttk.Frame(bp, padding=(6, 0, 0, 0))
        bp.add(tf, weight=1)
        bp.add(pf, weight=1)
        self._build_pictures(pf)
        ttk.Button(bb, text="Set up this flight  \u203a\u203a", style="Big.TButton",
                   command=lambda: nb.select(1)).pack(side="right", padx=(8, 0))
        for txt, cmd in (("Spoiler", self.reveal), ("Copy", self.copy_brief),
                         ("Save text...", self.save_brief),
                         ("Save .fms", lambda: self.save_fms(force=True)),
                         ("Export...", self.export_menu), ("Make a trip", self.trip_from_idea),
                         ("Read aloud", self.read_aloud), ("Kneeboard", self.toggle_kneeboard)):
            ttk.Button(bb, text=txt, style="Quiet.TButton", command=cmd).pack(side="left", padx=(0, 3))

        # --- Launch tab ---
        t2wrap = ScrollFrame(nb, self.theme)
        nb.add(t2wrap, text="Fly it")
        t2 = t2wrap.inner
        t2.configure(padding=(8, 6, 14, 10))
        self._build_launch(t2)

        # --- Live weather tab ---
        t4 = ttk.Frame(nb, padding=6)
        nb.add(t4, text="Weather")
        self._build_live(t4)
        self.tab_wx = t4

        # --- Scenic world tab ---
        t5 = ttk.Frame(nb, padding=6)
        nb.add(t5, text="Scenic")
        self._build_scenic(t5)
        self.tab_scenic = t5

        # --- North America / World idea tabs ---
        tna = ttk.Frame(nb, padding=6)
        nb.add(tna, text="North America")
        self._build_region_tab(tna, "na")
        self.tab_na = tna
        tw = ttk.Frame(nb, padding=6)
        nb.add(tw, text="World")
        self._build_region_tab(tw, "world")
        self.tab_world = tw

        # --- Online flights tab ---
        tof = ttk.Frame(nb, padding=6)
        nb.add(tof, text="Online")
        self._build_online(tof)
        self.tab_online = tof

        # --- Live flight tab ---
        t8 = ttk.Frame(nb, padding=6)
        nb.add(t8, text="Live")
        self._build_live_flight(t8)
        self.tab_live = t8

        # --- Career tab ---
        t9 = ttk.Frame(nb, padding=6)
        nb.add(t9, text="Career")
        self._build_career(t9)
        self.tab_career = t9

        # --- Logbook tab ---
        t6 = ttk.Frame(nb, padding=6)
        nb.add(t6, text="Logbook")
        self._build_logbook(t6)
        self.tab_log = t6

        # --- Trips tab ---
        t7 = ttk.Frame(nb, padding=6)
        nb.add(t7, text="Trips")
        self._build_trips(t7)
        self.tab_trips = t7

        # --- Log tab ---
        t3 = ttk.Frame(nb, padding=4)
        self.logtxt = ScrolledText(t3, wrap="word", font=MONO, height=10)
        self.theme.track(self.logtxt, "text")
        self.logtxt.pack(fill="both", expand=True)
        nb.add(t3, text="Log")

    def _build_pictures(self, f):
        self.map_cv = tk.Canvas(f, height=self.theme.px(260), width=self.theme.px(420), background="#e9eef1")
        self.theme.track(self.map_cv, "canvas")
        self.map_cv.pack(fill="both", expand=True)
        self.map_cv.bind("<Configure>", lambda e: self.draw_map())
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(6, 2))
        ttk.Label(row, text="Pictures of:").pack(side="left")
        self.v_picapt = tk.StringVar()
        self.cb_picapt = ttk.Combobox(row, textvariable=self.v_picapt, state="readonly", width=40)
        self.cb_picapt.pack(side="left", padx=4)
        self.cb_picapt.bind("<<ComboboxSelected>>", lambda e: self.show_pictures())
        self.v_photos = tk.BooleanVar(value=self.cfg.get("photos", True))
        ttk.Checkbutton(row, text="Photos", variable=self.v_photos,
                        command=self.show_pictures).pack(side="right")
        pn = ttk.Notebook(f)
        pn.pack(fill="both", expand=True)
        self.pic_nb = pn
        # photo
        t = ttk.Frame(pn)
        pn.add(t, text="Photo")
        self.photo_lbl = tk.Label(t, text="", background="#20252b", foreground="#ccc", height=12)
        self.photo_lbl.pack(fill="both", expand=True)
        self.photo_lbl.bind("<Configure>", lambda e: self._photo_resize())
        pr = ttk.Frame(t)
        pr.pack(fill="x")
        self.photo_cap = ttk.Label(pr, text="", foreground=self.theme.c["accent"], cursor="hand2")
        self.photo_cap.pack(side="left")
        self.photo_cap.bind("<Button-1>", lambda e: self._open_photo_page())
        self.btn_pil = ttk.Button(pr, text="Enable JPEG photos", command=self.install_pillow)
        if not pics.HAVE_PIL:
            self.btn_pil.pack(side="right")
        # diagram
        t = ttk.Frame(pn)
        pn.add(t, text="Diagram")
        self.apt_cv = tk.Canvas(t, height=self.theme.px(240), width=self.theme.px(420), background="#f3f1ea")
        self.theme.track(self.apt_cv, "canvas")
        self.apt_cv.pack(fill="both", expand=True)
        self.apt_cv.bind("<Configure>", lambda e: self.draw_diagram())
        # terrain
        t = ttk.Frame(pn)
        pn.add(t, text="Terrain")
        tb = ttk.Frame(t)
        tb.pack(fill="x")
        ttk.Button(tb, text="Check terrain", command=self.check_terrain).pack(side="left")
        self.v_dem = tk.BooleanVar(value=self.cfg.get("terrain_online", False))
        ttk.Checkbutton(tb, text="Use online terrain data (slower, more accurate)",
                        variable=self.v_dem).pack(side="left", padx=6)
        ttk.Button(tb, text="Forecast", command=self.get_taf).pack(side="right")
        self.terr_cv = tk.Canvas(t, height=self.theme.px(170), background="#eef1f3")
        self.theme.track(self.terr_cv, "canvas")
        self.terr_cv.pack(fill="both", expand=True, pady=3)
        self.l_terr = tk.Label(t, text="Press 'Check terrain' for the highest ground and a safe altitude.",
                               justify="left", anchor="nw", wraplength=420)
        self.l_terr.pack(fill="x")

        # sky
        t = ttk.Frame(pn)
        pn.add(t, text="Sky")
        self.sky_cv = tk.Canvas(t, height=self.theme.px(240), width=self.theme.px(420))
        self.theme.track(self.sky_cv, "canvas")
        self.sky_cv.pack(fill="both", expand=True)
        self.sky_cv.bind("<Configure>", lambda e: self.draw_skypic())
        # numbers
        t = ttk.Frame(pn, padding=4)
        pn.add(t, text="Numbers")
        row = ttk.Frame(t)
        row.pack(fill="x")
        ttk.Label(row, text="Fuel gal:").pack(side="left")
        self.v_fuelgal = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.v_fuelgal, width=6).pack(side="left", padx=(2, 8))
        ttk.Label(row, text="People + bags kg:").pack(side="left")
        self.v_load = tk.StringVar(value="170")
        ttk.Entry(row, textvariable=self.v_load, width=6).pack(side="left", padx=2)
        self.v_wet = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="wet runway", variable=self.v_wet,
                        command=lambda: self.draw_numbers()).pack(side="left", padx=8)
        ttk.Button(row, text="Work it out", style="Big.TButton",
                   command=self.draw_numbers).pack(side="right")
        self.num_txt = ScrolledText(t, wrap="word", height=14, font=self.theme.ui)
        self.theme.track(self.num_txt, "text")
        self.num_txt.pack(fill="both", expand=True, pady=(4, 0))
        self.num_txt.config(state="disabled")
        for v in (self.v_fuelgal, self.v_load):
            v.trace_add("write", lambda *a: self.debounce("num", self.draw_numbers, 400))

        # radio
        t = ttk.Frame(pn, padding=4)
        pn.add(t, text="Radio")
        row = ttk.Frame(t)
        row.pack(fill="x")
        ttk.Label(row, text="Callsign:").pack(side="left")
        self.v_callsign = tk.StringVar(value=self.cfg.get("callsign", "N12345"))
        ttk.Entry(row, textvariable=self.v_callsign, width=10).pack(side="left", padx=(2, 8))
        ttk.Button(row, text="Read the ATIS aloud", style="Quiet.TButton",
                   command=self.speak_atis).pack(side="right")
        ttk.Button(row, text="Refresh", style="Quiet.TButton",
                   command=self.draw_radio).pack(side="right", padx=4)
        self.radio_txt = ScrolledText(t, wrap="word", height=14, font=self.theme.ui)
        self.theme.track(self.radio_txt, "text")
        self.radio_txt.pack(fill="both", expand=True, pady=(4, 0))
        self.radio_txt.config(state="disabled")
        self.v_callsign.trace_add("write", lambda *a: self.debounce("radio", self.draw_radio, 500))

        # plane
        t = ttk.Frame(pn)
        pn.add(t, text="Plane")
        self.plane_lbl = tk.Label(t, text="", background="#f4f4f4", height=12)
        self.plane_lbl.pack(fill="both", expand=True)
        self.plane_lbl.bind("<Configure>", lambda e: self._plane_resize())
        self.plane_cap = ttk.Label(t, text="")
        self.plane_cap.pack(anchor="w")
        self.photos = pics.PhotoFetcher(core.CACHE_DIR)
        self._photo_info = None
        self._photo_req = 0
        self._resize_job = {}

    def _build_launch(self, f):
        c = self.cfg
        # connection
        g = ttk.LabelFrame(f, text="Connection (X-Plane 12.4+ Web API)", padding=6)
        g.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.v_host = tk.StringVar(value=c.get("host", "127.0.0.1"))
        self.v_port = tk.StringVar(value=str(c.get("port", 8086)))
        ttk.Label(g, text="Host:").pack(side="left")
        ttk.Entry(g, textvariable=self.v_host, width=14).pack(side="left")
        ttk.Label(g, text=" Port:").pack(side="left")
        ttk.Entry(g, textvariable=self.v_port, width=6).pack(side="left")
        ttk.Button(g, text="Test connection", command=self.test_conn).pack(side="left", padx=6)
        self.l_conn = ttk.Label(g, text="not checked", style="Muted.TLabel")
        self.l_conn.pack(side="left")

        # start position
        g = ttk.LabelFrame(f, text="Starting position", padding=6)
        g.grid(row=1, column=0, sticky="nsew", pady=4, padx=(0, 4))
        g.columnconfigure(3, weight=1)
        self.v_dep = tk.StringVar()
        self.v_start = tk.StringVar(value=c.get("start", "runway"))
        self.v_rwy = tk.StringVar()
        self.v_ramp = tk.StringVar()
        self.v_final = tk.StringVar(value="3")
        self.v_frwy = tk.StringVar()
        self.v_airpct = tk.StringVar(value="30")
        self.v_airalt = tk.StringVar(value="4500")
        ttk.Label(g, text="Departure airport:").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(g, textvariable=self.v_dep, width=8)
        e.grid(row=0, column=1, sticky="w")
        e.bind("<FocusOut>", lambda ev: self.refresh_dep())
        e.bind("<Return>", lambda ev: self.refresh_dep())
        self.l_dep = ttk.Label(g, text="", style="Muted.TLabel")
        self.l_dep.grid(row=6, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(g, text="On the runway", value="runway", variable=self.v_start).grid(row=1, column=0, sticky="w")
        self.cb_rwy = ttk.Combobox(g, textvariable=self.v_rwy, width=8, state="readonly")
        self.cb_rwy.grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(g, text="Parked at", value="ramp", variable=self.v_start).grid(row=2, column=0, sticky="w")
        self.cb_ramp = ttk.Combobox(g, textvariable=self.v_ramp, width=26, state="readonly")
        self.cb_ramp.grid(row=2, column=1, columnspan=3, sticky="w", pady=2)
        ttk.Radiobutton(g, text="On final to next stop", value="final", variable=self.v_start).grid(row=3, column=0, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_final, from_=1, to=15, width=4).grid(row=3, column=1, sticky="w")
        ttk.Label(g, text="nm  rwy").grid(row=3, column=2, sticky="w")
        self.cb_frwy = ttk.Combobox(g, textvariable=self.v_frwy, width=6, state="readonly")
        self.cb_frwy.grid(row=3, column=3, sticky="w")
        ttk.Radiobutton(g, text="In the air, % of leg 1", value="air", variable=self.v_start).grid(row=4, column=0, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_airpct, from_=5, to=95, increment=5, width=4).grid(row=4, column=1, sticky="w")
        ttk.Label(g, text="ft MSL").grid(row=4, column=2, sticky="w")
        ttk.Entry(g, textvariable=self.v_airalt, width=7).grid(row=4, column=3, sticky="w")
        self.v_engines = tk.BooleanVar(value=c.get("engines", True))
        ttk.Checkbutton(g, text="Engines running (untick for cold & dark)",
                        variable=self.v_engines).grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # time
        g = ttk.LabelFrame(f, text="Date and time", padding=6)
        g.grid(row=2, column=0, sticky="nsew", padx=(0, 4))
        self.v_timemode = tk.StringVar(value="custom")
        self.v_month = tk.StringVar(value=core.MONTHS[5])
        self.v_hour = tk.StringVar(value="09:00")
        ttk.Radiobutton(g, text="Set:", value="custom", variable=self.v_timemode).grid(row=0, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.v_month, values=core.MONTHS, width=10, state="readonly").grid(row=0, column=1)
        ttk.Label(g, text=" local time").grid(row=0, column=2)
        ttk.Combobox(g, textvariable=self.v_hour, width=6,
                     values=[f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]).grid(row=0, column=3)
        ttk.Radiobutton(g, text="Use my computer's date and time", value="system",
                        variable=self.v_timemode).grid(row=1, column=0, columnspan=4, sticky="w")
        rb = ttk.Radiobutton(g, text="The real time where I'm flying", value="there",
                             variable=self.v_timemode)
        rb.grid(row=2, column=0, columnspan=4, sticky="w")
        Tooltip(rb, "Today's date, and the clock time it is right now at the departure airport's "
                    "longitude - so the sun is where it really is over there.")
        self.l_there = ttk.Label(g, text="", style="Muted.TLabel")
        self.l_there.grid(row=3, column=0, columnspan=4, sticky="w")
        self.v_timemode.trace_add("write", lambda *a: self.update_there_label())

        # weather
        g = ttk.LabelFrame(f, text="Weather", padding=6)
        g.grid(row=1, column=1, rowspan=2, sticky="nsew", pady=4)
        self.v_wxmode = tk.StringVar(value=c.get("wxmode", "mission"))
        self.v_sky = tk.StringVar()
        self.v_wdir = tk.StringVar(value="0")
        self.v_wspd = tk.StringVar(value="0")
        self.v_gust = tk.StringVar(value="0")
        self.v_temp = tk.StringVar(value="15")
        self.v_vis = tk.StringVar(value="10")
        self.v_ceil = tk.StringVar(value="none")
        self.v_alt = tk.StringVar(value="29.92")
        self.v_preset = tk.StringVar(value=XP_PRESETS[0])
        ttk.Radiobutton(g, text="Mission weather (edit below)", value="mission", variable=self.v_wxmode).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(g, text="Sky:").grid(row=1, column=0, sticky="w")
        self.sky_names = {v[0]: k for k, v in core.SKY.items()}
        cb = ttk.Combobox(g, textvariable=self.v_sky, values=list(self.sky_names), width=40, state="readonly")
        cb.grid(row=1, column=1, columnspan=3, sticky="w")
        self.cb_sky = cb
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_sky_pick())
        ttk.Label(g, text="Wind from (T):").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_wdir, from_=0, to=350, increment=10, width=5, wrap=True).grid(row=2, column=1, sticky="w")
        ttk.Label(g, text="Speed kt:").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_wspd, from_=0, to=60, width=5).grid(row=2, column=3, sticky="w")
        ttk.Label(g, text="Gusts +kt:").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_gust, from_=0, to=30, width=5).grid(row=3, column=1, sticky="w")
        ttk.Label(g, text="Temp C:").grid(row=3, column=2, sticky="w")
        ttk.Spinbox(g, textvariable=self.v_temp, from_=-40, to=50, width=5).grid(row=3, column=3, sticky="w")
        ttk.Label(g, text="Visibility SM:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.v_vis, width=6,
                     values=["0.25", "0.5", "0.75", "1", "1.5", "2", "3", "5", "7", "10", "20"]
                     ).grid(row=4, column=1, sticky="w")
        ttk.Label(g, text="Altimeter:").grid(row=4, column=2, sticky="w")
        ttk.Entry(g, textvariable=self.v_alt, width=6).grid(row=4, column=3, sticky="w")
        ttk.Label(g, text="Ceiling ft AGL:").grid(row=5, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.v_ceil, width=6,
                     values=["none", "100", "200", "300", "400", "600", "800", "1000", "1500", "2500", "4000"]
                     ).grid(row=5, column=1, sticky="w")
        ttk.Button(g, text="Minimums", width=9, command=lambda: self.wx_quick("min")).grid(row=5, column=2, sticky="w")
        ttk.Button(g, text="Clear day", width=9, command=lambda: self.wx_quick("vfr")).grid(row=5, column=3, sticky="w")
        self.l_rules = ttk.Label(g, text="", style="Muted.TLabel")
        self.l_rules.grid(row=6, column=0, columnspan=4, sticky="w")
        self.l_wind = ttk.Label(g, text="", style="Muted.TLabel", wraplength=360)
        self.l_wind.grid(row=7, column=0, columnspan=4, sticky="w", pady=2)
        for v in (self.v_wdir, self.v_wspd):
            v.trace_add("write", lambda *a: self.update_wind_label())
        for v in (self.v_month, self.v_hour, self.v_sky, self.v_gust, self.v_temp, self.v_vis, self.v_ceil):
            v.trace_add("write", lambda *a: self.idea and self.debounce("sky", self.draw_skypic, 250))
        self.v_ceil.trace_add("write", lambda *a: self.update_rules_label())
        self.v_vis.trace_add("write", lambda *a: self.update_rules_label())
        ttk.Radiobutton(g, text="Real-world weather", value="real", variable=self.v_wxmode).grid(row=8, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(g, text="X-Plane preset:", value="preset", variable=self.v_wxmode).grid(row=9, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.v_preset, values=XP_PRESETS, width=24, state="readonly").grid(row=9, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(g, text="Leave X-Plane's weather alone", value="keep", variable=self.v_wxmode).grid(row=10, column=0, columnspan=4, sticky="w")

        # route / extras
        g = ttk.LabelFrame(f, text="Route and twist", padding=6)
        g.grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)
        self.v_loadroute = tk.BooleanVar(value=c.get("loadroute", True))
        self.v_arm = tk.BooleanVar(value=True)
        self.v_monitor = tk.BooleanVar(value=c.get("monitor", True))
        ttk.Checkbutton(g, text="Load the route into the GPS/FMS", variable=self.v_loadroute).grid(row=0, column=0, sticky="w")
        self.l_plugin = ttk.Label(g, text="", style="Muted.TLabel")
        self.l_plugin.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(g, text="Install GPS plugin...", command=self.install_plugin).grid(row=0, column=2, sticky="e")
        self.cb_arm = ttk.Checkbutton(g, text="Arm the twist failure", variable=self.v_arm,
                                      command=lambda: self.draw_map())
        self.cb_arm.grid(row=1, column=0, sticky="w")
        self.l_arm = ttk.Label(g, text="", style="Muted.TLabel")
        self.l_arm.grid(row=1, column=1, columnspan=2, sticky="w", padx=6)
        ttk.Checkbutton(g, text="Show live progress (distance to next stop)",
                        variable=self.v_monitor).grid(row=2, column=0, columnspan=2, sticky="w")
        self.v_grade = tk.BooleanVar(value=c.get("grade", True))
        ttk.Checkbutton(g, text="Score the flight and add it to the logbook", variable=self.v_grade).grid(
            row=3, column=0, columnspan=2, sticky="w")
        extra = ttk.Frame(g)
        extra.grid(row=5, column=0, columnspan=3, sticky="w")
        self.v_insim = tk.BooleanVar(value=c.get("insim", True))
        ttk.Checkbutton(extra, text="Show the mission inside X-Plane", variable=self.v_insim).pack(side="left")
        self.v_speak = tk.BooleanVar(value=c.get("speak", False))
        ttk.Checkbutton(extra, text="Read the briefing aloud", variable=self.v_speak).pack(side="left", padx=8)
        self.v_knee = tk.BooleanVar(value=c.get("knee", False))
        ttk.Checkbutton(extra, text="Open the kneeboard", variable=self.v_knee).pack(side="left")
        sur = ttk.Frame(g)
        sur.grid(row=6, column=0, columnspan=3, sticky="w")
        self.v_surprise = tk.BooleanVar(value=c.get("surprise", False))
        ttk.Checkbutton(sur, text="Surprise failure between", variable=self.v_surprise).pack(side="left")
        self.v_sur_lo = tk.StringVar(value=str(c.get("sur_lo", 10)))
        self.v_sur_hi = tk.StringVar(value=str(c.get("sur_hi", 40)))
        ttk.Spinbox(sur, textvariable=self.v_sur_lo, from_=1, to=180, width=4).pack(side="left", padx=2)
        ttk.Label(sur, text="and").pack(side="left")
        ttk.Spinbox(sur, textvariable=self.v_sur_hi, from_=2, to=240, width=4).pack(side="left", padx=2)
        ttk.Label(sur, text="minutes after takeoff").pack(side="left")
        ttk.Button(sur, text="Which ones...", style="Quiet.TButton",
                   command=self.choose_emergencies).pack(side="left", padx=8)
        self.v_emerg = {k: tk.BooleanVar(value=k in set(c.get("emergencies",
                                                              ["engine", "vacuum", "radio", "roughness",
                                                               "alternator", "pitot", "attitude"])))
                        for k in link.EMERGENCIES}
        fu = ttk.Frame(g)
        fu.grid(row=7, column=0, columnspan=3, sticky="w")
        self.v_setfuel = tk.BooleanVar(value=c.get("set_fuel", False))
        ttk.Checkbutton(fu, text="Load the planned fuel into the aircraft", variable=self.v_setfuel).pack(side="left")
        self.l_fuelplan = ttk.Label(fu, text="", style="Muted.TLabel")
        self.l_fuelplan.pack(side="left", padx=8)
        pl = ttk.Frame(g)
        pl.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(pl, text="Payload (kg, 0 = leave alone):").pack(side="left")
        self.v_payload = tk.StringVar(value="0")
        ttk.Spinbox(pl, textvariable=self.v_payload, from_=0, to=20000, increment=25, width=7).pack(side="left", padx=4)
        self.l_payload = ttk.Label(pl, text="", style="Muted.TLabel")
        self.l_payload.pack(side="left", padx=6)
        g.columnconfigure(1, weight=1)

        # --- flight-plan file (.fms) options ---
        gf = ttk.LabelFrame(f, text="Flight plan file (.fms)", padding=6)
        gf.grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)
        self.v_fmssave = tk.BooleanVar(value=c.get("fms_save", True))
        self.v_fmsdir = tk.StringVar(value=c.get("fms_dir", ""))
        self.v_fmsname = tk.StringVar(value=c.get("fms_name", "IDEA_{from}_{to}"))
        ttk.Checkbutton(gf, text="Save a .fms file when I launch a flight", variable=self.v_fmssave,
                        command=self.update_fms_label).pack(side="left")
        ttk.Button(gf, text="Where and what name...", command=self.fms_options).pack(side="right")
        ttk.Button(gf, text="Save one now", command=lambda: self.save_fms(force=True)).pack(side="right", padx=4)
        self.l_fms = ttk.Label(f, text="", style="Muted.TLabel", wraplength=700, justify="left")
        self.l_fms.grid(row=6, column=0, columnspan=2, sticky="w")
        for v in (self.v_fmsdir, self.v_fmsname):
            v.trace_add("write", lambda *a: self.update_fms_label())

        b = ttk.Frame(f)
        b.grid(row=7, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(b, text="Launch flight in X-Plane", style="Big.TButton", command=self.launch).pack(side="left")
        ttk.Button(b, text="Send route to GPS only", command=self.send_route_only).pack(side="left", padx=6)
        ttk.Button(b, text="Stop monitor", command=self.stop_monitor).pack(side="left")
        ttk.Button(b, text="Repair failures", command=self.repair).pack(side="left", padx=6)
        self.v_live = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_live, font=MONO, foreground=self.theme.c["ok"]).grid(row=5, column=0, columnspan=2, sticky="w")
        self.v_live2 = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_live2, font=MONO, foreground=self.theme.c["warn"]).grid(row=6, column=0, columnspan=2,
                                                                                  sticky="w")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

    # ======================================================================
    # Helpers
    # ======================================================================
    def log(self, msg):
        self.q.put(("log", msg))

    def _pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.logtxt.insert("end", val + "\n")
                    self.logtxt.see("end")
                    self.v_status.set(val.strip())
                elif kind == "live":
                    self.v_live.set(val)
                elif kind == "live2":
                    self.v_live2.set(val)
                elif kind == "liveredraw":
                    self.debounce("liveredraw", self.draw_live, 400)
                elif kind == "call":
                    val()
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def ui(self, fn):
        self.q.put(("call", fn))

    def root(self):
        return Path(self.v_root.get().strip())

    def profile_key(self):
        if self.v_prof.get() == AUTO_PROF:
            return "auto:" + (self.selected_acf() or "?")
        name = self.v_prof.get()
        return next((k for k, p in core.AIRCRAFT.items() if p["name"] == name), "c172")

    def ac(self):
        """The performance profile in use (auto-read from the .acf, or a preset), with your edits applied."""
        key = self.profile_key()
        cache = getattr(self, "_prof_cache", None)
        if cache is None:
            cache = self._prof_cache = {}
        if key not in cache:
            if key.startswith("auto:"):
                rel = self.selected_acf()
                prof = xp_acf.profile_from_acf(self.root() / rel, rel) if rel else dict(core.AIRCRAFT["c172"])
            else:
                prof = dict(core.AIRCRAFT[key])
            prof.setdefault("glider", False)
            over = (self.cfg.get("profiles") or {}).get(key)
            if over:
                prof.update({k: (set(v) if k == "surfaces" else v) for k, v in over.items()})
            cache[key] = prof
        return cache[key]

    def on_profile(self):
        self._prof_cache = {}
        self._sc_key = self._ww_key = None
        self.gen = None
        a = self.ac()
        extra = xp_acf.summary(a) if a.get("acf") else (f"{a['cruise']} kt, ~{a['range']} nm, "
                                                       f"min runway {a['min_rwy']:,} ft")
        self.l_perf.config(text=extra)
        if hasattr(self, "plane_cap"):
            self.show_plane()

    def edit_profile(self):
        a = self.ac()
        key = self.profile_key()
        win = tk.Toplevel(self)
        win.title("Aircraft performance")
        win.transient(self)
        vs = {}
        fields = [("cruise", "Cruise speed (kt)"), ("range", "Range (nm)"), ("min_rwy", "Shortest runway (ft)"),
                  ("xwind", "Crosswind limit (kt)"), ("ceiling", "Ceiling (ft)")]
        for i, (k, lbl) in enumerate(fields):
            ttk.Label(win, text=lbl).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            v = tk.StringVar(value=str(a[k]))
            vs[k] = v
            ttk.Entry(win, textvariable=v, width=10).grid(row=i, column=1, sticky="w", padx=6)
        surf = {}
        r = len(fields)
        ttk.Label(win, text="Runway surfaces").grid(row=r, column=0, sticky="w", padx=6)
        for i, sname in enumerate(["paved", "grass", "dirt", "gravel", "snow", "lakebed"]):
            v = tk.BooleanVar(value=sname in a["surfaces"])
            surf[sname] = v
            ttk.Checkbutton(win, text=sname, variable=v).grid(row=r + 1 + i // 3, column=i % 3, sticky="w", padx=6)
        flags = {}
        r += 3
        for i, (k, lbl) in enumerate([("night", "night"), ("ifr", "IFR"), ("water", "floats"),
                                      ("heli", "helicopter"), ("multi", "multi-engine"), ("glider", "glider")]):
            v = tk.BooleanVar(value=bool(a.get(k)))
            flags[k] = v
            ttk.Checkbutton(win, text=lbl, variable=v).grid(row=r + i // 3, column=i % 3, sticky="w", padx=6)

        def save():
            over = {}
            for k, v in vs.items():
                try:
                    over[k] = int(float(v.get()))
                except ValueError:
                    pass
            over["surfaces"] = sorted(k for k, v in surf.items() if v.get())
            over.update({k: v.get() for k, v in flags.items()})
            profs = dict(self.cfg.get("profiles") or {})
            profs[key] = over
            self.cfg["profiles"] = profs
            core.save_config(profiles=profs)
            self._prof_cache = {}
            self.on_profile()
            win.destroy()

        def reset():
            profs = dict(self.cfg.get("profiles") or {})
            profs.pop(key, None)
            self.cfg["profiles"] = profs
            core.save_config(profiles=profs)
            self._prof_cache = {}
            self.on_profile()
            win.destroy()
        br = ttk.Frame(win)
        br.grid(row=r + 3, column=0, columnspan=3, sticky="e", pady=6, padx=6)
        ttk.Button(br, text="Reset to default", command=reset).pack(side="left", padx=4)
        ttk.Button(br, text="Save", command=save).pack(side="left")

    def api(self):
        return link.XPlaneAPI(self.v_host.get().strip() or "127.0.0.1", int(self.v_port.get() or 8086))

    def save_cfg(self):
        core.save_config(
            xplane_root=self.v_root.get(), acf=self.selected_acf(),
            profile="auto" if self.v_prof.get() == AUTO_PROF else self.profile_key(),
            country=self.v_country.get(), state=self.v_state.get(), **{"from": self.v_from.get()},
            area=self.area_key(), continent=self.v_continent.get(),
            near=self.v_near.get(), radius=self.num(self.v_radius, 150), max_leg=self.num(self.v_maxleg, 0),
            private=self.v_private.get(), missions=[k for k, v in self.v_miss.items() if v.get()],
            count=int(self.num(self.v_count, 8)), twist=int(self.v_twist.get()), custom=self.v_custom.get(),
            host=self.v_host.get(), port=int(self.num(self.v_port, 8086)), start=self.v_start.get(),
            engines=self.v_engines.get(), wxmode=self.v_wxmode.get(), loadroute=self.v_loadroute.get(),
            monitor=self.v_monitor.get(), photos=self.v_photos.get(), grade=self.v_grade.get(),
            wx_auto=self.v_wxauto.get(),
            wx_interval=self.num(self.v_wxint, 10), wx_kind=self.hazard_key(), wx_scope=self.v_wxscope.get(),
            wx_radius=self.num(self.v_wxrad, 300), wx_home=self.v_wxhome.get(), wx_usable=self.v_wxusable.get(),
            wx_area=self.v_wxarea.get(), wx_min=self.num(self.v_wxmin, 2), wx_goto=self.v_wxgoto.get(),
            sc_famous=self.v_scfam.get(), sc_gems=self.v_scgem.get(), sc_area=self.v_scarea.get(),
            sc_wonders=self.v_scwon.get(), sc_random=self.v_scrnd.get(),
            sc_tags=[k for k, v in self.v_sctags.items() if v.get()], sc_n=int(self.num(self.v_scn, 12)),
            insim=self.v_insim.get(), speak=self.v_speak.get(), knee=self.v_knee.get(),
            surprise=self.v_surprise.get(), sur_lo=self.num(self.v_sur_lo, 10), sur_hi=self.num(self.v_sur_hi, 40),
            terrain_online=self.v_dem.get(),
            fms_save=self.v_fmssave.get(), fms_dir=self.v_fmsdir.get(), fms_name=self.v_fmsname.get(),
            scenery_pref=self.v_scpref.get(), set_fuel=self.v_setfuel.get(),
            callsign=self.v_callsign.get(),
            emergencies=[k for k, v in self.v_emerg.items() if v.get()])

    @staticmethod
    def num(var, default):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _close(self):
        try:
            self.save_cfg()
        except Exception:
            pass
        self.stop_monitor()
        self.stop_grader(save=True)
        if getattr(self, "knee", None):
            try:
                self.knee.destroy()
            except Exception:
                pass
        self.destroy()

    # ======================================================================
    # X-Plane folder, aircraft
    # ======================================================================
    def browse_root(self):
        d = filedialog.askdirectory(title="Choose your X-Plane 12 folder")
        if d:
            self.v_root.set(d)
            self.load_xplane()

    def load_xplane(self, rebuild=False):
        root = self.root()
        if not core.is_xplane_root(root):
            messagebox.showerror("X-Plane", f"That doesn't look like an X-Plane folder:\n{root}")
            return
        self.v_status.set("Loading airports...")

        def work():
            try:
                aps = core.load_airports(root, rebuild, log=self.log)
                acfs = scan_aircraft(root)
                self.airports, self.acfs = aps, acfs
                self.log(f"{len(aps):,} airports and {len(acfs)} aircraft found.")
                self.ui(self.after_load)
            except Exception as e:
                self.log("Error loading X-Plane data: " + str(e))
                self.log(traceback.format_exc())
        threading.Thread(target=work, daemon=True).start()

    def after_load(self):
        core.save_config(xplane_root=str(self.root()))
        try:
            oa = self.ourairports()
            if oa.data:
                n = oa.enrich(self.airports, {k: v for k, v in COUNTRY_NAMES.items()})
                self.log(f"OurAirports: extra details for {n:,} airports "
                         f"(downloaded {oa.age_days():.0f} days ago).")
        except Exception as e:
            self.log(f"OurAirports: {e}")
        self.add_spots()
        self.scan_scenery(quiet=True)
        self.fill_countries()
        self.cb_acf["values"] = [acf_label(a) for a in self.acfs]
        want = self.cfg.get("acf")
        idx = self.acfs.index(want) if want in self.acfs else \
            next((i for i, a in enumerate(self.acfs) if "172" in a), 0 if self.acfs else -1)
        if idx >= 0:
            self.cb_acf.current(idx)
            self.on_acf(keep_profile=bool(want in self.acfs and self.cfg.get("profile")))
        self.update_plugin_label()
        self.update_fms_label()
        self.update_rules_label()
        self.v_status.set("Ready - pick your settings and press Generate ideas.")

    # ======================================================================
    # Your own landing spots
    # ======================================================================
    def spots(self):
        if not hasattr(self, "_spots"):
            self._spots = xp_radio.Spots(core.CACHE_DIR / "spots.json")
        return self._spots

    def add_spots(self):
        """Put your own spots into the airport list so everything else can use them."""
        if not self.airports:
            return
        self.airports = [a for a in self.airports if not a.get("spot")]
        extra = self.spots().as_airports()
        if extra:
            self.airports.extend(extra)
            self.log(f"{len(extra)} of your own landing spots added to the airport list.")
        self.gen = None

    def spots_window(self):
        sp = self.spots()
        win = tk.Toplevel(self)
        win.title("My landing spots")
        win.geometry(f"{self.theme.px(700)}x{self.theme.px(460)}")
        win.transient(self)
        self.theme.track(win, "window")
        ttk.Label(win, text="Places that aren't airports - gravel bars, meadows, ridges, oil rigs",
                  style="Head.TLabel").pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Label(win, text="The app treats these like tiny airports: they can be a destination, they go "
                            "into the route and the .fms as a lat/lon waypoint, and bush or helicopter "
                            "ideas can use them.",
                  style="MutedBg.TLabel", wraplength=self.theme.px(660), justify="left").pack(
            anchor="w", padx=12)
        cols = ("id", "name", "lat", "lon", "elev", "surface", "len")
        tv = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse", height=8)
        for col, h, w in zip(cols, ("Code", "Name", "Latitude", "Longitude", "Elev ft", "Surface", "Length ft"),
                             (70, 200, 90, 90, 70, 80, 80)):
            tv.heading(col, text=h)
            tv.column(col, width=w, anchor="w" if col in ("id", "name") else "center", stretch=col == "name")
        self.theme.fit_columns(tv)
        tv.pack(fill="both", expand=True, padx=8, pady=6)

        def fill():
            tv.delete(*tv.get_children())
            for x in sp.items:
                tv.insert("", "end", values=(x["id"], x["name"], f"{x['lat']:.5f}", f"{x['lon']:.5f}",
                                             f"{x['elev']:,}", x["surface"], f"{x['len']:,}" if x["len"] else "-"))
        fill()

        form = ttk.LabelFrame(win, text="Add a spot", padding=8)
        form.pack(fill="x", padx=8)
        v = {k: tk.StringVar() for k in ("name", "lat", "lon", "elev", "len", "notes")}
        v["surface"] = tk.StringVar(value="dirt")
        for i, (label, key, w) in enumerate([("Name:", "name", 22), ("Latitude:", "lat", 12),
                                             ("Longitude:", "lon", 12)]):
            ttk.Label(form, text=label).grid(row=0, column=i * 2, sticky="e", padx=(6, 2))
            ttk.Entry(form, textvariable=v[key], width=w).grid(row=0, column=i * 2 + 1, sticky="w")
        ttk.Label(form, text="Elevation ft:").grid(row=1, column=0, sticky="e", padx=(6, 2), pady=4)
        ttk.Entry(form, textvariable=v["elev"], width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(form, text="Surface:").grid(row=1, column=2, sticky="e", padx=(6, 2))
        ttk.Combobox(form, textvariable=v["surface"], width=10, state="readonly",
                     values=["dirt", "gravel", "grass", "snow", "lakebed", "water", "paved"]).grid(
            row=1, column=3, sticky="w")
        ttk.Label(form, text="Usable length ft:").grid(row=1, column=4, sticky="e", padx=(6, 2))
        ttk.Entry(form, textvariable=v["len"], width=8).grid(row=1, column=5, sticky="w")
        ttk.Label(form, text="Notes:").grid(row=2, column=0, sticky="e", padx=(6, 2))
        ttk.Entry(form, textvariable=v["notes"], width=60).grid(row=2, column=1, columnspan=5, sticky="ew", pady=4)

        def take_from_sim():
            try:
                api = self.api()
                lat = float(api.get("sim/flightmodel/position/latitude"))
                lon = float(api.get("sim/flightmodel/position/longitude"))
                elev = float(api.get("sim/flightmodel/position/elevation")) * 3.28084
                v["lat"].set(f"{lat:.5f}")
                v["lon"].set(f"{lon:.5f}")
                v["elev"].set(f"{elev:.0f}")
                if not v["name"].get():
                    v["name"].set("Where I am now")
            except Exception as e:
                messagebox.showinfo("Spots", f"Couldn't read your position from X-Plane:\n{e}")

        def add():
            try:
                lat, lon = float(v["lat"].get()), float(v["lon"].get())
            except ValueError:
                messagebox.showinfo("Spots", "Latitude and longitude need to be numbers, "
                                             "e.g. 44.91234 and -114.52100.")
                return
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                messagebox.showinfo("Spots", "That latitude/longitude isn't on Earth.")
                return
            sp.add(v["name"].get().strip() or "Spot", lat, lon, self.num(v["elev"], 0),
                   v["surface"].get(), self.num(v["len"], 0), v["notes"].get().strip())
            for k in ("name", "lat", "lon", "elev", "len", "notes"):
                v[k].set("")
            fill()
            self.add_spots()

        def remove():
            s2 = tv.selection()
            if not s2:
                return
            ident = tv.item(s2[0], "values")[0]
            item = next((x for x in sp.items if x["id"] == ident), None)
            if item and messagebox.askyesno("Spots", f"Remove '{item['name']}'?"):
                sp.remove(item)
                fill()
                self.add_spots()

        b = ttk.Frame(win, style="Bg.TFrame", padding=(12, 8))
        b.pack(fill="x")
        ttk.Button(b, text="Use my position in X-Plane", style="Quiet.TButton",
                   command=take_from_sim).pack(side="left")
        ttk.Button(b, text="Remove selected", style="Quiet.TButton", command=remove).pack(side="left", padx=6)
        ttk.Button(b, text="Add this spot", style="Big.TButton", command=add).pack(side="right")

    def choose_emergencies(self):
        win = tk.Toplevel(self)
        win.title("Which emergencies?")
        win.transient(self)
        self.theme.track(win, "window")
        ttk.Label(win, text="Tick what the surprise failure may pick from:", style="Head.TLabel").pack(
            anchor="w", padx=12, pady=(10, 4))
        body = ttk.Frame(win, padding=(8, 0))
        body.pack(fill="both", expand=True)
        items = list(link.EMERGENCIES.items())
        half = (len(items) + 1) // 2
        for col, chunk in enumerate((items[:half], items[half:])):
            box = ttk.Frame(body)
            box.grid(row=0, column=col, sticky="nw", padx=8)
            for k, (title, advice) in chunk:
                cb = ttk.Checkbutton(box, text=title, variable=self.v_emerg[k])
                cb.pack(anchor="w")
                Tooltip(cb, advice)
        foot = ttk.Frame(win, style="Bg.TFrame", padding=12)
        foot.pack(fill="x")
        ttk.Button(foot, text="All", style="Quiet.TButton",
                   command=lambda: [v.set(True) for v in self.v_emerg.values()]).pack(side="left")
        ttk.Button(foot, text="Engine only", style="Quiet.TButton",
                   command=lambda: [v.set(k in ("engine", "roughness")) for k, v in
                                    self.v_emerg.items()]).pack(side="left", padx=4)
        ttk.Button(foot, text="Instruments only", style="Quiet.TButton",
                   command=lambda: [v.set(k in ("vacuum", "pitot", "static", "asi", "attitude",
                                                "altimeter", "gyro", "gps")) for k, v in
                                    self.v_emerg.items()]).pack(side="left")
        ttk.Button(foot, text="Done", style="Big.TButton",
                   command=lambda: (self.save_cfg(), win.destroy())).pack(side="right")

    def emergency_pool(self):
        on = [k for k, v in self.v_emerg.items() if v.get()]
        return on or ["engine"]

    # ======================================================================
    # Scenery you have installed
    # ======================================================================
    def scenery(self):
        if not hasattr(self, "_sc_pack"):
            self._sc_pack = xp_scenery.Scenery(core.CACHE_DIR)
        return self._sc_pack

    def scan_scenery(self, quiet=False, force=False):
        sc = self.scenery()
        same_root = sc.root == str(self.root())
        if sc.packs and same_root and not force:
            self.update_scenery_label()
            return

        def work():
            try:
                sc.scan(self.root(), self.airports, log=(lambda m: None) if quiet else self.log)
                self.ui(lambda: (self.update_scenery_label(),
                                 None if quiet else self.log("Scenery scan: " + sc.summary_line())))
            except Exception as e:
                msg = str(e)
                self.ui(lambda: self.log(f"Couldn't read Custom Scenery: {msg}"))
        threading.Thread(target=work, daemon=True).start()

    def update_scenery_label(self):
        if hasattr(self, "l_scenery"):
            self.l_scenery.config(text=self.scenery().summary_line())

    def scenery_window(self):
        sc = self.scenery()
        win = tk.Toplevel(self)
        win.title("My scenery")
        win.geometry(f"{self.theme.px(760)}x{self.theme.px(520)}")
        win.transient(self)
        self.theme.track(win, "window")
        head = ttk.Frame(win, style="Bg.TFrame", padding=(12, 10, 12, 4))
        head.pack(fill="x")
        ttk.Label(head, text="Scenery you have installed", style="Head.TLabel").pack(side="left")
        ttk.Button(head, text="Rescan", style="Quiet.TButton",
                   command=lambda: (self.scan_scenery(force=True), win.destroy())).pack(side="right")
        ttk.Label(win, text=sc.summary_line(), style="MutedBg.TLabel").pack(anchor="w", padx=12)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        t1 = ttk.Frame(nb, padding=6)
        nb.add(t1, text="Packs")
        cols = ("pack", "kind", "n", "state")
        tv = ttk.Treeview(t1, columns=cols, show="headings", selectmode="browse")
        for col, h, w in zip(cols, ("Pack", "Kind", "Airports / tiles", "In use"), (330, 90, 120, 80)):
            tv.heading(col, text=h)
            tv.column(col, width=w, anchor="w" if col == "pack" else "center", stretch=col == "pack")
        self.theme.fit_columns(tv)
        sb = ttk.Scrollbar(t1, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        for name, info in sorted(sc.packs.items(), key=lambda kv: (kv[1]["kind"], kv[0].lower())):
            n = len(info.get("airports", [])) if info["kind"] == "airport" else info.get("tiles", 0)
            tv.insert("", "end", values=(name, info["kind"], f"{n:,}",
                                         "off" if info.get("disabled") else "yes"))

        t2 = ttk.Frame(nb, padding=6)
        nb.add(t2, text="Never flown there")
        visited = set()
        try:
            visited = {a for e in self.logbook.entries for a in e.get("route", [])}
        except Exception:
            pass
        never = sc.never_flown(visited)
        box = tk.Listbox(t2, exportselection=False)
        self.theme.track(box, "list")
        box.pack(fill="both", expand=True)
        for name, ids in never:
            box.insert("end", f"{name}   -   {', '.join(ids[:6])}{' ...' if len(ids) > 6 else ''}")
        if not never:
            box.insert("end", "Nothing to show - either you have flown into every add-on airport, "
                              "or there are no add-on airport packs.")

        def fly_it():
            s = box.curselection()
            if not s or not never:
                return
            ids = never[s[0]][1]
            self.v_custom.set(ids[0])
            win.destroy()
            self.open_picker()
        ttk.Button(t2, text="Show me one of these airports", style="Big.TButton",
                   command=fly_it).pack(anchor="e", pady=(6, 0))

    # ======================================================================
    # Wonders of the world
    # ======================================================================
    def _home_ref(self):
        """The airport we measure 'near me' from: the From box, the near box, or the current idea."""
        for ident in (self.v_from.get().strip(), self.v_near.get().strip()):
            if ident:
                a = next((x for x in self.airports if x["id"].upper() == ident.upper()), None)
                if a:
                    return a
        if self.idea:
            return self.idea.stops[0]
        return self.airports[0] if self.airports else None

    def wonders_near(self):
        """The 400-odd places worth looking at, sorted by how far they are from you."""
        try:
            finder = self.scenic_finder()
        except RuntimeError as e:
            messagebox.showinfo("Wonders", str(e))
            return
        home = self._home_ref()
        if not home:
            messagebox.showinfo("Wonders", "Airports are still loading - give it a moment.")
            return
        win = tk.Toplevel(self)
        win.title("Wonders of the world")
        win.geometry(f"{self.theme.px(940)}x{self.theme.px(580)}")
        win.transient(self)
        self.theme.track(win, "window")
        head = ttk.Frame(win, style="Bg.TFrame", padding=(12, 10, 12, 4))
        head.pack(fill="x")
        ttk.Label(head, text="Wonders of the world", style="Head.TLabel").pack(side="left")
        ttk.Label(head, text="   Measured from:", style="MutedBg.TLabel").pack(side="left")
        v_ref = tk.StringVar(value=home["id"])
        ttk.Entry(head, textvariable=v_ref, width=8).pack(side="left", padx=4)
        v_reach = tk.BooleanVar(value=True)
        ttk.Checkbutton(head, text="Only ones I can reach", variable=v_reach).pack(side="left", padx=8)
        lbl = ttk.Label(win, text="", style="MutedBg.TLabel")
        lbl.pack(anchor="w", padx=12)

        body = ttk.Frame(win, padding=(8, 6))
        body.pack(fill="both", expand=True)
        cols = ("name", "what", "dist")
        tv = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for col, h, w in zip(cols, ("Wonder", "What you're looking at", "Distance"), (210, 470, 90)):
            tv.heading(col, text=h)
            tv.column(col, width=w, anchor="w" if col in ("name", "what") else "e",
                      stretch=col == "what")
        self.theme.fit_columns(tv)
        sb = ttk.Scrollbar(body, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

        def fill():
            ident = v_ref.get().strip().upper()
            ref = next((x for x in self.airports if x["id"].upper() == ident), home)
            v_ref.set(ref["id"])
            reach = {c["title"] for c in finder.wonders()} if v_reach.get() else None
            tv.delete(*tv.get_children())
            rows = []
            for w in wonders.ALL:
                if reach is not None and w["name"] not in reach:
                    continue
                rows.append((wonders.nm(ref["lat"], ref["lon"], w["lat"], w["lon"]), w))
            rows.sort(key=lambda x: x[0])
            for d, w in rows:
                tv.insert("", "end", values=(w["name"], w["text"], f"{d:,.0f} nm"))
            near = sum(1 for d, _ in rows if d <= 300)
            lbl.config(text=f"{len(rows):,} places shown, {near} of them within 300 nm of {ref['id']}. "
                            f"Untick the box to see all {len(wonders.ALL):,}.")

        def use(setup):
            s = tv.selection()
            if not s:
                messagebox.showinfo("Wonders", "Pick one from the list first.")
                return
            name = tv.item(s[0], "values")[0]
            cand = next((c for c in finder.wonders() if c["title"] == name), None)
            if not cand:
                messagebox.showinfo("Wonders", f"There is no runway anywhere near {name} in your "
                                               f"scenery, so there's no flight to build.")
                return
            idea = finder.to_idea(cand)
            if not idea:
                messagebox.showinfo("Wonders", f"{name} is too far from the nearest usable runway for "
                                               f"this aeroplane. Try one with longer legs.")
                return
            win.destroy()
            self._add_idea(idea)
            self.nb.select(1 if setup else 0)

        ttk.Button(head, text="Refresh", style="Quiet.TButton", command=fill).pack(side="right")
        b = ttk.Frame(win, padding=(12, 0, 12, 10))
        b.pack(fill="x")
        ttk.Button(b, text="Open briefing", command=lambda: use(False)).pack(side="left")
        ttk.Button(b, text="Set up in X-Plane  >>", style="Big.TButton",
                   command=lambda: use(True)).pack(side="left", padx=6)
        ttk.Label(b, text="Most of these have no airport - the flight puts you over the top of it.",
                  style="Muted.TLabel").pack(side="right")
        tv.bind("<Double-1>", lambda e: use(False))
        fill()

    # ======================================================================
    # Area (Where)
    # ======================================================================
    def area_key(self):
        return next((k for k, v in AREAS.items() if v == self.v_area.get()), "country")

    def on_area(self):
        """Show only the boxes that matter for the chosen area."""
        a = self.area_key()
        rows = {"continent": [(self.wl_cont, self.cb_cont)],
                "country":   [(self.wl_country, self.cb_country)],
                "state":     [(self.wl_country, self.cb_country), (self.wl_state, self.cb_state)],
                "near":      [(self.wl_near, self.e_near), (self.wl_within, self.sp_radius)]}
        want = {id(w) for pair in rows.get(a, []) for w in pair if w is not None}
        for w in (self.wl_cont, self.cb_cont, self.wl_country, self.cb_country, self.wl_state,
                  self.cb_state, self.wl_near, self.e_near, self.wl_within, self.sp_radius):
            if id(w) in want:
                w.grid()
                try:
                    w.configure(state="readonly" if isinstance(w, ttk.Combobox) and w is self.cb_cont
                                else "normal")
                except tk.TclError:
                    pass
            else:
                w.grid_remove()
        if a == "state":
            self.on_country()

    def fill_countries(self):
        names, count = {}, {}
        for ap in self.airports or ():
            iso = ap.get("iso") or ("US" if core.is_us(ap) else "")
            if not iso:
                continue
            count[iso] = count.get(iso, 0) + 1
            if ap.get("country") and iso not in names:
                names[iso] = ap["country"]
        labels = sorted(f"{names.get(i) or COUNTRY_NAMES.get(i, i)} ({i})" for i in count)
        self.country_labels = labels
        self.cb_country["values"] = labels
        cur = self.v_country.get().strip()
        if len(cur) == 2:   # a bare code from an older version
            self.v_country.set(next((l for l in labels if l.endswith(f"({cur.upper()})")), cur))
        self.on_country()

    def country_iso(self):
        t = self.v_country.get().strip()
        m = re.search(r"\(([A-Za-z0-9]{2,3})\)\s*$", t)
        if m:
            return m.group(1).upper()
        if len(t) == 2 and t.isalpha():
            return t.upper()
        low = t.lower()
        for l in getattr(self, "country_labels", []):
            if l.lower().startswith(low) and low:
                return re.search(r"\(([A-Z0-9]{2,3})\)$", l).group(1)
        return ""

    def on_country(self):
        iso = self.country_iso()
        if not iso or not self.airports:
            return
        states = sorted({ap["state"] for ap in self.airports if ap.get("state") and
                         ((ap.get("iso") or ("US" if core.is_us(ap) else "")) == iso)})
        self.cb_state["values"] = states
        if self.v_state.get() and self.v_state.get() not in states:
            full = core.US_STATES.get(self.v_state.get().upper())
            self.v_state.set(full if full in states else "")

    def area_text(self):
        a = self.area_key()
        return {"world": "whole world", "continent": self.v_continent.get(), "country": self.v_country.get(),
                "state": f"{self.v_state.get()}, {self.v_country.get()}",
                "near": f"within {self.v_radius.get()} nm of {self.v_near.get().upper()}"}[a] + \
            (f", always departing {self.v_from.get().upper()}" if self.v_from.get().strip() else "")

    def selected_acf(self):
        i = self.cb_acf.current()
        return self.acfs[i] if 0 <= i < len(self.acfs) else None

    def on_acf(self, keep_profile=False):
        rel = self.selected_acf()
        if not rel:
            return
        lv = liveries(self.root(), rel)
        self.cb_livery["values"] = ["(default)"] + lv
        self.v_livery.set("(default)")
        self._prof_cache = {}
        self.gen = None
        self._sc_key = self._ww_key = None
        if not keep_profile and self.v_prof.get() != AUTO_PROF:
            self.v_prof.set(core.AIRCRAFT[core.guess_profile(rel)]["name"])
        self.on_profile()
        self.show_plane()

    # ======================================================================
    # Generating
    # ======================================================================
    def make_gen(self, seed):
        if not self.airports:
            raise RuntimeError("Airports are still loading - give it a moment.")
        area = self.area_key()
        iso = self.country_iso()
        opts = SimpleNamespace(
            from_=self.v_from.get().strip() or None,
            near=(self.v_near.get().strip() or None) if area == "near" else None,
            radius=self.num(self.v_radius, 150),
            state=(self.v_state.get().strip() or None) if area == "state" else None,
            country=iso if area in ("country", "state") else "ANY",
            continent=self.v_continent.get() if area == "continent" else None,
            include_private=self.v_private.get(), max_leg=self.num(self.v_maxleg, 0) or None)
        if area == "near" and not opts.near:
            raise RuntimeError("Type the airport to search near (Where > Near).")
        if area in ("country", "state") and not iso:
            raise RuntimeError("Pick a country (Where > Country).")
        opts.payload_capacity = xp_acf.payload_capacity_kg(self.ac())
        opts.scenery = self.scenery() if self.v_scpref.get() else None
        opts.scenery_pref = self.v_scpref.get()
        return core.Generator(self.airports, self.ac(), random.Random(seed), opts)

    def generate(self):
        kinds = [k for k, v in self.v_miss.items() if v.get()]
        if not kinds:
            messagebox.showinfo("Missions", "Tick at least one mission type.")
            return
        seed = int(self.v_seed.get()) if self.v_seed.get().strip().isdigit() else random.randrange(1_000_000)
        try:
            self.gen = self.make_gen(seed)
        except (KeyError, RuntimeError) as e:
            messagebox.showerror("Can't generate", str(e.args[0]))
            return
        self.log(f"Area: {self.area_text()}")
        if not self.gen.pool:
            messagebox.showerror("Can't generate", "No airports match that area for this aircraft.")
            return
        self.save_cfg()
        if "realwx" in kinds:
            if not self.metar_src.obs or (self.metar_src.age_min() or 999) > max(5, self.num(self.v_wxint, 10)):
                if not getattr(self, "_gen_waiting", False):
                    self._gen_waiting = True
                    self.refresh_weather(then=self._generate_after_wx)
                    return
            self.gen.metars = self.metar_src.obs
            self.gen.wx_kind = self.hazard_key()
        ideas = self.gen.generate(int(self.num(self.v_count, 8)), kinds, self.v_twist.get() / 100)
        if not ideas:
            messagebox.showinfo("No ideas", "Couldn't build ideas with those settings - try more mission types "
                                            "or a bigger area.")
            return
        self.ideas = ideas
        self.revealed.clear()
        self.lb.delete(0, "end")
        for i, idea in enumerate(ideas, 1):
            self.lb.insert("end", f"{i:2d}. {idea.title}")
        self.lb.selection_set(0)
        self.on_select()
        self.log(f"Generated {len(ideas)} ideas (seed {seed}, {len(self.gen.pool):,} usable airports).")

    def _generate_after_wx(self, ok):
        self._gen_waiting = False
        if not ok:
            self.log("Live weather unavailable - generating without the live-weather mission.")
            self.v_miss["realwx"].set(False)
        self.generate()

    # ======================================================================
    # Live weather
    # ======================================================================
    def _build_live(self, f):
        c = self.cfg
        self.metar_src = livewx.MetarSource(core.CACHE_DIR)
        self.wx_results = []
        self.wx_sel = None
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Button(top, text="Refresh weather", command=lambda: self.refresh_weather(force=True)).pack(side="left")
        self.v_wxauto = tk.BooleanVar(value=c.get("wx_auto", False))
        self.v_wxint = tk.StringVar(value=str(int(c.get("wx_interval", 10))))
        ttk.Checkbutton(top, text="Auto-refresh every", variable=self.v_wxauto,
                        command=self.schedule_weather).pack(side="left", padx=(10, 2))
        ttk.Spinbox(top, textvariable=self.v_wxint, from_=5, to=60, increment=5, width=4).pack(side="left")
        ttk.Label(top, text="min").pack(side="left")
        self.l_wxage = ttk.Label(top, text="", style="Muted.TLabel")
        self.l_wxage.pack(side="left", padx=10)
        ttk.Label(top, text="Source: aviationweather.gov (NOAA)", style="Muted.TLabel").pack(side="right")

        q = ttk.Frame(f)
        q.pack(fill="x", pady=6)
        ttk.Label(q, text="Look for:").pack(side="left")
        self.v_hazard = tk.StringVar(value=livewx.HAZARDS.get(c.get("wx_kind", "any"), livewx.HAZARDS["any"]))
        ttk.Combobox(q, textvariable=self.v_hazard, values=list(livewx.HAZARDS.values()), state="readonly",
                     width=38).pack(side="left", padx=4)
        self.v_wxscope = tk.StringVar(value=c.get("wx_scope", "near"))
        ttk.Radiobutton(q, text="within", value="near", variable=self.v_wxscope).pack(side="left", padx=(8, 0))
        self.v_wxrad = tk.StringVar(value=str(int(c.get("wx_radius", 300))))
        ttk.Spinbox(q, textvariable=self.v_wxrad, from_=25, to=2000, increment=25, width=5).pack(side="left")
        ttk.Label(q, text="nm of").pack(side="left")
        self.v_wxhome = tk.StringVar(value=c.get("wx_home", "") or c.get("from", "") or c.get("near", ""))
        ttk.Entry(q, textvariable=self.v_wxhome, width=7).pack(side="left", padx=2)
        ttk.Radiobutton(q, text="my region", value="region", variable=self.v_wxscope).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(q, text="worldwide:", value="world", variable=self.v_wxscope).pack(side="left", padx=(8, 0))
        self.v_wxarea = tk.StringVar(value=c.get("wx_area", "Whole world"))
        ttk.Combobox(q, textvariable=self.v_wxarea, values=list(livewx.CONTINENTS), state="readonly",
                     width=24).pack(side="left", padx=2)
        ttk.Button(q, text="Find", style="Big.TButton", command=self.find_weather).pack(side="right")
        q2 = ttk.Frame(f)
        q2.pack(fill="x")
        self.v_wxusable = tk.BooleanVar(value=c.get("wx_usable", True))
        ttk.Checkbutton(q2, text="Only airports my plane can use", variable=self.v_wxusable).pack(side="left")
        ttk.Label(q2, text="   Minimum severity:").pack(side="left")
        self.v_wxmin = tk.StringVar(value=f'{c.get("wx_min", 2):g}')
        ttk.Spinbox(q2, textvariable=self.v_wxmin, from_=0.5, to=10, increment=0.5, width=4).pack(side="left")
        ttk.Label(q2, text="(higher = only the worst)", style="Muted.TLabel").pack(side="left", padx=4)

        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)
        lf = ttk.Frame(body)
        cols = ("apt", "name", "where", "dist", "cat", "wind", "vis", "ceil", "wx", "score")
        heads = ("Airport", "Name", "Where", "nm", "Cat", "Wind", "Vis", "Ceiling", "Weather", "Score")
        widths = (68, 170, 90, 45, 50, 90, 45, 68, 80, 52)
        self.tv = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
        for col, h, w in zip(cols, heads, widths):
            self.tv.heading(col, text=h, command=lambda c=col: self.sort_weather(c))
            self.tv.column(col, width=w, anchor="w" if col in ("apt", "name", "wind", "wx") else "center",
                           stretch=col == "name")
        for cat, colr in livewx.CAT_COLOR.items():
            if cat:
                self.tv.tag_configure(cat, foreground=colr)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.theme.fit_columns(self.tv)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.on_wx_select())
        self.tv.bind("<Double-1>", lambda e: self.wx_make_idea(False))
        rf = ttk.PanedWindow(body, orient="vertical")
        mf = ttk.Frame(rf)
        self.wx_cv = tk.Canvas(mf, width=self.theme.px(380), height=self.theme.px(220), background="#eef1f3")
        self.theme.track(self.wx_cv, "canvas")
        self.wx_cv.pack(fill="both", expand=True)
        rf.add(mf, weight=3)
        nf = ttk.Frame(rf)
        rf.add(nf, weight=2)
        nh = ttk.Frame(nf)
        nh.pack(fill="x")
        ttk.Label(nh, text="Airports near the weather (your plane can use) - pick one:",
                  style="Head.TLabel").pack(side="left")
        self.v_nearnm = tk.StringVar(value="60")
        ttk.Label(nh, text="nm").pack(side="right")
        sp = ttk.Spinbox(nh, textvariable=self.v_nearnm, from_=10, to=200, increment=10, width=4,
                         command=lambda: self.fill_nearby())
        sp.pack(side="right")
        sp.bind("<Return>", lambda e: self.fill_nearby())
        ttk.Label(nh, text="within").pack(side="right")
        ncols = ("apt", "name", "nm", "cat", "rwy")
        self.tv_near = ttk.Treeview(nf, columns=ncols, show="headings", selectmode="browse", height=6)
        for col, h, w in zip(ncols, ("Airport", "Name", "nm", "Weather", "Longest runway"), (62, 150, 40, 60, 120)):
            self.tv_near.heading(col, text=h)
            self.tv_near.column(col, width=w, anchor="w" if col in ("apt", "name", "rwy") else "center",
                                stretch=col == "name")
        for cat, colr in livewx.CAT_COLOR.items():
            if cat:
                self.tv_near.tag_configure(cat, foreground=colr)
        self.theme.fit_columns(self.tv_near)
        self.tv_near.pack(fill="both", expand=True)
        self.tv_near.bind("<Double-1>", lambda e: self.wx_make_idea(False, use_nearby=True))
        nb2 = ttk.Frame(nf)
        nb2.pack(fill="x", pady=(3, 0))
        ttk.Button(nb2, text="Fly from here INTO it >>",
                   command=lambda: self.wx_make_idea(False, use_nearby=True)).pack(side="left")
        ttk.Button(nb2, text="Take off IN it, land here >>",
                   command=lambda: self.wx_make_idea(True, use_nearby=True)).pack(side="left", padx=4)
        self.near_list = []
        self.wx_cv.bind("<Configure>", lambda e: self.debounce("wxmap", self.draw_wx_map, 150))
        body.add(lf, weight=3)
        body.add(rf, weight=2)

        bot = ttk.Frame(f)
        bot.pack(fill="x", pady=(6, 0))
        self.l_metar = ttk.Label(bot, text="Pick a row to see its METAR.", font=MONO, wraplength=900, justify="left")
        self.l_metar.pack(anchor="w")
        self.l_alts = ttk.Label(bot, text="", style="Muted.TLabel", wraplength=900, justify="left")
        self.l_alts.pack(anchor="w")
        b = ttk.Frame(bot)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Set up a flight INTO this weather  >>", style="Big.TButton",
                   command=lambda: self.wx_make_idea(False)).pack(side="left")
        ttk.Button(b, text="Take off IN this weather  >>", style="Big.TButton",
                   command=lambda: self.wx_make_idea(True)).pack(side="left", padx=6)
        self.v_wxgoto = tk.BooleanVar(value=c.get("wx_goto", True))
        ttk.Checkbutton(b, text="then open the 'Fly it' tab", variable=self.v_wxgoto).pack(side="left", padx=6)
        ttk.Label(b, text="Tip: tick 'realwx' under Mission types to mix these into Generate ideas.",
                  style="Muted.TLabel").pack(side="right")
        self.update_wx_age()
        self.after(1500, self.schedule_weather)

    def hazard_key(self):
        return next((k for k, v in livewx.HAZARDS.items() if v == self.v_hazard.get()), "any")

    def update_wx_age(self):
        a = self.metar_src.age_min()
        self.l_wxage.config(text="no weather downloaded yet" if a is None else
                            f"{len(self.metar_src.obs):,} reports, {a:.0f} min old")

    def refresh_weather(self, force=False, then=None):
        self.l_wxage.config(text="downloading weather...")
        self.log("Downloading current METARs from aviationweather.gov...")

        def work():
            try:
                n = self.metar_src.refresh(force=force)
                ok, msg = True, f"Live weather: {n:,} METARs."
            except Exception as e:
                ok, msg = False, f"Live weather failed: {e}"
            self.log(msg)

            def done():
                self.update_wx_age()
                if ok and self.wx_results:
                    self.find_weather(quiet=True)
                if then:
                    then(ok)
            self.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def schedule_weather(self):
        job = getattr(self, "_wx_job", None)
        if job:
            self.after_cancel(job)
            self._wx_job = None
        if self.v_wxauto.get():
            mins = max(5, self.num(self.v_wxint, 10))
            age = self.metar_src.age_min()
            if age is None or age >= mins:
                self.refresh_weather(force=True)
            self._wx_job = self.after(int(mins * 60000), self.schedule_weather)
        self.update_wx_age()

    def find_weather(self, quiet=False):
        if not self.metar_src.obs:
            self.refresh_weather(then=lambda ok: ok and self.find_weather())
            return
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
        except (KeyError, RuntimeError) as e:
            if not quiet:
                messagebox.showerror("Live weather", str(e.args[0]))
            return
        home = None
        maxnm = None
        scope = self.v_wxscope.get()
        gen = self.gen
        obs = self.metar_src.obs
        if scope == "world":
            key = (self.profile_key(), self.v_private.get())
            if getattr(self, "_ww_key", None) != key:
                opts = SimpleNamespace(from_=None, near=None, radius=0, state=None, country="ANY",
                                       include_private=self.v_private.get(), max_leg=None)
                self._ww_gen = core.Generator(self.airports, self.ac(), random.Random(), opts)
                self._ww_key = key
            gen = self._ww_gen
            area = self.v_wxarea.get()
            obs = [o for o in obs if livewx.in_area(o, area)]
        elif scope == "near":
            home = self.gen.find(self.v_wxhome.get())
            if not home:
                if not quiet:
                    messagebox.showinfo("Live weather", "Type the airport to search around (e.g. your home field), "
                                                        "or choose 'anywhere in my region'.")
                return
            maxnm = self.num(self.v_wxrad, 300)
        kind = self.hazard_key()
        usable = self.v_wxusable.get()
        minsc = self.num(self.v_wxmin, 2)
        self.wx_gen = gen
        self.l_wxage.config(text="searching...")

        def work():
            try:
                res = livewx.find_bad_weather(obs, gen, kind, home=home, max_nm=maxnm, usable_only=usable,
                                              min_score=minsc, limit=300)
                err = None
            except Exception as e:
                res, err = [], e
            self.ui(lambda: self._show_weather(res, home, err))
        threading.Thread(target=work, daemon=True).start()

    def _show_weather(self, res, home, err):
        self.update_wx_age()
        if err:
            self.log(f"Weather search failed: {err}")
            return
        self.wx_results, self.wx_home = res, home
        self._fill_wx_table()
        where = (f" within {self.v_wxrad.get()} nm of {home['id']}." if home else
                 f" - {self.v_wxarea.get().lower()}." if self.v_wxscope.get() == "world" else " in your region.")
        self.log(f"Found {len(res)} airports with {self.v_hazard.get().lower()}{where}")
        if res:
            first = self.tv.get_children()[0]
            self.tv.selection_set(first)
            self.tv.see(first)
        else:
            self.wx_sel = None
            self.fill_nearby()
            self.l_metar.config(text="Nothing that bad right now - try 'Any bad weather', a bigger radius, or later.")
            self.l_alts.config(text="")
            self.draw_wx_map()

    def _fill_wx_table(self):
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(self.wx_results):
            o, a = r["obs"], r["apt"]
            wind = ("VRB" if o.get("wdir") is None else f"{o['wdir']:03.0f}") + f"@{o.get('wspd') or 0:.0f}" + \
                (f"G{o['wgst']:.0f}" if o.get("wgst") else "") if (o.get("wspd") or 0) > 0 else "calm"
            vis = "" if o.get("vis") is None else f"{o['vis']:g}"
            ceil = "" if o.get("ceiling") is None else f"{o['ceiling']:,.0f}"
            dist = f"{r['home_dist']:.0f}" if r.get("home_dist") is not None else ""
            name = a["name"] + (f"  (METAR {o['id']}, {r['apt_dist']:.0f} nm)" if o["id"] != a["id"] else "")
            where = a.get("state") or a.get("iso") or a.get("city") or ""
            self.tv.insert("", "end", iid=str(i), values=(a["id"], name, where, dist, o.get("cat") or "", wind, vis, ceil,
                                                          o.get("wx") or ("CB" if o.get("cb") else ""), r["score"]),
                           tags=(o.get("cat") or "",))

    def sort_weather(self, col):
        key = {"apt": lambda r: r["apt"]["id"], "name": lambda r: r["apt"]["name"],
               "where": lambda r: r["apt"].get("state") or r["apt"].get("iso") or "",
               "dist": lambda r: r.get("home_dist") or 0, "cat": lambda r: r["obs"].get("cat") or "",
               "wind": lambda r: -(max(r["obs"].get("wspd") or 0, r["obs"].get("wgst") or 0)),
               "vis": lambda r: r["obs"].get("vis") if r["obs"].get("vis") is not None else 99,
               "ceil": lambda r: r["obs"].get("ceiling") if r["obs"].get("ceiling") is not None else 99999,
               "wx": lambda r: r["obs"].get("wx") or "", "score": lambda r: -r["score"]}[col]
        self.wx_results.sort(key=key)
        self._fill_wx_table()

    def on_wx_select(self):
        sel = self.tv.selection()
        if not sel:
            return
        r = self.wx_results[int(sel[0])]
        self.wx_sel = r
        o = r["obs"]
        self.l_metar.config(text=o.get("raw") or livewx.describe(o))
        alts = ", ".join(f"{a['id']} ({d:.0f} nm)" for d, a in r["alts"])
        self.l_alts.config(text=f"{r['apt']['name']}: {livewx.describe(o)}.   Other airports close by: {alts or 'none'}")
        self.draw_wx_map()
        self.fill_nearby()

    def fill_nearby(self):
        r = self.wx_sel
        self.tv_near.delete(*self.tv_near.get_children())
        self.near_list = []
        if not r:
            return
        g = getattr(self, "wx_gen", None) or self.gen
        if not g:
            return
        grid = getattr(self, "_near_grid", None)
        if grid is None or grid[0] is not g or grid[3] != self.metar_src.fetched:
            grid = (g, livewx.Grid(g.pool), livewx.Grid(self.metar_src.obs), self.metar_src.fetched)
            self._near_grid = grid
        rad = self.num(self.v_nearnm, 60)
        bad = r["apt"]
        for dd, a in grid[1].near(bad["lat"], bad["lon"], rad)[:60]:
            ob = livewx.nearest_obs(grid[2], a["lat"], a["lon"], 25)
            cat = (ob.get("cat") or "") if ob else ""
            rws = [x for x in g.usable(a) if x["s"] != "helipad"]
            rw = max(rws, key=lambda x: x["len"]) if rws else None
            self.near_list.append(a)
            self.tv_near.insert("", "end", iid=str(len(self.near_list) - 1),
                                values=(a["id"], a["name"] + ("  (the weather airport)" if a is bad else ""),
                                        f"{dd:.0f}", cat or "?", f"{rw['len']:,} ft {rw['s']}" if rw else "helipad"),
                                tags=(cat,))
        kids = self.tv_near.get_children()
        pick = next((k for k in kids if self.near_list[int(k)] is not bad and
                     self.tv_near.item(k)["values"][3] in ("VFR", "MVFR")), None) or (kids[1] if len(kids) > 1 else None)
        if pick:
            self.tv_near.selection_set(pick)
            self.tv_near.see(pick)

    def dangerous_weather(self):
        """One click: worldwide, any hazard, only the worst."""
        self.v_wxscope.set("world")
        self.v_wxarea.set("Whole world")
        self.v_hazard.set(livewx.HAZARDS["any"])
        self.v_wxmin.set("6")
        self.nb.select(self.tab_wx)
        age = self.metar_src.age_min()
        if age is None or age > max(5, self.num(self.v_wxint, 10)):
            self.refresh_weather(force=True, then=lambda ok: ok and self.find_weather())
        else:
            self.find_weather()

    def draw_wx_map(self):
        if not hasattr(self, "wx_cv"):
            return
        home = getattr(self, "wx_home", None)
        rad = self.num(self.v_wxrad, 300) if home else 300
        pics.draw_wx_map(self.wx_cv, self.metar_src.obs, self.wx_results, center=home, radius_nm=rad,
                         selected=self.wx_sel, home=home)

    def wx_make_idea(self, depart_here, use_nearby=False):
        r = self.wx_sel
        if not r:
            messagebox.showinfo("Live weather", "Pick an airport in the list first.")
            return
        other = None
        if use_nearby:
            sel = self.tv_near.selection()
            if not sel:
                messagebox.showinfo("Live weather", "Pick one of the nearby airports first.")
                return
            other = self.near_list[int(sel[0])]
            if other is r["apt"]:
                messagebox.showinfo("Live weather", "That's the weather airport itself - pick a different one "
                                                    "to fly from or to.")
                return
        g = getattr(self, "wx_gen", None) or self.gen
        g.metars = self.metar_src.obs
        g.wx_kind = self.hazard_key()
        g._obs_grid = None
        keep = g.fixed_home
        home = getattr(self, "wx_home", None)
        if home and not depart_here and home["id"] != r["apt"]["id"]:
            g.fixed_home = home
        try:
            idea = g.m_realwx(pick=r, depart_here=depart_here, other=other)
        finally:
            g.fixed_home = keep
        if not idea:
            messagebox.showinfo("Live weather", "Couldn't find a sensible second airport for that one.")
            return
        if self.v_twist.get() and g.rng.random() < self.v_twist.get() / 100:
            idea.twist, idea.failure = g.twist(idea)
        self.ideas.append(idea)
        self.lb.insert("end", f"{len(self.ideas):2d}. {idea.title}")
        self.lb.selection_clear(0, "end")
        self.lb.selection_set("end")
        self.lb.see("end")
        self.on_select()
        self.nb.select(1 if self.v_wxgoto.get() else 0)
        self.log(f"New flight: {idea.title}. Weather set to X-Plane real-world weather and your computer's clock "
                 f"- change it on the 'Fly it' tab if you like.")

    # ======================================================================
    # Scenic world
    # ======================================================================
    def _build_scenic(self, f):
        c = self.cfg
        r1 = ttk.Frame(f)
        r1.pack(fill="x")
        ttk.Label(r1, text="Pick from:").pack(side="left")
        self.v_scfam = tk.BooleanVar(value=c.get("sc_famous", True))
        self.v_scgem = tk.BooleanVar(value=c.get("sc_gems", True))
        self.v_scwon = tk.BooleanVar(value=c.get("sc_wonders", True))
        self.v_scrnd = tk.BooleanVar(value=c.get("sc_random", False))
        ttk.Checkbutton(r1, text="Famous routes", variable=self.v_scfam).pack(side="left", padx=4)
        ttk.Checkbutton(r1, text=f"Natural wonders ({len(wonders.ALL)})",
                        variable=self.v_scwon).pack(side="left", padx=4)
        ttk.Checkbutton(r1, text="Hidden gems in your scenery", variable=self.v_scgem).pack(side="left", padx=4)
        ttk.Checkbutton(r1, text="Random places", variable=self.v_scrnd).pack(side="left", padx=4)
        ttk.Label(r1, text="   Where:").pack(side="left")
        self.v_scarea = tk.StringVar(value=c.get("sc_area", "Whole world"))
        ttk.Combobox(r1, textvariable=self.v_scarea, values=list(core.CONTINENTS), state="readonly",
                     width=20).pack(side="left", padx=4)
        r2 = ttk.Frame(f)
        r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="Scenery:").grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 6))
        chosen = set(c.get("sc_tags", list(scenic.TAGS)))
        self.v_sctags = {}
        per = 5
        for i, (k, lbl) in enumerate(scenic.TAGS.items()):
            v = tk.BooleanVar(value=k in chosen)
            self.v_sctags[k] = v
            ttk.Checkbutton(r2, text=lbl, variable=v).grid(row=i // per, column=1 + i % per,
                                                           sticky="w", padx=2)
        for col in range(1, per + 1):
            r2.columnconfigure(col, weight=1)
        r3 = ttk.Frame(f)
        r3.pack(fill="x", pady=(2, 6))
        ttk.Button(r3, text="Surprise me!", style="Big.TButton", command=self.scenic_surprise).pack(side="left")
        ttk.Button(r3, text="Anywhere on earth", style="Big.TButton",
                   command=self.anywhere).pack(side="left", padx=(6, 0))
        ttk.Button(r3, text="Show me", command=self.scenic_list).pack(side="left", padx=(10, 2))
        self.v_scn = tk.StringVar(value=str(c.get("sc_n", 12)))
        ttk.Spinbox(r3, textvariable=self.v_scn, from_=1, to=50, width=4).pack(side="left")
        ttk.Label(r3, text="ideas").pack(side="left")
        ttk.Button(r3, text="All scenery", command=lambda: [v.set(True) for v in self.v_sctags.values()]).pack(side="left", padx=(12, 2))
        ttk.Button(r3, text="None", command=lambda: [v.set(False) for v in self.v_sctags.values()]).pack(side="left")
        self.l_sc = ttk.Label(r3, text="Uses the plane on the left; 'Where' on the left is ignored here.", style="Muted.TLabel")
        self.l_sc.pack(side="right")
        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)
        lf = ttk.Frame(body)
        self.sc_lb = tk.Listbox(lf, exportselection=False)
        self.theme.track(self.sc_lb, "list")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.sc_lb.yview)
        self.sc_lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.sc_lb.pack(fill="both", expand=True)
        self.sc_lb.bind("<<ListboxSelect>>", lambda e: self.scenic_preview())
        self.sc_lb.bind("<Double-1>", lambda e: self.scenic_use(False))
        rf = ttk.Frame(body)
        self.sc_cv = tk.Canvas(rf, width=self.theme.px(420), height=self.theme.px(260), background="#e9eef1")
        self.theme.track(self.sc_cv, "canvas")
        self.sc_cv.pack(fill="both", expand=True)
        self.sc_cv.bind("<Configure>", lambda e: self.debounce("scmap", self.scenic_preview, 150))
        self.sc_txt = tk.Label(rf, text="", justify="left", anchor="nw", wraplength=420)
        self.sc_txt.pack(fill="x", pady=4)
        body.add(lf, weight=2)
        body.add(rf, weight=3)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(4, 0))
        ttk.Button(b, text="Open briefing", command=lambda: self.scenic_use(False)).pack(side="left")
        ttk.Button(b, text="Set up in X-Plane  >>", style="Big.TButton",
                   command=lambda: self.scenic_use(True)).pack(side="left", padx=6)
        self.sc_ideas = []

    def scenic_finder(self):
        if not self.airports:
            raise RuntimeError("Airports are still loading - give it a moment.")
        key = (self.profile_key(), self.v_private.get(), id(self.airports))
        if getattr(self, "_sc_key", None) != key:
            self._sc = scenic.ScenicFinder(core, self.airports, self.ac(), random.Random(), self.v_private.get())
            self._sc_key = key
        return self._sc

    def _scenic_run(self, n, then, force_random=False):
        tags = [k for k, v in self.v_sctags.items() if v.get()]
        if not tags:
            messagebox.showinfo("Scenic world", "Tick at least one kind of scenery.")
            return
        if len(tags) == len(self.v_sctags):
            tags = None                      # everything ticked means "don't filter"
        area = self.v_scarea.get()
        fam = self.v_scfam.get() and not force_random
        gem = self.v_scgem.get() and not force_random
        won = self.v_scwon.get() and not force_random
        rnd = self.v_scrnd.get() or force_random
        if not (fam or gem or won or rnd):
            messagebox.showinfo("Scenic world", "Tick at least one source to pick from.")
            return
        try:
            finder = self.scenic_finder()
        except RuntimeError as e:
            messagebox.showinfo("Scenic world", str(e))
            return
        first = finder._gems is None and gem
        self.l_sc.config(text="Searching your scenery for hidden gems (first time only)..." if first else "Searching...")
        self.save_cfg()

        def work():
            try:
                ideas, err = finder.surprise(n, tags, area, fam, gem, won, rnd), None
            except Exception as e:
                ideas, err = [], e
                self.log(traceback.format_exc())
            self.ui(lambda: then(ideas, err))
        threading.Thread(target=work, daemon=True).start()

    def anywhere(self):
        """Throw a dart at the planet. No lists, no filters - just somewhere."""
        def done(ideas, err):
            self.l_sc.config(text="")
            if err or not ideas:
                messagebox.showinfo("Anywhere on earth",
                                    f"Nothing found ({err})" if err else
                                    "Nothing matched - try 'Whole world', or tick more scenery types.")
                return
            self._add_idea(ideas[0])
            self.nb.select(0)
            self.log(f"Anywhere on earth: {ideas[0].title}")
        self._scenic_run(1, done, force_random=True)

    def scenic_surprise(self):
        def done(ideas, err):
            self.l_sc.config(text="")
            if err or not ideas:
                messagebox.showinfo("Scenic world", f"Nothing found ({err})" if err else
                                    "Nothing matched - try more scenery types or 'Whole world'.")
                return
            self._add_idea(ideas[0])
            self.nb.select(0)
            self.log(f"Scenic surprise: {ideas[0].title}")
        self._scenic_run(1, done)

    def scenic_list(self):
        def done(ideas, err):
            self.sc_ideas = ideas
            self.sc_lb.delete(0, "end")
            for i in ideas:
                a = i.stops[-1]
                where = a.get("country") or a.get("state") or a.get("iso") or scenic.continent_of(a)
                self.sc_lb.insert("end", f"{i.title}  -  {where}")
            self.l_sc.config(text=f"{len(ideas)} ideas" if not err else f"Error: {err}")
            if ideas:
                self.sc_lb.selection_set(0)
                self.scenic_preview()
        self._scenic_run(int(self.num(self.v_scn, 12)), done)

    def _sc_sel(self):
        s = self.sc_lb.curselection()
        return self.sc_ideas[s[0]] if s and s[0] < len(self.sc_ideas) else None

    def scenic_preview(self):
        i = self._sc_sel()
        if not i:
            return
        pics.draw_route_map(self.sc_cv, i.stops, self.airports or (), title=i.title)
        extra = [n for n in i.notes if n.startswith(("Where", "Scenery", "Your plane", "The sight",
                                                     "High ground", "This one tops"))]
        self.sc_txt.config(text=i.mission + "\n\n" + "\n".join(extra) +
                           f"\n\nSuggested: {i.when_text()}, {i.wx.sky_text.lower()}")

    def scenic_use(self, setup):
        i = self._sc_sel()
        if not i:
            messagebox.showinfo("Scenic world", "Press 'Show me' and pick one first.")
            return
        self._add_idea(i)
        self.nb.select(1 if setup else 0)

    def _add_idea(self, idea):
        if not self.gen:
            try:
                self.gen = self.make_gen(random.randrange(1_000_000))
            except (KeyError, RuntimeError):
                self.gen = self.scenic_finder().gen
        if idea not in self.ideas:
            self.ideas.append(idea)
            self.lb.insert("end", f"{len(self.ideas):2d}. {idea.title}")
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(self.ideas.index(idea))
        self.lb.see(self.ideas.index(idea))
        self.on_select()

    def custom_route(self):
        ids = self.v_custom.get().replace(",", " ").replace("-", " ").split()
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
            idea = self.gen.custom(ids)
        except (KeyError, ValueError, RuntimeError) as e:
            messagebox.showerror("Custom route", str(e.args[0]))
            return
        self.ideas.append(idea)
        self.lb.insert("end", f"{len(self.ideas):2d}. {idea.title}")
        self.lb.selection_clear(0, "end")
        self.lb.selection_set("end")
        self.on_select()

    # ======================================================================
    # Showing an idea
    # ======================================================================
    def on_select(self):
        sel = self.lb.curselection()
        if not sel:
            return
        self.idea = self.ideas[sel[0]]
        self.show_brief()
        self.fill_launch()
        self.show_pictures()

    def brief_tags(self):
        """(Re)define the text styles used by the briefing."""
        t, th = self.txt, self.theme
        c, fam = th.c, th.family
        t.tag_configure("h1", font=(fam, 14, "bold"), foreground=c["text"], spacing1=2, spacing3=4)
        t.tag_configure("sub", font=(fam, 9), foreground=c["muted"], spacing3=10)
        t.tag_configure("label", font=(fam, 9, "bold"), foreground=c["muted"], spacing1=8, spacing3=2)
        t.tag_configure("body", font=(fam, 10), foreground=c["text"], lmargin1=2, lmargin2=2, spacing3=3)
        t.tag_configure("stop", font=(fam, 10, "bold"), foreground=c["text"], spacing1=4)
        t.tag_configure("stoptag", font=(fam, 9, "bold"), foreground=c["accent"])
        t.tag_configure("small", font=(fam, 9), foreground=c["muted"], lmargin1=16, lmargin2=16)
        t.tag_configure("leg", font=(fam, 9), foreground=c["accent"], lmargin1=16, lmargin2=16, spacing3=2)
        t.tag_configure("note", font=(fam, 10), foreground=c["text"], lmargin1=16, lmargin2=16, spacing3=3)
        t.tag_configure("twist", font=(fam, 10, "bold"), foreground=c["warn"], lmargin1=16, lmargin2=16,
                        spacing1=6, spacing3=4)
        t.tag_configure("total", font=(fam, 10, "bold"), foreground=c["text"], spacing1=6)
        t.tag_configure("mono", font=th.mono, foreground=c["text"])
        t.tag_configure("scenery", font=(fam, 9), foreground=c["ok"], lmargin1=16, lmargin2=16)
        for name, col in (("ok", c["ok"]), ("bad", c["bad"]), ("accent", c["accent"]), ("lifr", c["lifr"])):
            t.tag_configure(name, foreground=col, font=(fam, 10, "bold"))

    def show_brief(self):
        idea, ac = self.idea, self.ac()
        reveal = id(idea) in self.revealed
        t = self.txt
        t.config(state="normal")
        t.delete("1.0", "end")
        self.brief_tags()

        def line(text, *tags):
            t.insert("end", text + "\n", tags or ("body",))

        line(idea.title, "h1")
        line(f"{core.MISSIONS[idea.kind]}   \u00b7   {ac['name']}", "sub")

        stops = idea.stops
        if idea.hidden and not reveal:
            a = stops[0]
            line("DEPART", "label")
            line(f"{a['id']}  {a['name']}  ({a['elev']:,} ft)", "stop")
            line(core.rwy_list(a), "small")
        else:
            line("ROUTE", "label")
            total = 0
            for j, a in enumerate(stops):
                tag = ("Depart" if j == 0 else "Arrive" if j == len(stops) - 1 else
                       "Overfly" if a["id"] in getattr(idea, "overfly", ()) else f"Stop {j}")
                extra = []
                if a["tower"]:
                    extra.append("towered")
                if a.get("ils"):
                    extra.append("ILS " + ",".join(a["ils"]))
                loc = ", ".join(x for x in (a.get("city"), a.get("state")) if x)
                t.insert("end", f"{tag}   ", "stoptag")
                t.insert("end", f"{a['id']}  {a['name']}", "stop")
                t.insert("end", f"   {a['elev']:,} ft{'  ' + loc if loc else ''}\n", "small")
                if a.get("wonder"):
                    line(a.get("notes") or "A position, not an airport - fly over it.", "small")
                else:
                    line(core.rwy_list(a) + ("   [" + ", ".join(extra) + "]" if extra else ""), "small")
                sc_txt = "" if a.get("wonder") else self.scenery().describe(a)
                if sc_txt:
                    line("\u2b50 " + sc_txt, "scenery")
                if j < len(stops) - 1:
                    b = stops[j + 1]
                    dd = core.d(a, b)
                    total += dd
                    line(f"\u2193  {dd:.0f} nm   course {core.crs(a, b):03.0f}\u00b0 T   "
                         f"about {core.ete_min(dd, ac)} min", "leg")
            line(f"{total:.0f} nm total, about "
                 f"{sum(core.ete_min(core.d(a, b), ac) for a, b in zip(stops, stops[1:]))} min flying, "
                 f"suggested {'IFR' if idea.ifr else 'VFR'} cruise "
                 f"{core.cruise_alt(stops, ac, idea.ifr):,} ft", "total")

        line("MISSION", "label")
        line(idea.mission, "body")

        line("WHEN", "label")
        line(idea.when_text(), "body")
        line(idea.sun_text(), "small")

        line("WEATHER", "label")
        rules = idea.wx.flight_rules()
        t.insert("end", rules + "   ", {"VFR": "ok", "MVFR": "accent", "IFR": "bad", "LIFR": "lifr"}[rules])
        t.insert("end", f"{idea.wx.describe()}   at {idea.wx_at['id']}\n", "body")

        if idea.notes:
            line("NOTES", "label")
            for n in idea.notes:
                line("\u2022  " + n, "note")
        if idea.twist:
            line("TWIST", "label")
            line(idea.twist, "twist")
        if idea.spoiler:
            line("SPOILER", "label")
            line(idea.spoiler if reveal else "Hidden - press 'Reveal spoiler' when you've landed.", "note")
        t.config(state="disabled")

    def reveal(self):
        if self.idea:
            self.revealed.add(id(self.idea))
            self.show_brief()
            self.show_pictures()

    # ======================================================================
    # Pictures
    # ======================================================================
    def is_hidden(self):
        return bool(self.idea and self.idea.hidden and id(self.idea) not in self.revealed)

    def debounce(self, key, fn, ms=150):
        j = self._resize_job.get(key)
        if j:
            self.after_cancel(j)
        self._resize_job[key] = self.after(ms, fn)

    # ------------------------------------------------------------------ numbers
    def draw_numbers(self):
        """Density altitude, runway lengths, fuel and weight for this flight."""
        if not hasattr(self, "num_txt") or not self.idea:
            return
        idea, ac = self.idea, self.ac()
        wx = self.cur_wx() if hasattr(self, "v_sky") and self.v_sky.get() else idea.wx
        t = self.num_txt
        th, c = self.theme, self.theme.c
        t.config(state="normal")
        t.delete("1.0", "end")
        t.tag_configure("h", font=(th.family, 10, "bold"), foreground=c["text"], spacing1=8, spacing3=3)
        t.tag_configure("b", font=(th.family, 10), foreground=c["text"], spacing3=2)
        t.tag_configure("m", font=(th.family, 9), foreground=c["muted"], spacing3=2)
        t.tag_configure("ok", font=(th.family, 10, "bold"), foreground=c["ok"])
        t.tag_configure("warn", font=(th.family, 10, "bold"), foreground=c["warn"])
        t.tag_configure("bad", font=(th.family, 10, "bold"), foreground=c["bad"])

        def line(txt, tag="b"):
            t.insert("end", txt + "\n", tag)

        wb = xp_perf.weight_balance(ac, self.num(self.v_fuelgal, None) or None,
                                    self.num(self.v_load, 0) + (idea.payload_kg or 0))
        frac = 1.0
        if wb["total_kg"] and wb["mtow_kg"]:
            frac = wb["total_kg"] / wb["mtow_kg"]
        wet = self.v_wet.get()

        stops = self.route_stops()
        far = idea.main_dest() if len(stops) > 1 else stops[0]
        pairs = [("DEPARTURE", stops[0])]
        if far["id"] != stops[0]["id"]:
            pairs.append(("ARRIVAL" if stops[-1]["id"] == far["id"] else "FARTHEST STOP", far))
        if stops[-1]["id"] not in (stops[0]["id"], far["id"]):
            pairs.append(("ARRIVAL", stops[-1]))
        for label, a in pairs:
            line(f"{label}  -  {a['id']} {a['name']}", "h")
            da = xp_perf.density_alt(a["elev"], wx.temp, wx.altimeter)
            line(f"Field {a['elev']:,} ft, {wx.temp} C, altimeter {wx.altimeter:.2f}  \u2192  "
                 f"density altitude {da:,.0f} ft", "b")
            ends = core.runway_ends(a)
            best = None
            for end, hdg, r in ends:
                hw, xw = xp_perf.wind_components(hdg, wx.wind_dir, wx.wind_spd)
                if best is None or hw > best[1]:
                    best = (end, hw, xw, r)
            if not best:
                line("No runway data for this airport.", "m")
                continue
            end, hw, xw, r = best
            gust = f", gusts to {wx.wind_spd + wx.gust} kt" if wx.gust else ""
            line(f"Best runway {end} ({r['len']:,} ft {r['s']}): "
                 f"{hw:+.0f} kt head/tailwind, {xw:.0f} kt crosswind{gust}", "b")
            lim = ac.get("xwind") or 15
            if xw > lim:
                line(f"That crosswind is over this aircraft's {lim} kt limit.", "bad")
            chk = xp_perf.runway_check(ac, a, r["len"], a["elev"], wx.temp, wx.altimeter, frac, hw,
                                       r["s"], wet)
            line(f"Takeoff: {chk['takeoff']['roll']:,} ft roll, "
                 f"{chk['takeoff']['over50']:,} ft over a 50 ft obstacle", "b")
            line(f"Landing: {chk['landing']['roll']:,} ft roll, "
                 f"{chk['landing']['over50']:,} ft over a 50 ft obstacle", "b")
            tag = {"comfortable": "ok", "fine": "ok", "tight": "warn", "too short": "bad"}[chk["verdict"]]
            line(f"{r['len']:,} ft available - {chk['verdict']}: {chk['why']}.", tag)

        # fuel
        line("FUEL", "h")
        dist = sum(core.d(a, b) for a, b in zip(stops, stops[1:]))
        alt_nm = 0.0
        others = [x for x in (self.gen.pool if self.gen else []) if x["id"] != stops[-1]["id"]]
        if idea.ifr and others:
            near = min(others, key=lambda x: core.d(stops[-1], x))
            alt_nm = core.d(stops[-1], near)
        fp = xp_perf.fuel_plan(ac, dist, night=(idea.tod == "night"), ifr=idea.ifr, alternate_nm=alt_nm)
        line(f"{dist:.0f} nm at about {fp['gph']:.1f} gal/hr: "
             f"{fp['trip']:.1f} trip + {fp['taxi']:.1f} taxi"
             + (f" + {fp['alternate']:.1f} alternate" if alt_nm else "")
             + f" + {fp['reserve']:.1f} reserve ({fp['reserve_min']} min)", "b")
        line(f"Total {fp['total']:.1f} US gal  ({fp['lb']:.0f} lb / {fp['kg']:.0f} kg)", "b")
        if fp["capacity_gal"]:
            line(f"Tanks hold about {fp['capacity_gal']:.0f} gal - "
                 f"{'fits with ' + format(fp['capacity_gal'] - fp['total'], '.0f') + ' gal spare' if fp['fits'] else 'THIS DOES NOT FIT - plan a fuel stop'}"
                 + (f", full endurance about {fp['endurance_h']:.1f} h" if fp['endurance_h'] else ""),
                 "b" if fp["fits"] else "bad")

        # weight and balance
        line("WEIGHT", "h")
        if wb["total_kg"] is None:
            line("This aircraft's file doesn't give empty and maximum weights, so I can't do "
                 "weight and balance for it.", "m")
        else:
            line(f"Empty {wb['empty_kg']:,.0f} kg + fuel {wb['fuel_kg']:,.0f} kg + "
                 f"load {wb['payload_kg']:,.0f} kg = {wb['total_kg']:,.0f} kg", "b")
            over = wb["over_kg"]
            if over > 0:
                line(f"{over:,.0f} kg OVER the {wb['mtow_kg']:,.0f} kg maximum - take off fuel or load.", "bad")
            else:
                line(f"{-over:,.0f} kg under the {wb['mtow_kg']:,.0f} kg maximum.", "ok")
            if wb.get("cg") is not None:
                where = "inside" if wb["cg_ok"] else "OUTSIDE"
                line(f"CG about {wb['cg']:.2f} ft ({wb.get('cg_pct', 0):.0f}% of the envelope) - "
                     f"{where} the {wb['cg_fwd']:.2f} to {wb['cg_aft']:.2f} ft limits.",
                     "ok" if wb["cg_ok"] else "bad")
            else:
                line("The aircraft file doesn't give CG limits, so only the weight is checked.", "m")

        line("These are rule-of-thumb estimates from the aircraft's stall speed and weights, "
             "calibrated against a Cessna 172's published figures - not your aircraft's flight "
             "manual. Treat them as a sanity check, and add your own margin.", "m")
        t.config(state="disabled")

    def spoken_callsign(self):
        cs = (self.v_callsign.get() or "N12345").strip()
        return xp_radio.say_ident(cs) if len(cs) <= 8 else cs

    def draw_radio(self):
        if not hasattr(self, "radio_txt") or not self.idea:
            return
        idea, ac = self.idea, self.ac()
        wx = self.cur_wx() if hasattr(self, "v_sky") and self.v_sky.get() else idea.wx
        stops = self.route_stops()
        show = core.Idea(idea.kind, idea.title, stops, idea.mission, wx=wx, ifr=idea.ifr,
                         month=idea.month, tod=idea.tod)
        show.overfly = getattr(idea, "overfly", [])
        a = xp_radio.atis(stops[-1], wx, core, letter_index=(idea.month + len(stops)) % 26)
        self._atis = a
        t = self.radio_txt
        th, c = self.theme, self.theme.c
        t.config(state="normal")
        t.delete("1.0", "end")
        t.tag_configure("h", font=(th.family, 10, "bold"), foreground=c["muted"], spacing1=8, spacing3=3)
        t.tag_configure("b", font=(th.family, 10), foreground=c["text"], spacing3=3, lmargin1=4, lmargin2=4)
        t.tag_configure("w", font=(th.family, 9, "bold"), foreground=c["accent"], spacing1=6)
        t.insert("end", f"ATIS AT {stops[-1]['id']}\n", "h")
        t.insert("end", a["text"] + "\n", "b")
        t.insert("end", "WHAT YOU SAY\n", "h")
        for when, txt in xp_radio.calls(show, ac, core, callsign=self.spoken_callsign(),
                                        letter=a["letter"], wx=wx):
            t.insert("end", when + "\n", "w")
            t.insert("end", txt + "\n", "b")
        t.insert("end", "\nPhraseology varies by country and by controller - this is the "
                        "everyday US pattern, written out so you can practise it.\n", "h")
        t.config(state="disabled")

    def speak_atis(self):
        a = getattr(self, "_atis", None)
        if not a:
            self.draw_radio()
            a = getattr(self, "_atis", None)
        if a:
            kb.speak(a["text"])

    def show_pictures(self):
        if not self.idea:
            return
        stops = self.route_stops()
        uniq = []
        for a in stops:
            if a not in uniq:
                uniq.append(a)
        if self.is_hidden():
            uniq = uniq[:1]
        self._pic_apts = uniq
        self.cb_picapt["values"] = [f"{a['id']}  {a['name']}" for a in uniq]
        cur = self.cb_picapt.current()
        if not (0 <= cur < len(uniq)) or getattr(self, "_pic_for", None) is not self.idea:
            main = self.idea.main_dest()
            cur = uniq.index(main) if main in uniq else len(uniq) - 1
            self._pic_for = self.idea
        self.cb_picapt.current(cur)
        if getattr(self, "_terr_for", None) is not self.idea:
            self._terrain = None
        self.draw_map()
        self.draw_diagram()
        self.draw_skypic()
        self.draw_numbers()
        self.draw_radio()
        self.load_photo()
        if hasattr(self, "terr_cv") and getattr(self, "_terr_for", None) is not self.idea:
            self.terr_cv.delete("all")
            self.l_terr.config(text="Press 'Check terrain' for the highest ground and a safe altitude.")
        if hasattr(self, "live_cv"):
            self.debounce("liveredraw", self.draw_live, 200)

    def pic_apt(self):
        i = self.cb_picapt.current()
        apts = getattr(self, "_pic_apts", [])
        return apts[i] if 0 <= i < len(apts) else None

    def draw_map(self):
        if not self.idea:
            return
        stops = self.route_stops()
        f = self.idea.failure
        if f and self.v_arm.get():
            f = self.adapt_failure(f, stops)
        elif f:
            f = None
        wx = self.cur_wx()
        pics.draw_route_map(self.map_cv, stops, self.airports or (), hidden=self.is_hidden(), failure=f,
                            wind=(wx.wind_dir, wx.wind_spd), title=self.idea.title)

    def draw_diagram(self):
        a = self.pic_apt()
        if not a:
            return
        wx = self.cur_wx()
        best = self.gen.favoured(a, wx.wind_dir, wx.wind_spd) if self.gen else None
        pics.draw_airport(self.apt_cv, a, wind=(wx.wind_dir, wx.wind_spd), fav_end=best[0] if best else None)

    def draw_skypic(self):
        if not self.idea:
            return
        try:
            m = core.MONTHS.index(self.v_month.get())
            hh, _, mm = self.v_hour.get().partition(":")
            hour = int(hh) + int(mm or 0) / 60
        except ValueError:
            m, hour = self.idea.month, self.idea.hour
        a = self.pic_apt() or self.idea.stops[0]
        when = f"{core.MONTHS[m]}, {core.fmt_hour(hour)} local at {a['id']}"
        pics.draw_sky(self.sky_cv, m, hour, self.cur_wx(), a["elev"], a["lat"], when)

    def load_photo(self):
        a = self.pic_apt()
        self._photo_info = None
        self.photo_lbl.config(image="", text="")
        self.photo_lbl.image = None
        self.photo_cap.config(text="")
        if not a:
            return
        if not self.v_photos.get():
            self.photo_lbl.config(text="Wikipedia photos are switched off.")
            return
        self._photo_req += 1
        req = self._photo_req
        self.photo_lbl.config(text=f"Looking for a photo of {a['name']}...")

        def work():
            try:
                info = self.photos.get(a)
                err = None
            except Exception as e:
                info, err = None, e

            def done():
                if req != self._photo_req:
                    return
                if err:
                    self.photo_lbl.config(text=f"Couldn't reach Wikipedia ({err}).")
                elif not info:
                    self.photo_lbl.config(text=f"No Wikipedia article found for {a['id']}.\n"
                                               f"See the Airport diagram tab instead.")
                elif not info.get("file"):
                    self._photo_info = info
                    self.photo_lbl.config(text="The Wikipedia article has no photo.")
                    self.photo_cap.config(text=f"Wikipedia: {info['title']}  (open)")
                else:
                    self._photo_info = info
                    self.photo_cap.config(text=f"Photo: Wikipedia - {info['title']}  (open article)")
                    self._photo_resize()
            self.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def _photo_resize(self):
        def go():
            info = self._photo_info
            if not info or not info.get("file"):
                return
            w, h = max(100, self.photo_lbl.winfo_width() - 4), max(80, self.photo_lbl.winfo_height() - 4)
            img = pics.load_image(info["file"], w, h)
            if img:
                self.photo_lbl.config(image=img, text="")
                self.photo_lbl.image = img
            elif not pics.HAVE_PIL:
                self.photo_lbl.config(image="", text="This photo is a JPEG - press 'Enable JPEG photos' below\n"
                                                     "(installs the free Pillow image library, one time).")
        self.debounce("photo", go)

    def _open_photo_page(self):
        if self._photo_info:
            import webbrowser
            webbrowser.open(self._photo_info["url"])

    def install_pillow(self):
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe") and Path(exe[:-5] + ".exe").exists():
            exe = exe[:-5] + ".exe"
        self.btn_pil.config(state="disabled", text="Installing Pillow...")

        def work():
            import subprocess
            flags = 0x08000000 if sys.platform.startswith("win") else 0   # no console window
            try:
                r = subprocess.run([exe, "-m", "pip", "install", "pillow"], capture_output=True, text=True,
                                   creationflags=flags, timeout=600)
                out = (r.stdout or "")[-400:] + (r.stderr or "")[-400:]
            except Exception as e:
                r, out = None, str(e)
            import importlib
            import site
            try:
                site.addsitedir(site.getusersitepackages())
            except Exception:
                pass
            importlib.invalidate_caches()
            ok = pics.recheck_pil()

            def done():
                if ok:
                    self.btn_pil.pack_forget()
                    self.log("Pillow installed - JPEG photos enabled.")
                    self.show_plane()
                    self._photo_resize()
                else:
                    self.btn_pil.config(state="normal", text="Enable JPEG photos")
                    self.log("Couldn't install Pillow automatically. Open a command prompt and run:  "
                             "py -m pip install pillow\n" + out)
            self.ui(done)
        threading.Thread(target=work, daemon=True).start()

    def show_plane(self):
        rel = self.selected_acf()
        lv = self.v_livery.get()
        self._plane_path = pics.aircraft_icon(self.root(), rel, None if lv == "(default)" else lv)
        name = Path(rel).parent.name if rel else ""
        self.plane_cap.config(text=f"{name}{'  -  ' + lv if lv and lv != '(default)' else ''}   "
                                   f"(flies like: {self.v_prof.get()})")
        self._plane_resize()

    def _plane_resize(self):
        def go():
            p = getattr(self, "_plane_path", None)
            if not p:
                self.plane_lbl.config(image="", text="This aircraft has no thumbnail picture.")
                return
            w, h = max(100, self.plane_lbl.winfo_width() - 4), max(80, self.plane_lbl.winfo_height() - 4)
            img = pics.load_image(p, w, h)
            self.plane_lbl.config(image=img or "", text="" if img else "Couldn't load the thumbnail.")
            self.plane_lbl.image = img
        self.debounce("plane", go)

    def copy_brief(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt.get("1.0", "end"))
        self.log("Briefing copied to clipboard.")

    def save_brief(self):
        if not self.idea:
            return
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")],
                                         initialfile=f"{self.idea.stops[0]['id']}_{self.idea.stops[-1]['id']}.txt")
        if p:
            Path(p).write_text(core.fmt_idea(0, self.idea, self.ac(), True), encoding="utf-8")
            self.log(f"Saved {p}")

    def route_stops(self):
        """Idea's stops, but starting from the departure airport chosen on the launch tab."""
        s = list(self.idea.stops)
        dep = self.gen.find(self.v_dep.get()) if self.gen else None
        if dep and dep["id"] != s[0]["id"]:
            s = [dep] + s[1:] if len(s) > 1 else [dep] + s
            if len(self.idea.stops) > 2 and self.idea.stops[-1]["id"] == self.idea.stops[0]["id"]:
                s[-1] = dep   # round trip: come back to the new home
        return s

    def route_idea(self):
        i = core.Idea(self.idea.kind, self.idea.title, self.route_stops(), self.idea.mission, wx=self.idea.wx,
                      ifr=self.idea.ifr)
        return i

    # ---- .fms output options ------------------------------------------
    def fms_dir(self):
        """Where .fms files go: your own folder, or X-Plane's Output/FMS plans."""
        d = (self.v_fmsdir.get() or "").strip() if hasattr(self, "v_fmsdir") else ""
        return Path(d) if d else self.root() / "Output" / "FMS plans"

    def fms_filename(self, idea, pattern=None):
        """Build the file name from the pattern, e.g. IDEA_{from}_{to}."""
        pat = (pattern if pattern is not None else self.v_fmsname.get()).strip() or "IDEA_{from}_{to}"
        t = time.localtime()
        fields = {"from": idea.stops[0]["id"], "to": idea.stops[-1]["id"],
                  "date": time.strftime("%Y-%m-%d", t), "time": time.strftime("%H%M", t),
                  "kind": idea.kind, "title": idea.title, "n": str(len(idea.stops)),
                  "aircraft": self.ac()["name"]}
        out = pat
        for k, v in fields.items():
            out = out.replace("{" + k + "}", str(v))
        out = re.sub(r"[^A-Za-z0-9 ._+()-]+", "_", out).strip(" ._") or "IDEA"
        return out[:80] + ".fms"

    def fms_options(self):
        win = tk.Toplevel(self)
        win.title("Flight plan file options")
        win.transient(self)
        ttk.Label(win, text="Folder (blank = X-Plane's own Output/FMS plans):").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2))
        ttk.Entry(win, textvariable=self.v_fmsdir, width=56).grid(row=1, column=0, columnspan=2, sticky="ew", padx=8)
        ttk.Button(win, text="Browse...", command=self.pick_fms_dir).grid(row=1, column=2, padx=8)
        ttk.Label(win, text="File name:").grid(row=2, column=0, sticky="w", padx=8, pady=(8, 2))
        ttk.Combobox(win, textvariable=self.v_fmsname, width=40,
                     values=["IDEA_{from}_{to}", "{from}-{to}", "{from}_{to}_{date}",
                             "{date}_{time}_{from}_{to}", "{title}", "{kind}_{from}_{to}"]
                     ).grid(row=2, column=1, sticky="w", pady=(8, 2))
        ttk.Button(win, text="Open folder", command=self.open_fms_dir).grid(row=2, column=2, padx=8)
        ttk.Label(win, text="Fields you can use: {from} {to} {date} {time} {kind} {title} {n} {aircraft}\n"
                           "X-Plane's GPS only lists plans that are in its own Output/FMS plans folder - "
                           "use another folder for Little Navmap or a second sim.",
                  style="Muted.TLabel", justify="left").grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        lbl = ttk.Label(win, text="", style="Muted.TLabel")
        lbl.grid(row=4, column=0, columnspan=3, sticky="w", padx=8)

        def show(*_):
            if not lbl.winfo_exists():
                return
            try:
                name = self.fms_filename(self.route_idea()) if self.idea else self.v_fmsname.get() + ".fms"
            except Exception:
                name = self.v_fmsname.get() + ".fms"
            lbl.config(text=f"Next file: {self.fms_dir() / name}")
        traces = [(v, v.trace_add("write", show)) for v in (self.v_fmsdir, self.v_fmsname)]
        show()

        def done():
            for v, tid in traces:
                try:
                    v.trace_remove("write", tid)
                except tk.TclError:
                    pass
            self.save_cfg()
            self.update_fms_label()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", done)
        ttk.Button(win, text="Done", command=done).grid(row=5, column=2, sticky="e", padx=8, pady=8)
        win.columnconfigure(1, weight=1)

    def pick_fms_dir(self):
        d = filedialog.askdirectory(title="Where should .fms flight plans go?",
                                    initialdir=str(self.fms_dir()))
        if d:
            xp = self.root() / "Output" / "FMS plans"
            self.v_fmsdir.set("" if Path(d) == xp else d)
            self.save_cfg()

    def open_fms_dir(self):
        d = self.fms_dir()
        d.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(d))                                   # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open", str(d)])
        except Exception as e:
            self.log(f"Couldn't open {d}: {e}")

    def update_fms_label(self):
        if not hasattr(self, "l_fms"):
            return
        d = self.fms_dir()
        own = bool((self.v_fmsdir.get() or "").strip())
        try:
            name = self.fms_filename(self.route_idea()) if self.idea else self.v_fmsname.get() + ".fms"
        except Exception:
            name = self.v_fmsname.get() + ".fms"
        if self.v_fmssave.get():
            txt = f"Next file: {d / name}"
        else:
            txt = "Off - no .fms file is written when you launch. ('Save one now' still works.)"
        if own:
            txt += "  -  your own folder, so X-Plane's GPS menu won't list it."
        self.l_fms.config(text=txt)

    def save_fms(self, force=False):
        if not self.idea:
            if force:
                messagebox.showinfo("Flight plan", "Generate and pick an idea first.")
            return
        if not force and not self.v_fmssave.get():
            return
        d = self.fms_dir()
        idea = self.route_idea()
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / self.fms_filename(idea)
            core.write_fms(p, idea, self.ac())
        except OSError as e:
            self.log(f"Couldn't write the .fms file into {d}: {e}")
            if force:
                messagebox.showerror("Flight plan", f"Couldn't write it into\n{d}\n\n{e}")
            return
        self.log(f"Saved flight plan {p}  (load it from the GPS/FMS flight-plan menu)")
        self.update_fms_label()
        return p

    # ======================================================================
    # Launch tab
    # ======================================================================
    def on_sky_pick(self):
        key = self.sky_names.get(self.v_sky.get(), "clear")
        if key != "metar":
            self.v_vis.set(f"{core.SKY[key][2]:g}")
            self.set_ceil_box(core.Wx(key).ceiling)
        elif self.idea and self.idea.wx.custom:
            self.v_vis.set(f"{self.idea.wx.vis:g}")
            self.set_ceil_box(self.idea.wx.ceiling)

    def set_ceil_box(self, ft):
        self._ceil_from_sky = True
        self.v_ceil.set("none" if not ft else str(int(ft)))
        self._ceil_from_sky = False

    def ceil_value(self):
        """The ceiling box as a number, or None for 'none'/blank."""
        t = self.v_ceil.get().strip().lower()
        if t in ("", "none", "clear", "-", "0"):
            return None
        try:
            return max(100, int(float(t.replace(",", ""))))
        except ValueError:
            return None

    def wx_quick(self, what):
        """The two shortcut buttons under the weather box."""
        if what == "min":
            self.v_wxmode.set("mission")
            key = "ovc2" if (self.idea and self.idea.ifr or self.ac()["ifr"]) else "haze15"
            self.v_sky.set(core.SKY[key][0])
            self.on_sky_pick()
        else:
            self.v_wxmode.set("mission")
            self.v_sky.set(core.SKY["clear"][0])
            self.on_sky_pick()
            self.v_vis.set("10")
            self.v_gust.set("0")
        self.update_rules_label()
        self.idea and self.debounce("sky", self.draw_skypic, 100)

    def update_rules_label(self):
        """Show VFR/MVFR/IFR/LIFR for whatever ceiling and visibility are in the boxes."""
        if not hasattr(self, "l_rules"):
            return
        w = core.Wx("clear", vis=self.num(self.v_vis, 10))
        c = self.ceil_value()
        if c:
            w.set_ceiling(c)
        r = w.flight_rules()
        col = {"VFR": "#0a5", "MVFR": "#06c", "IFR": "#c30", "LIFR": "#a0a"}[r]
        txt = f"{r} - ceiling {c:,} ft" if c else f"{r} - no ceiling"
        self.l_rules.config(text=f"{txt}, {core.vis_str(self.num(self.v_vis, 10))}", foreground=col)

    def fill_launch(self):
        idea = self.idea
        self.v_dep.set(idea.stops[0]["id"])
        self.v_month.set(core.MONTHS[idea.month])
        self.v_hour.set(core.fmt_hour(round(idea.hour * 2) / 2))
        wx = idea.wx
        self.sky_names = {v[0]: k for k, v in core.SKY.items()}
        if wx.custom:
            self.sky_names = {wx.sky_text: "metar", **self.sky_names}
        self.cb_sky["values"] = list(self.sky_names)
        self.v_sky.set(wx.sky_text)
        if idea.live:
            self.v_timemode.set("system")
            self.v_wxmode.set("real")
        else:
            if self.v_timemode.get() == "system" and getattr(self, "_auto_live", False):
                self.v_timemode.set("custom")
            if self.v_wxmode.get() == "real" and getattr(self, "_auto_live", False):
                self.v_wxmode.set("mission")
        self._auto_live = idea.live
        self.v_wdir.set(str(wx.wind_dir))
        self.v_wspd.set(str(wx.wind_spd))
        self.v_gust.set(str(wx.gust))
        self.v_temp.set(str(wx.temp))
        self.v_vis.set(f"{wx.vis:g}")
        self.set_ceil_box(wx.ceiling)
        self.update_rules_label()
        self.v_alt.set(f"{wx.altimeter:.2f}")
        self.v_airalt.set(str(core.cruise_alt(idea.stops, self.ac(), idea.ifr)))
        self.v_payload.set(str(int(idea.payload_kg or 0)))
        cap = xp_acf.payload_capacity_kg(self.ac())
        self.l_payload.config(text=f"(about {cap:,.0f} kg available with 70% fuel)" if cap else "")
        if idea.failure:
            self.cb_arm.state(["!disabled"])
            self.l_arm.config(text=f"({idea.failure['desc']} - needs live progress on)")
        else:
            self.cb_arm.state(["disabled"])
            self.l_arm.config(text="(this idea's twist is up to you to fly)" if idea.twist else "(no twist)")
        self.refresh_dep()
        self.update_plugin_label()
        self.update_fms_label()
        self.update_there_label()

    def cur_wx(self):
        sky = self.sky_names.get(self.v_sky.get(), "clear")
        extra = ()
        if sky == "metar" and self.idea and self.idea.wx.custom:
            iw = self.idea.wx
            extra = (iw.layers, iw.sky_text, iw.precip)
        elif sky == "metar":
            sky = "clear"
        w = core.Wx(sky, self.num(self.v_wdir, 0), self.num(self.v_wspd, 0), self.num(self.v_gust, 0),
                    self.num(self.v_temp, 15), self.num(self.v_alt, 29.92),
                    self.num(self.v_vis, 10 if extra else core.SKY[sky][2]), *extra)
        w.set_vis(self.num(self.v_vis, w.vis))
        ceil = self.ceil_value()
        if ceil != w.ceiling:
            w.set_ceiling(ceil)
        return w

    def refresh_dep(self):
        if not self.gen or not self.idea:
            return
        a = self.gen.find(self.v_dep.get())
        if not a:
            self.l_dep.config(text="not found in your scenery", foreground=self.theme.c["bad"])
            return
        self.l_dep.config(text=f"{a['name']} ({a['elev']:,} ft)", foreground=self.theme.c["muted"])
        ends = [e for e, h, r in core.runway_ends(a)] + [r["e"][0] for r in a["rwys"] if r["s"] == "helipad"]
        self.cb_rwy["values"] = ends
        best = self.gen.favoured(a, self.num(self.v_wdir, 0), self.num(self.v_wspd, 0)) if ends else None
        self.v_rwy.set(best[0] if best else (ends[0] if ends else ""))
        ramps = a.get("ramps", [])
        pref = sorted(ramps, key=lambda r: (0 if ("props" in r[2] or "all" in r[2] or "helos" in r[2]) else 1,
                                            0 if r[1] in ("tie_down", "misc", "hangar") else 1))
        self.ramp_map = {f"{r[0]}  [{r[1]}]": r[0] for r in pref}
        self.cb_ramp["values"] = list(self.ramp_map)
        self.v_ramp.set(next(iter(self.ramp_map), ""))
        # runway at the next stop for "on final"
        stops = self.route_stops()
        nxt = stops[1] if len(stops) > 1 else stops[0]
        fends = [e for e, h, r in core.runway_ends(nxt)]
        self.cb_frwy["values"] = fends
        fb = self.gen.favoured(nxt, self.num(self.v_wdir, 0), self.num(self.v_wspd, 0)) if fends else None
        self.v_frwy.set(fb[0] if fb else (fends[0] if fends else ""))
        if not ramps and self.v_start.get() == "ramp":
            self.v_start.set("runway")
        self.update_wind_label()
        self.debounce("showpics", self.show_pictures, 300)

    def update_wind_label(self):
        if not self.gen or not self.idea:
            return
        self.debounce("pics", lambda: (self.draw_map(), self.draw_diagram(), self.draw_skypic()), 300)
        a = self.gen.find(self.v_dep.get())
        if not a:
            return
        w = self.cur_wx()
        self.gen.set_wind_text(w, a)
        self.l_wind.config(text=w.wind_text)

    def update_plugin_label(self):
        try:
            inst, ack = link.plugin_status(self.root())
        except Exception:
            inst, ack = False, None
        if not (self.root() / "Resources" / "plugins" / "XPPython3").exists():
            self.l_plugin.config(text="needs XPPython3 + plugin (see Install)", foreground=self.theme.c["warn"])
        elif not inst:
            self.l_plugin.config(text="plugin not installed yet", foreground=self.theme.c["warn"])
        else:
            self.l_plugin.config(text="plugin installed" + (f" - last: {ack['message']}" if ack else ""),
                                 foreground=self.theme.c["ok"])

    def install_plugin(self):
        root = self.root()
        pyp = root / "Resources" / "plugins" / "XPPython3"
        dest = root / "Resources" / "plugins" / "PythonPlugins"
        if not pyp.exists():
            if messagebox.askyesno(
                    "XPPython3 needed",
                    "Loading the route into the GPS needs the free XPPython3 plugin, which isn't installed.\n\n"
                    "Install it from xppython3.readthedocs.io (unzip into X-Plane 12/Resources/plugins), "
                    "then press this button again.\n\nOpen the XPPython3 website now?"):
                import webbrowser
                webbrowser.open("https://xppython3.readthedocs.io/en/latest/usage/installation_plugin.html")
            return
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "PI_FlightIdeas.py", dest / "PI_FlightIdeas.py")
        self.update_plugin_label()
        messagebox.showinfo("Plugin installed",
                            f"Copied PI_FlightIdeas.py to\n{dest}\n\nRestart X-Plane (or Plugins > XPPython3 > "
                            f"Reload scripts) to activate it.")

    def test_conn(self):
        api = self.api()

        def work():
            ok, msg = api.check()
            self.ui(lambda: self.l_conn.config(text=msg, foreground=self.theme.c["ok"] if ok else "#c00"))
            self.log(msg)
        threading.Thread(target=work, daemon=True).start()

    def build_flight_json(self):
        idea = self.idea
        stops = self.route_stops()
        dep = stops[0]
        acf = self.selected_acf()
        if not acf:
            raise ValueError("Choose an aircraft first.")
        mode = self.v_start.get()
        if mode == "runway":
            if not self.v_rwy.get():
                raise ValueError("Pick a runway.")
            if self.ac()["heli"] and not core.runway_ends(dep):
                start = link.ground_start(dep["lat"], dep["lon"], 0)
            else:
                start = link.runway_start(dep["id"], self.v_rwy.get())
        elif mode == "ramp":
            name = self.ramp_map.get(self.v_ramp.get())
            if not name:
                raise ValueError("This airport has no parking spots in its scenery - pick a runway start.")
            start = link.ramp_start(dep["id"], name)
        elif mode == "final":
            nxt = stops[1] if len(stops) > 1 else dep
            if not self.v_frwy.get():
                raise ValueError(f"{nxt['id']} has no runway to be on final for.")
            start = link.runway_start(nxt["id"], self.v_frwy.get(), self.num(self.v_final, 3))
        else:
            nxt = stops[1] if len(stops) > 1 else dep
            p = core.interp(dep, nxt, self.num(self.v_airpct, 30) / 100)
            start = link.air_start(p["lat"], p["lon"], self.num(self.v_airalt, 4500), core.crs(dep, nxt),
                                   self.ac()["cruise"] * 0.9)
        if self.v_timemode.get() == "system":
            lt, sysclock = None, True
        elif self.v_timemode.get() == "there":
            lt, sysclock = self.time_there(dep), False
        else:
            m = core.MONTHS.index(self.v_month.get())
            hh, _, mm = self.v_hour.get().partition(":")
            lt, sysclock = (int(15 + 30.4 * m) + 1, int(hh) + int(mm or 0) / 60), False
        wm = self.v_wxmode.get()
        if wm == "mission":
            st = idea.wx_at if idea.wx_at in stops else dep
            weather = self.cur_wx().to_xplane(st["lat"], st["lon"], st["elev"])
        elif wm == "real":
            weather = "use_real_weather"
        elif wm == "preset":
            weather = self.v_preset.get()
        else:
            weather = None
        lv = self.v_livery.get()
        f = link.build_flight(acf, None if lv == "(default)" else lv, start, lt, weather,
                              self.v_engines.get(), system_time=sysclock)
        pay = self.num(self.v_payload, 0)
        if pay > 0:
            f["weight"] = {"payload_weight_in_kilograms": [round(pay)]}
        return f

    def launch(self):
        if not self.idea:
            messagebox.showinfo("Launch", "Generate and pick an idea first.")
            return
        try:
            flight = self.build_flight_json()
        except ValueError as e:
            messagebox.showerror("Launch", str(e))
            return
        self.save_cfg()
        (core.CACHE_DIR / "last_flight.json").write_text(json.dumps({"data": flight}, indent=2))
        idea = self.route_idea()
        hidden = self.idea.hidden and id(self.idea) not in self.revealed
        want_route = self.v_loadroute.get() and not hidden
        stops = idea.stops
        failure = self.adapt_failure(self.idea.failure, stops) if (self.v_arm.get() and self.idea.failure) else None
        fms_txt = core.fms_text(idea, self.ac())
        fms_path = self.save_fms()   # None when the .fms switch is off
        root = self.root()
        monitor = self.v_monitor.get()
        grade = self.v_grade.get()
        acname = self.ac()["name"] + f" ({Path(self.selected_acf() or '').stem})"
        insim = self.v_insim.get()
        surprise = (self.num(self.v_sur_lo, 10), self.num(self.v_sur_hi, 40)) if self.v_surprise.get() else None
        pool = self.emergency_pool()
        fuel_kg = None
        if self.v_setfuel.get():
            dist = sum(core.d(a, b) for a, b in zip(stops, stops[1:])) or 60
            fp = xp_perf.fuel_plan(self.ac(), dist, night=(idea.tod == "night"), ifr=idea.ifr)
            cap = (self.ac().get("acf") or {}).get("fuel_kg")
            fuel_kg = min(fp["kg"] * 1.15, cap) if cap else fp["kg"] * 1.15   # plan + a bit, never over full
        msg_lines = [idea.title, idea.mission[:220]] + ([idea.twist[:200]] if idea.twist else [])
        if self.v_speak.get():
            kb.speak(kb.briefing_speech(self.idea, self.ac()))
        if self.v_knee.get() and not getattr(self, "knee", None):
            self.toggle_kneeboard()
        self._live_t0 = None

        api = self.api()

        def work():
            ok, msg = api.check()
            if not ok:
                self.log(msg)
                self.ui(lambda: messagebox.showerror("X-Plane", msg))
                return
            self.log("Starting flight in X-Plane...")
            try:
                api.start_flight(flight)
            except link.XPlaneError as e:
                self.log(f"Launch failed: {e}\n(the JSON sent is in {core.CACHE_DIR / 'last_flight.json'})")
                self.ui(lambda: messagebox.showerror("Launch failed", str(e)))
                return
            self.log("Flight started.")
            try:
                if want_route:
                    link.send_route_to_plugin(root, fms_txt)
                    inst, _ = link.plugin_status(root)
                    self.log("Route sent to the GPS plugin - it loads once the flight is ready." if inst else
                             (f"The GPS plugin isn't installed - load {fms_path.name} from X-Plane's GPS menu."
                              if fms_path else
                              "The GPS plugin isn't installed, and .fms saving is switched off, so the route "
                              "isn't in the sim. Turn it back on under 'Flight plan file (.fms)'."))
                elif hidden:
                    self.log("Mystery flight: route not loaded into the GPS (that would spoil it).")
            except Exception as e:
                self.log(f"Route: {e}")
            if insim:
                try:
                    link.send_message_to_plugin(root, msg_lines)
                except Exception as e:
                    self.log(f"In-sim message: {e}")
            if fuel_kg:
                try:
                    n = api.set_fuel_kg(fuel_kg)
                    self.log(f"Fuel set to {fuel_kg:.0f} kg across {n} tank(s).")
                except Exception as e:
                    self.log(f"Couldn't set the fuel ({e}) - load it yourself in the sim.")
            if monitor:
                self.ui(lambda: self.start_monitor(api, stops, failure, surprise, pool))
            if grade:
                self.ui(lambda: self.start_grader(idea, acname, stops))
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def adapt_failure(f, stops):
        """Re-place the twist failure if the route was changed on the launch tab."""
        f = dict(f)
        if len(stops) < 2:
            return f
        if f["type"] == "engine":
            a, b = max(zip(stops, stops[1:]), key=lambda l: core.d(*l))
            p = core.interp(a, b, 0.5)
            f.update(lat=p["lat"], lon=p["lon"], desc=f"engine failure halfway between {a['id']} and {b['id']}")
        elif f["type"] == "vacuum":
            p = core.interp(stops[0], stops[1], min(1.0, 6 / max(1, core.d(stops[0], stops[1]))))
            f.update(lat=p["lat"], lon=p["lon"], desc=f"vacuum failure ~6 nm out of {stops[0]['id']}")
        return f

    def send_route_only(self):
        if not self.idea:
            return
        p = self.save_fms()
        link.send_route_to_plugin(self.root(), core.fms_text(self.route_idea(), self.ac()), wait_for_new_flight=False)
        self.log("Route sent to the GPS plugin" + (f" (also saved as {p.name})." if p else "."))

    def start_monitor(self, api, stops, failure, surprise=None, pool=None):
        self.stop_monitor()
        self.monitor = link.FlightMonitor(api, stops, failure, on_status=lambda s: self.q.put(("live", s)),
                                          random_failure=surprise, on_event=lambda t: self.log(t),
                                          failure_pool=pool)
        self.monitor.start()
        self.log("Live monitor running" + (f" - twist armed: {failure['desc']}" if failure else "") + ".")

    # ======================================================================
    # Online: OurAirports + Flight Plan Database
    # ======================================================================
    def ourairports(self):
        if not hasattr(self, "_oa"):
            self._oa = xp_online.OurAirports(core.CACHE_DIR)
        return self._oa

    def download_airport_data(self):
        oa = self.ourairports()

        def work():
            try:
                n = oa.download(log=self.log)
                cnt = oa.enrich(self.airports or [], {k: v for k, v in COUNTRY_NAMES.items()})
                self.log(f"Added details to {cnt:,} of your airports.")
                self.ui(lambda: (self.fill_countries(), self.update_online_labels(),
                                 messagebox.showinfo("Airport data",
                                                     f"Downloaded {n:,} airports.\nYour scenery now has city, "
                                                     f"region, country, airport type and Wikipedia links.")))
            except Exception as e:
                msg = str(e)
                self.log(f"Airport data download failed: {msg}")
                self.ui(lambda: messagebox.showerror("Airport data", f"Couldn't download it:\n{msg}"))
        threading.Thread(target=work, daemon=True).start()

    def _build_online(self, f):
        c = self.cfg
        top = ttk.LabelFrame(f, text="Routes other pilots have shared (flightplandatabase.com)", padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="From:").grid(row=0, column=0, sticky="w")
        self.v_ofrom = tk.StringVar(value=c.get("o_from", ""))
        ttk.Entry(top, textvariable=self.v_ofrom, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(top, text="To:").grid(row=0, column=2, sticky="e")
        self.v_oto = tk.StringVar(value=c.get("o_to", ""))
        ttk.Entry(top, textvariable=self.v_oto, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(top, text="Tags:").grid(row=0, column=4, sticky="e")
        self.v_otags = tk.StringVar(value=c.get("o_tags", ""))
        ttk.Combobox(top, textvariable=self.v_otags, width=18,
                     values=["", "scenic", "bush", "vfr", "ifr", "mountain", "island", "shortfield",
                             "sightseeing", "challenge", "generated"]).grid(row=0, column=5, sticky="w", padx=2)
        ttk.Label(top, text="Distance nm:").grid(row=1, column=0, sticky="w", pady=2)
        self.v_odmin = tk.StringVar(value=str(int(c.get("o_dmin", 0))))
        self.v_odmax = tk.StringVar(value=str(int(c.get("o_dmax", 300))))
        ttk.Entry(top, textvariable=self.v_odmin, width=6).grid(row=1, column=1, sticky="w")
        ttk.Label(top, text="to").grid(row=1, column=2, sticky="e")
        ttk.Entry(top, textvariable=self.v_odmax, width=6).grid(row=1, column=3, sticky="w")
        ttk.Label(top, text="Sort:").grid(row=1, column=4, sticky="e")
        self.v_osort = tk.StringVar(value=c.get("o_sort", "popularity"))
        ttk.Combobox(top, textvariable=self.v_osort, values=["popularity", "created", "updated", "distance"],
                     state="readonly", width=12).grid(row=1, column=5, sticky="w", padx=2)
        ttk.Button(top, text="Search", style="Big.TButton", command=self.online_search).grid(row=0, column=6,
                                                                                             rowspan=2, padx=8)
        ttk.Label(top, text="API key (optional):").grid(row=2, column=0, columnspan=2, sticky="w")
        self.v_okey = tk.StringVar(value=c.get("o_key", ""))
        ttk.Entry(top, textvariable=self.v_okey, width=34, show="*").grid(row=2, column=2, columnspan=3, sticky="w")
        ttk.Label(top, text="(a free account raises the request limit)", style="Muted.TLabel").grid(row=2, column=5,
                                                                                                 columnspan=2,
                                                                                                 sticky="w")
        cols = ("route", "nm", "name", "who", "tags", "pop")
        self.tv_on = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse", height=12)
        for col, h, w in zip(cols, ("Route", "nm", "Name", "Shared by", "Tags", "Likes"),
                             (110, 55, 260, 110, 150, 55)):
            self.tv_on.heading(col, text=h)
            self.tv_on.column(col, width=w, anchor="w" if col in ("route", "name", "who", "tags") else "center",
                              stretch=col == "name")
        self.theme.fit_columns(self.tv_on)
        self.tv_on.pack(fill="both", expand=True, pady=4)
        self.tv_on.bind("<Double-1>", lambda e: self.online_use())
        self.l_on = ttk.Label(f, text="Search for routes near an airport, or by tag. Needs internet.",
                              style="Muted.TLabel", wraplength=900, justify="left")
        self.l_on.pack(anchor="w")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Make it a flight idea", style="Big.TButton", command=self.online_use).pack(side="left")
        ttk.Button(b, text="Save .fms to X-Plane", command=self.online_fms).pack(side="left", padx=4)
        ttk.Button(b, text="Open on the website", command=self.online_web).pack(side="left")
        g3 = ttk.LabelFrame(f, text="What's actually flying right now (OpenSky Network)", padding=6)
        g3.pack(fill="x", pady=(8, 0))
        ttk.Label(g3, text="Near:").pack(side="left")
        self.v_skynear = tk.StringVar(value=c.get("sky_near", ""))
        ttk.Entry(g3, textvariable=self.v_skynear, width=8).pack(side="left", padx=2)
        ttk.Label(g3, text="within").pack(side="left")
        self.v_skyrad = tk.StringVar(value=str(int(c.get("sky_rad", 300))))
        ttk.Spinbox(g3, textvariable=self.v_skyrad, from_=50, to=1000, increment=50, width=5).pack(side="left",
                                                                                                   padx=2)
        ttk.Label(g3, text="nm  (blank = wherever your ideas are)").pack(side="left")
        ttk.Button(g3, text="Copy a real flight", style="Big.TButton",
                   command=self.real_flight).pack(side="right")
        self.l_sky = ttk.Label(f, text="", style="Muted.TLabel", wraplength=self.theme.px(900),
                               justify="left")
        self.l_sky.pack(anchor="w")

        g2 = ttk.LabelFrame(f, text="Airport details (OurAirports open database)", padding=6)
        g2.pack(fill="x", pady=(8, 0))
        ttk.Button(g2, text="Download / refresh", command=self.download_airport_data).pack(side="right", padx=(8, 0))
        self.l_oa = ttk.Label(g2, text="", style="Muted.TLabel", wraplength=760, justify="left")
        self.l_oa.pack(side="left", fill="x", expand=True)
        self.online_plans = []
        self.update_online_labels()

    def update_online_labels(self):
        oa = self.ourairports()
        age = oa.age_days()
        self.l_oa.config(text=(f"{len(oa.data):,} airports on file, downloaded {age:.0f} days ago - adds city, "
                               f"region, country, airport type and Wikipedia links (better photos)."
                               if oa.data else
                               "Not downloaded yet: about 10 MB, adds city, region, country, airport type and "
                               "Wikipedia links for better photos."))

    def fpdb(self):
        return xp_online.FlightPlanDB(self.v_okey.get().strip())

    def online_search(self):
        api = self.fpdb()
        q = dict(from_icao=self.v_ofrom.get().strip() or None, to_icao=self.v_oto.get().strip() or None,
                 tags=self.v_otags.get().strip() or None, dist_min=self.num(self.v_odmin, 0) or None,
                 dist_max=self.num(self.v_odmax, 0) or None, sort=self.v_osort.get(), limit=60)
        self.l_on.config(text="Searching flightplandatabase.com...")
        core.save_config(o_from=self.v_ofrom.get(), o_to=self.v_oto.get(), o_tags=self.v_otags.get(),
                         o_dmin=self.num(self.v_odmin, 0), o_dmax=self.num(self.v_odmax, 300),
                         o_sort=self.v_osort.get(), o_key=self.v_okey.get())

        def work():
            try:
                plans, err = api.search(**q), None
            except Exception as e:
                plans, err = [], e
            self.ui(lambda: self.show_plans(plans, err))
        threading.Thread(target=work, daemon=True).start()

    def show_plans(self, plans, err):
        self.online_plans = plans
        self.tv_on.delete(*self.tv_on.get_children())
        if err:
            self.l_on.config(text=f"Couldn't reach flightplandatabase.com ({err}). Check your internet.")
            return
        for i, p in enumerate(plans):
            d = p.get("distance")
            self.tv_on.insert("", "end", iid=str(i), values=(
                f"{p.get('fromICAO') or '?'}-{p.get('toICAO') or '?'}",
                f"{d:.0f}" if isinstance(d, (int, float)) else "", (p.get("name") or "")[:60],
                (p.get("user") or {}).get("username", ""), ", ".join(p.get("tags") or [])[:30],
                p.get("likes", "")))
        self.l_on.config(text=f"{len(plans)} routes. Double-click one to turn it into a flight idea. "
                              f"Airports you don't have are dropped automatically.")

    def _plan_sel(self):
        s = self.tv_on.selection()
        return self.online_plans[int(s[0])] if s else None

    def online_use(self):
        p = self._plan_sel()
        if not p:
            messagebox.showinfo("Online flights", "Pick a route first.")
            return
        api = self.fpdb()
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
        except (KeyError, RuntimeError) as e:
            messagebox.showerror("Online flights", str(e.args[0]))
            return
        gen, ac = self.gen, self.ac()

        def work():
            try:
                full = api.plan(p["id"])
                idea = xp_online.plan_to_idea(full, core, gen, ac)
                err = None
            except Exception as e:
                idea, err = None, e
            self.ui(lambda: self._online_done(idea, err))
        threading.Thread(target=work, daemon=True).start()

    def _online_done(self, idea, err):
        if err or not idea:
            messagebox.showerror("Online flights", f"Couldn't use that plan:\n{err}")
            return
        self._add_idea(idea)
        self.nb.select(0)
        self.log("Imported " + idea.title)

    def online_fms(self):
        p = self._plan_sel()
        if not p:
            return
        api = self.fpdb()
        out = self.fms_dir()

        def work():
            try:
                txt = api.fms(p["id"])
                out.mkdir(parents=True, exist_ok=True)
                f = out / f"FPDB{p['id']}_{p.get('fromICAO', '')}_{p.get('toICAO', '')}.fms"
                f.write_text(txt, encoding="utf-8")
                self.log(f"Saved {f}")
            except Exception as e:
                self.log(f"Couldn't download that plan: {e}")
        threading.Thread(target=work, daemon=True).start()

    def real_flight(self):
        """Pick something airborne right now and build a flight from it."""
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
        except (KeyError, RuntimeError) as e:
            messagebox.showerror("Real traffic", str(e.args[0]))
            return
        gen, ac = self.gen, self.ac()
        near = self.v_skynear.get().strip()
        rad = self.num(self.v_skyrad, 300)
        centre = gen.find(near) if near else (gen.pool[0] if gen.pool else None)
        if centre is None:
            messagebox.showinfo("Real traffic", "Load your scenery first.")
            return
        self.l_sky.config(text="Asking OpenSky what's in the air...")
        core.save_config(sky_near=near, sky_rad=rad)

        def work():
            try:
                sky = xp_online.OpenSky()
                states = sky.fetch(centre["lat"], centre["lon"], rad)
                light = sky.light_traffic(states)
                if not light:
                    raise ValueError(f"OpenSky returned {len(states)} aircraft near {centre['id']}, "
                                     f"but none of them are flying like a light aircraft right now.")
                pick = random.choice(light[:40])
                idea = xp_online.real_flight_idea(pick, core, gen, ac)
                err = None
            except Exception as e:
                idea, err, light = None, e, []
            self.ui(lambda: self._real_done(idea, err, len(light)))
        threading.Thread(target=work, daemon=True).start()

    def _real_done(self, idea, err, n):
        if err or not idea:
            self.l_sky.config(text=f"Couldn't get live traffic: {err}")
            self.log(f"OpenSky: {err}")
            return
        self.l_sky.config(text=f"{n} light aircraft airborne in that area - picked one.")
        self._add_idea(idea)
        self.nb.select(0)
        self.log("Built a flight from real traffic: " + idea.title)

    def online_web(self):
        p = self._plan_sel()
        if p:
            import webbrowser
            webbrowser.open(f"https://flightplandatabase.com/plan/{p['id']}")

    # ======================================================================
    # North America / World idea tabs
    # ======================================================================
    def _build_region_tab(self, f, scope):
        c = self.cfg
        v = {}
        top = ttk.LabelFrame(f, text="Where", padding=6)
        top.pack(fill="x")
        if scope == "na":
            ttk.Label(top, text="Region:").grid(row=0, column=0, sticky="w")
            v["preset"] = tk.StringVar(value=c.get("na_preset", "All of North America"))
            cb = ttk.Combobox(top, textvariable=v["preset"], values=list(NA_PRESETS), state="readonly", width=26)
            cb.grid(row=0, column=1, sticky="w", padx=4)
            cb.bind("<<ComboboxSelected>>", lambda e: self.region_states(scope))
            ttk.Label(top, text="State / province:").grid(row=0, column=2, sticky="e")
            v["state"] = tk.StringVar(value=c.get("na_state", ""))
            v["cb_state"] = ttk.Combobox(top, textvariable=v["state"], width=20)
            v["cb_state"].grid(row=0, column=3, sticky="w")
        else:
            ttk.Label(top, text="Continent:").grid(row=0, column=0, sticky="w")
            v["continent"] = tk.StringVar(value=c.get("w_continent", "Whole world"))
            ttk.Combobox(top, textvariable=v["continent"], values=list(core.CONTINENTS), state="readonly",
                         width=26).grid(row=0, column=1, sticky="w", padx=4)
            ttk.Label(top, text="Country:").grid(row=0, column=2, sticky="e")
            v["country"] = tk.StringVar(value=c.get("w_country", ""))
            v["cb_country"] = ttk.Combobox(top, textvariable=v["country"], width=24)
            v["cb_country"].grid(row=0, column=3, sticky="w")
            v["cb_country"].bind("<<ComboboxSelected>>", lambda e: self.region_states(scope))
            ttk.Label(top, text="State / province:").grid(row=1, column=2, sticky="e", pady=2)
            v["state"] = tk.StringVar(value=c.get("w_state", ""))
            v["cb_state"] = ttk.Combobox(top, textvariable=v["state"], width=24)
            v["cb_state"].grid(row=1, column=3, sticky="w")
        r = 1 if scope == "na" else 2
        ttk.Label(top, text="Near airport:").grid(row=r, column=0, sticky="w", pady=2)
        v["near"] = tk.StringVar(value=c.get(scope + "_near", ""))
        ttk.Entry(top, textvariable=v["near"], width=8).grid(row=r, column=1, sticky="w", padx=4)
        v["radius"] = tk.StringVar(value=str(int(c.get(scope + "_radius", 250))))
        ttk.Label(top, text="within").grid(row=r, column=1, sticky="e")
        ttk.Spinbox(top, textvariable=v["radius"], from_=25, to=3000, increment=25, width=6).grid(row=r, column=2,
                                                                                                 sticky="w")
        ttk.Label(top, text="nm (blank airport = the whole area)", style="Muted.TLabel").grid(row=r, column=3,
                                                                                          sticky="w")
        ttk.Button(top, text="Browse airports...", command=lambda: self.open_picker(scope)).grid(row=r + 1, column=3,
                                                                                                sticky="e")
        v["from"] = tk.StringVar(value="")
        ttk.Label(top, text="Always depart from:").grid(row=r + 1, column=0, sticky="w")
        ttk.Entry(top, textvariable=v["from"], width=8).grid(row=r + 1, column=1, sticky="w", padx=4)

        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="Generate ideas here", style="Big.TButton",
                   command=lambda: self.region_generate(scope)).pack(side="left")
        v["count"] = tk.StringVar(value=str(int(c.get(scope + "_count", 10))))
        ttk.Spinbox(bar, textvariable=v["count"], from_=1, to=40, width=4).pack(side="left", padx=(8, 2))
        ttk.Label(bar, text="ideas").pack(side="left")
        ttk.Button(bar, text="Surprise me (one idea)",
                   command=lambda: self.region_generate(scope, 1, True)).pack(side="left", padx=10)
        ttk.Label(bar, text="Mission types, aircraft and twists come from the left panel.",
                  style="Muted.TLabel").pack(side="right")
        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)
        lf = ttk.Frame(body)
        v["lb"] = tk.Listbox(lf, exportselection=False)
        self.theme.track(v["lb"], "list")
        sb = ttk.Scrollbar(lf, orient="vertical", command=v["lb"].yview)
        v["lb"].config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        v["lb"].pack(fill="both", expand=True)
        v["lb"].bind("<<ListboxSelect>>", lambda e: self.region_pick(scope))
        v["lb"].bind("<Double-1>", lambda e: (self.region_pick(scope), self.nb.select(0)))
        rf = ttk.Frame(body)
        v["cv"] = tk.Canvas(rf, height=self.theme.px(260), background="#e9eef1")
        self.theme.track(v["cv"], "canvas")
        v["cv"].pack(fill="both", expand=True)
        v["txt"] = tk.Label(rf, text="", justify="left", anchor="nw", wraplength=430)
        v["txt"].pack(fill="x", pady=4)
        body.add(lf, weight=2)
        body.add(rf, weight=3)
        b2 = ttk.Frame(f)
        b2.pack(fill="x")
        ttk.Button(b2, text="Open briefing", command=lambda: (self.region_pick(scope), self.nb.select(0))).pack(side="left")
        ttk.Button(b2, text="Set up in X-Plane  >>", style="Big.TButton",
                   command=lambda: (self.region_pick(scope), self.nb.select(1))).pack(side="left", padx=6)
        v["ideas"] = []
        setattr(self, "rt_" + scope, v)

    def region_states(self, scope):
        v = getattr(self, "rt_" + scope)
        iso = "US"
        if scope == "na":
            iso = NA_PRESETS.get(v["preset"].get(), {}).get("country", "ANY")
        else:
            t = v["country"].get().strip()
            m = re.search(r"\(([A-Za-z0-9]{2,3})\)\s*$", t)
            iso = m.group(1).upper() if m else (t.upper() if len(t) == 2 else "")
        states = sorted({a["state"] for a in (self.airports or []) if a.get("state") and
                         ((a.get("iso") or ("US" if core.is_us(a) else "")) == iso)}) if iso not in ("", "ANY") else []
        v["cb_state"]["values"] = states
        if v["state"].get() not in states:
            v["state"].set("")

    def region_opts(self, scope):
        v = getattr(self, "rt_" + scope)
        o = SimpleNamespace(from_=v["from"].get().strip() or None, near=v["near"].get().strip() or None,
                            radius=self.num(v["radius"], 250), state=v["state"].get().strip() or None,
                            country="ANY", continent=None, box=None,
                            include_private=self.v_private.get(), max_leg=self.num(self.v_maxleg, 0) or None,
                            payload_capacity=xp_acf.payload_capacity_kg(self.ac()))
        if scope == "na":
            preset = NA_PRESETS.get(v["preset"].get(), {})
            o.country = preset.get("country", "ANY")
            o.continent = preset.get("continent")
            o.box = preset.get("box")
        else:
            o.continent = v["continent"].get()
            t = v["country"].get().strip()
            m = re.search(r"\(([A-Za-z0-9]{2,3})\)\s*$", t)
            if m:
                o.country = m.group(1).upper()
            elif len(t) == 2 and t.isalpha():
                o.country = t.upper()
        return o

    def region_generate(self, scope, n=None, open_it=False):
        v = getattr(self, "rt_" + scope)
        kinds = [k for k, b in self.v_miss.items() if b.get()] or [k for k in core.MISSIONS
                                                                   if k not in core.NOT_GENERATED
                                                                   and k != "realwx"]
        if not self.airports:
            messagebox.showinfo("Ideas", "Airports are still loading.")
            return
        opts = self.region_opts(scope)
        seed = random.randrange(1_000_000)
        try:
            gen = core.Generator(self.airports, self.ac(), random.Random(seed), opts)
        except KeyError as e:
            messagebox.showerror("Ideas", str(e.args[0]))
            return
        if not gen.pool:
            messagebox.showerror("Ideas", "No airports match that area for this aircraft.")
            return
        if "realwx" in kinds:
            gen.metars = self.metar_src.obs
            gen.wx_kind = self.hazard_key()
        count = n or int(self.num(v["count"], 10))
        ideas = gen.generate(count, kinds, self.v_twist.get() / 100)
        if not ideas:
            messagebox.showinfo("Ideas", "Couldn't build ideas there - try a bigger area or more mission types.")
            return
        self.gen = gen
        v["ideas"] = ideas
        v["lb"].delete(0, "end")
        for i in ideas:
            a = i.stops[-1]
            where = a.get("state") or a.get("country") or a.get("iso") or ""
            v["lb"].insert("end", f"{i.title}  -  {where}")
        v["lb"].selection_set(0)
        self.region_preview(scope)
        self.log(f"{len(ideas)} ideas in {v['preset'].get() if scope == 'na' else v['continent'].get()}"
                 f" (seed {seed}, {len(gen.pool):,} airports).")
        core.save_config(**{scope + "_near": v["near"].get(), scope + "_radius": self.num(v["radius"], 250),
                            scope + "_count": count,
                            **({"na_preset": v["preset"].get(), "na_state": v["state"].get()} if scope == "na"
                               else {"w_continent": v["continent"].get(), "w_country": v["country"].get(),
                                     "w_state": v["state"].get()})})
        if open_it:
            self.region_pick(scope)
            self.nb.select(0)

    def _region_sel(self, scope):
        v = getattr(self, "rt_" + scope)
        s = v["lb"].curselection()
        return v["ideas"][s[0]] if s and s[0] < len(v["ideas"]) else None

    def region_preview(self, scope):
        v = getattr(self, "rt_" + scope)
        i = self._region_sel(scope)
        if not i:
            return
        pics.draw_route_map(v["cv"], i.stops, self.airports or (), title=i.title, hidden=i.hidden)
        total = sum(core.d(a, b) for a, b in zip(i.stops, i.stops[1:]))
        v["txt"].config(text=f"{i.mission}\n\n{' - '.join(a['id'] for a in i.stops)}  |  {total:.0f} nm  |  "
                             f"{i.when_text()}  |  {i.wx.sky_text}")

    def region_pick(self, scope):
        i = self._region_sel(scope)
        if i:
            self._add_idea(i)
            self.region_preview(scope)

    # ======================================================================
    # Airport browser
    # ======================================================================
    def open_picker(self, scope=None):
        if not self.airports:
            messagebox.showinfo("Airports", "Airports are still loading.")
            return
        AirportPicker(self, scope)

    # ======================================================================
    # Live flight, kneeboard, speech, terrain, career, share codes
    # ======================================================================
    def _build_live_flight(self, f):
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.v_livehdr = tk.StringVar(value="No flight running. Launch one with 'Show live progress' or scoring on.")
        ttk.Label(top, textvariable=self.v_livehdr, style="Head.TLabel").pack(side="left")
        ttk.Button(top, text="Kneeboard", command=self.toggle_kneeboard).pack(side="right")
        ttk.Button(top, text="Read briefing aloud", command=self.read_aloud).pack(side="right", padx=4)
        self.live_cv = tk.Canvas(f, height=self.theme.px(380), background="#e9eef1")
        self.theme.track(self.live_cv, "canvas")
        self.live_cv.pack(fill="both", expand=True, pady=4)
        self.live_cv.bind("<Configure>", lambda e: self.debounce("livemap", self.draw_live, 200))
        self.v_livefacts = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_livefacts, font=MONO).pack(anchor="w")
        self.live_sample = None

    def on_live_sample(self, d):
        self.live_sample = d
        self.q.put(("liveredraw", None))

    def draw_live(self):
        d = self.live_sample
        if not self.idea:
            return
        stops = self.route_stops()
        here = {"lat": d["lat"], "lon": d["lon"], "hdg": d.get("hdg", 0),
                "label": f"{d['gs']:.0f} kt  {d['agl']:,.0f} ft"} if d else None
        wx = self.cur_wx()
        pics.draw_route_map(self.live_cv, stops, self.airports or (), wind=(wx.wind_dir, wx.wind_spd),
                            title=self.idea.title, here=here)
        if not d:
            self.v_livefacts.set("")
            return
        nxt = min(stops[1:], key=lambda a: core.dist_nm(d["lat"], d["lon"], a["lat"], a["lon"])) if len(stops) > 1 \
            else stops[0]
        dn = core.dist_nm(d["lat"], d["lon"], nxt["lat"], nxt["lon"])
        ete = dn / max(30, d["gs"]) * 60
        burn = exp.fuel_gph(self.ac()) * ((d["t"] - (getattr(self, "_live_t0", None) or d["t"])) / 3600)
        self._live_t0 = getattr(self, "_live_t0", d["t"])
        facts = (f"{d['gs']:.0f} kt GS   {d['ias']:.0f} kt IAS   {d['agl']:,.0f} ft AGL   {d['vs']:+.0f} fpm   |   "
                 f"next {nxt['id']} in {dn:.1f} nm (~{ete:.0f} min)   |   flown {d['dist_nm']:.0f} nm, "
                 f"fuel used ~{burn:.1f} gal")
        self.v_livefacts.set(facts)
        self.v_livehdr.set(f"In flight: {self.idea.title}")
        if getattr(self, "knee", None):
            self.knee.update_live(f"{nxt['id']} {dn:5.1f} nm  {d['gs']:3.0f} kt  {d['agl']:6,.0f} ft")

    def toggle_kneeboard(self):
        if getattr(self, "knee", None):
            try:
                self.knee.close()
            except Exception:
                pass
            self.knee = None
            return
        if not self.idea:
            messagebox.showinfo("Kneeboard", "Pick an idea first.")
            return
        self.knee = kb.Kneeboard(self, self.idea, self.ac(), on_close=lambda: setattr(self, "knee", None))

    def read_aloud(self):
        if self.idea:
            kb.speak(kb.briefing_speech(self.idea, self.ac()))
            self.log("Reading the briefing aloud.")

    # ---- terrain -------------------------------------------------------------
    def check_terrain(self):
        if not self.idea:
            return
        stops = self.route_stops()
        online = self.v_dem.get()
        ac = self.ac()
        alt = core.cruise_alt(stops, ac, self.idea.ifr)
        wx = self.cur_wx()
        self.l_terr.config(text="Checking terrain..." + (" (downloading elevations)" if online else ""))

        def work():
            t = xp_terrain.Terrain(core.CACHE_DIR, self.airports or [], online=online)
            try:
                res = t.summary(stops, alt, wind=(wx.wind_dir, wx.wind_spd))
                err = None
            except Exception as e:
                res, err = None, e
            self.ui(lambda: self.show_terrain(res, err, alt))
        threading.Thread(target=work, daemon=True).start()

    def show_terrain(self, res, err, alt):
        if err or not res:
            self.l_terr.config(text=f"Terrain check failed: {err}")
            return
        self._terrain = res
        self._terr_for = self.idea
        pics.draw_terrain(self.terr_cv, res["profile"], alt, res["msa_ft"])
        self.l_terr.config(text=f"Highest ground ~{res['max_ft']:,} ft ({res['source']}); minimum safe altitude "
                                f"~{res['msa_ft']:,} ft; planned cruise {alt:,} ft.\n" + "\n".join(res["warnings"]))
        core.save_config(terrain_online=self.v_dem.get())

    def get_taf(self):
        if not self.idea:
            return
        dest = self.idea.main_dest()["id"]
        self.l_terr.config(text=f"Asking for the forecast for {dest}...")

        def work():
            raw = livewx.fetch_taf(dest)
            self._terr_for = self.idea
            txt = ("TAF " + dest + ":\n" + "\n".join("  " + l for l in livewx.taf_lines(raw))) if raw else \
                f"No forecast published for {dest} (small airports usually have none)."
            self.ui(lambda: self.l_terr.config(text=txt))
            if raw:
                self.log("TAF " + dest + ": " + raw)
        threading.Thread(target=work, daemon=True).start()

    # ---- career --------------------------------------------------------------
    def _build_career(self, f):
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.v_career = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.v_career, style="Head.TLabel").pack(side="left")
        ttk.Button(top, text="Refresh", command=self.fill_career).pack(side="right")
        ttk.Button(top, text="Today's challenge", command=self.daily_challenge).pack(side="right", padx=4)
        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)
        lf = ttk.Frame(body)
        self.career_txt = ScrolledText(lf, wrap="word", font=MONO, height=20)
        self.theme.track(self.career_txt, "text")
        self.career_txt.pack(fill="both", expand=True)
        rf = ttk.Frame(body)
        self.tv_badge = ttk.Treeview(rf, columns=("b", "how"), show="headings", selectmode="browse")
        for col, h, w in zip(("b", "how"), ("Badge", "How to earn it"), (130, 280)):
            self.tv_badge.heading(col, text=h)
            self.tv_badge.column(col, width=w, anchor="w", stretch=col == "how")
        self.tv_badge.tag_configure("earned", foreground=self.theme.c["ok"])
        self.tv_badge.tag_configure("locked", foreground=self.theme.c["muted"])
        self.theme.fit_columns(self.tv_badge)
        self.tv_badge.pack(fill="both", expand=True)
        body.add(lf, weight=3)
        body.add(rf, weight=3)
        self.after(600, self.fill_career)

    def fill_career(self):
        by_id = {a["id"]: a for a in (self.airports or [])}
        s = career.career(self.logbook, by_id)
        self.v_career.set(f"{s['rating'][0]}  -  {s['hours']:.1f} h, {s['landings']} landings, "
                          f"{s['airports']} airports, {len(s['badges'])} badges")
        self.career_txt.delete("1.0", "end")
        self.career_txt.insert("1.0", career.summary_text(s))
        self.tv_badge.delete(*self.tv_badge.get_children())
        for n, d in s["badges"]:
            self.tv_badge.insert("", "end", values=("* " + n, d), tags=("earned",))
        for n, d in s["locked"]:
            self.tv_badge.insert("", "end", values=(n, d), tags=("locked",))

    def daily_challenge(self):
        seed, day = career.daily_seed()
        try:
            gen = self.make_gen(seed)
        except (KeyError, RuntimeError) as e:
            messagebox.showerror("Challenge", str(e.args[0]))
            return
        rng = random.Random(seed)
        kinds = [k for k in core.MISSIONS if k not in core.NOT_GENERATED and k != "realwx"]
        ideas = gen.generate(1, [rng.choice(kinds)], 1.0) or gen.generate(1, kinds, 1.0)
        if not ideas:
            messagebox.showinfo("Challenge", "Couldn't build today's challenge in this area - widen the area.")
            return
        idea = ideas[0]
        idea.title = f"Challenge of the day ({day}): {idea.title}"
        idea.notes.append("Everyone with the same settings gets this same flight today. Beat your own score.")
        self._add_idea(idea)
        self.nb.select(0)

    # ---- share codes ----------------------------------------------------------
    def import_share(self):
        code = self.v_custom.get().strip()
        if not code.startswith("XPFI1:"):
            code = self.clipboard_get() if self.clipboard_get else ""
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
            idea = exp.from_share_code(code, core, self.gen)
        except Exception as e:
            messagebox.showerror("Share code", f"Couldn't read that share code.\n\n{e}")
            return
        self._add_idea(idea)
        self.nb.select(0)
        self.log("Imported a shared flight: " + idea.title)

    # ======================================================================
    # Export / print
    # ======================================================================
    def export_menu(self):
        if not self.idea:
            return
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Print / open briefing sheet (HTML)", command=lambda: self.do_export("html"))
        m.add_command(label="Send the briefing to my phone or tablet", command=self.phone_briefing)
        m.add_command(label="Save nav log (headings, times, fuel)", command=lambda: self.do_export("navlog"))
        m.add_command(label="Show nav log here", command=lambda: self.do_export("shownav"))
        m.add_separator()
        m.add_command(label="Save .fms flight plan (X-Plane GPS)", command=lambda: self.save_fms(force=True))
        m.add_command(label="Save GPX (Little Navmap, SkyDemon...)", command=lambda: self.do_export("gpx"))
        m.add_command(label="Save KML (Google Earth)", command=lambda: self.do_export("kml"))
        m.add_command(label="Save Little Navmap plan (.lnmpln)", command=lambda: self.do_export("lnm"))
        m.add_command(label="Send straight to Little Navmap's folder",
                      command=lambda: self.do_export("lnmfolder"))
        m.add_separator()
        m.add_command(label="Approach plates and charts for this route",
                      command=self.charts_menu)
        m.add_separator()
        m.add_command(label="Copy route string", command=lambda: self.do_export("route"))
        m.add_command(label="Copy share code (send this flight to a friend)",
                      command=lambda: self.do_export("share"))
        m.add_command(label="Open in SimBrief", command=lambda: self.do_export("simbrief"))
        m.add_separator()
        m.add_command(label="Back up settings, logbook and trips...", command=self.backup_data)
        m.add_command(label="Restore from a backup...", command=self.restore_data)
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    def do_export(self, kind):
        idea, ac = self.route_idea(), self.ac()
        idea.notes, idea.twist, idea.title = self.idea.notes, self.idea.twist, self.idea.title
        idea.month, idea.tod, idea._hour = self.idea.month, self.idea.tod, self.idea._hour
        base = f"{idea.stops[0]['id']}_{idea.stops[-1]['id']}"
        out = core.CACHE_DIR / "exports"
        out.mkdir(parents=True, exist_ok=True)
        import webbrowser
        if kind == "route":
            self.clipboard_clear()
            self.clipboard_append(exp.route_string(idea))
            self.log("Route copied: " + exp.route_string(idea))
            return
        if kind == "share":
            code = exp.share_code(self.idea, ac["name"])
            self.clipboard_clear()
            self.clipboard_append(code)
            self.log(f"Share code copied ({len(code)} characters) - paste it to a friend, they use "
                     f"'Paste share code'.")
            return
        if kind == "simbrief":
            webbrowser.open(exp.simbrief_url(idea, ac))
            self.log("Opened SimBrief with this route.")
            return
        if kind == "shownav":
            self.txt.config(state="normal")
            self.txt.insert("end", "\n\n" + exp.nav_log(core, idea, ac, getattr(self, "_terrain", None)) + "\n")
            self.txt.see("end")
            self.txt.config(state="disabled")
            return
        if kind == "html":
            p = out / f"briefing_{base}.html"
            p.write_text(exp.briefing_html(core, idea, ac,
                                           exp.nav_log(core, idea, ac, getattr(self, "_terrain", None))),
                         encoding="utf-8")
            webbrowser.open(p.as_uri())
            self.log(f"Briefing sheet opened in your browser ({p}) - use Ctrl+P to print.")
            return
        if kind == "lnmfolder":
            d = self.lnm_dir(ask=True)
            if not d:
                return
            try:
                d.mkdir(parents=True, exist_ok=True)
                f = d / f"{base}.lnmpln"
                f.write_text(exp.lnmpln(idea, ac), encoding="utf-8")
                self.log(f"Saved {f} - it's in Little Navmap's flight plan list now.")
            except OSError as e:
                messagebox.showerror("Little Navmap", f"Couldn't write it there:\n{e}")
            return
        data, ext = {"navlog": (exp.nav_log(core, idea, ac, getattr(self, "_terrain", None)), ".txt"),
                     "gpx": (exp.gpx(idea), ".gpx"), "kml": (exp.kml(idea), ".kml"),
                     "lnm": (exp.lnmpln(idea, ac), ".lnmpln")}[kind]
        f = filedialog.asksaveasfilename(defaultextension=ext, initialfile=base + ext,
                                         filetypes=[(ext[1:].upper(), "*" + ext)])
        if f:
            Path(f).write_text(data, encoding="utf-8")
            self.log(f"Saved {f}")

    @staticmethod
    def time_there(apt):
        """(day of year, local clock hour) right now at this airport's longitude."""
        now = time.gmtime()
        hour = (now.tm_hour + now.tm_min / 60 + apt["lon"] / 15.0) % 24
        return now.tm_yday, hour

    def update_there_label(self):
        if not hasattr(self, "l_there"):
            return
        if self.v_timemode.get() != "there" or not self.idea:
            self.l_there.config(text="")
            return
        dep = self.gen.find(self.v_dep.get()) if self.gen else None
        dep = dep or self.route_stops()[0]
        _, h = self.time_there(dep)
        self.l_there.config(text=f"That's about {core.fmt_hour(h)} at {dep['id']} right now.")

    # ------------------------------------------------------------ phone briefing
    def phone_briefing(self):
        if not self.idea:
            return
        idea, ac = self.route_idea(), self.ac()
        idea.notes, idea.twist, idea.title = self.idea.notes, self.idea.twist, self.idea.title
        idea.month, idea.tod, idea._hour = self.idea.month, self.idea.tod, self.idea._hour
        html = exp.briefing_html(core, idea, ac,
                                 exp.nav_log(core, idea, ac, getattr(self, "_terrain", None)))
        try:
            srv = xp_web.BriefingServer(html, title=idea.title)
        except OSError as e:
            messagebox.showerror("Phone briefing", f"Couldn't start the little web server:\n{e}")
            return
        win = tk.Toplevel(self)
        win.title("Briefing on your phone")
        win.transient(self)
        self.theme.track(win, "window")
        ttk.Label(win, text="Scan this with your phone's camera", style="Head.TLabel").pack(
            anchor="w", padx=14, pady=(12, 2))
        url = srv.url
        cv = tk.Canvas(win, highlightthickness=0, background="#ffffff")
        cv.pack(padx=14, pady=8)
        try:
            m = xp_qr.matrix(url, "M")
            box = self.theme.px(6)
            n = len(m)
            side = (n + 8) * box
            cv.config(width=side, height=side)
            for r in range(n):
                for c in range(n):
                    if m[r][c]:
                        x, y = (c + 4) * box, (r + 4) * box
                        cv.create_rectangle(x, y, x + box, y + box, fill="#000000", outline="")
        except Exception as e:
            cv.config(width=self.theme.px(220), height=self.theme.px(60))
            cv.create_text(10, 20, anchor="w", text=f"(couldn't draw a QR code: {e})")
        lbl = ttk.Label(win, text=url, font=self.theme.mono)
        lbl.pack(padx=14)
        ttk.Label(win, text="Or type that address into the phone's browser. The page stays up while "
                            "this window is open - anyone on your network can open it, so close it "
                            "when you're done.",
                  style="MutedBg.TLabel", wraplength=self.theme.px(340), justify="left").pack(
            padx=14, pady=(6, 2))
        hits = ttk.Label(win, text="Not opened yet.", style="MutedBg.TLabel")
        hits.pack(padx=14, pady=(0, 4))

        def tick():
            if not win.winfo_exists():
                return
            hits.config(text=f"Opened {srv.hits} time(s)." if srv.hits else "Not opened yet.")
            win.after(1000, tick)
        tick()

        def close():
            srv.stop()
            self.theme.forget(win)
            win.destroy()
            self.log("Phone briefing server stopped.")
        row = ttk.Frame(win, style="Bg.TFrame", padding=12)
        row.pack(fill="x")
        ttk.Button(row, text="Copy the address", style="Quiet.TButton",
                   command=lambda: (self.clipboard_clear(), self.clipboard_append(url))).pack(side="left")
        ttk.Button(row, text="Stop serving", style="Big.TButton", command=close).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", close)
        self.log(f"Briefing served at {url} - scan the QR code with your phone.")

    # ------------------------------------------------------------ backup
    def backup_data(self):
        f = filedialog.asksaveasfilename(defaultextension=".zip",
                                         initialfile=f"flight_ideas_backup_{time.strftime('%Y-%m-%d')}.zip",
                                         filetypes=[("Zip file", "*.zip")])
        if not f:
            return
        try:
            n = xp_web.backup(core.CACHE_DIR, Path(f))
            self.log(f"Backed up {n} files to {f}")
            messagebox.showinfo("Backup", f"Saved {n} files to\n{f}\n\nSettings, logbook, trips, "
                                          f"spots and career are all in there.")
        except OSError as e:
            messagebox.showerror("Backup", str(e))

    def restore_data(self):
        f = filedialog.askopenfilename(filetypes=[("Zip file", "*.zip")])
        if not f:
            return
        if not messagebox.askyesno("Restore", "This replaces your current settings, logbook, trips and "
                                              "spots with the ones in the backup.\n\n(The old files are "
                                              "kept alongside as .json.bak.)\n\nGo ahead?"):
            return
        try:
            done = xp_web.restore(core.CACHE_DIR, Path(f))
        except (OSError, zipfile.BadZipFile) as e:
            messagebox.showerror("Restore", str(e))
            return
        self.log(f"Restored {len(done)} files: {', '.join(done)}")
        messagebox.showinfo("Restore", f"Restored {len(done)} files.\n\nClose and reopen the app so "
                                       f"everything picks them up.")

    def lnm_dir(self, ask=False):
        """Little Navmap's own flight plan folder, remembered once you've picked it."""
        saved = self.cfg.get("lnm_dir", "")
        if saved and Path(saved).is_dir():
            return Path(saved)
        guesses = [Path.home() / "Documents" / "Little Navmap" / "Flight Plans",
                   Path.home() / "Documents" / "Little Navmap",
                   Path.home() / "Little Navmap"]
        for g in guesses:
            if g.is_dir():
                core.save_config(lnm_dir=str(g))
                self.cfg["lnm_dir"] = str(g)
                return g
        if not ask:
            return None
        d = filedialog.askdirectory(title="Where does Little Navmap keep its flight plans?")
        if d:
            core.save_config(lnm_dir=d)
            self.cfg["lnm_dir"] = d
            return Path(d)
        return None

    def charts_menu(self):
        """Links to free charts for each airport on the route."""
        if not self.idea:
            return
        import webbrowser
        m = tk.Menu(self, tearoff=0)
        seen = []
        for a in self.route_stops():
            if a["id"] in seen or a.get("spot"):
                continue
            seen.append(a["id"])
            sub = tk.Menu(m, tearoff=0)
            ident = a["id"]
            us = core.is_us(a)
            if us:
                code = ident[1:] if len(ident) == 4 and ident.startswith("K") else ident
                sub.add_command(label="FAA approach plates and airport diagram (free)",
                                command=lambda c=code: webbrowser.open(
                                    f"https://www.airnav.com/cgi-bin/airport-search?name={c}"))
                sub.add_command(label="FAA digital terminal procedures",
                                command=lambda c=ident: webbrowser.open(
                                    "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/"
                                    f"dtpp/search/?cycle=current&ident={c}"))
                sub.add_command(label="AirNav airport page",
                                command=lambda c=ident: webbrowser.open(
                                    f"https://www.airnav.com/airport/{c}"))
            sub.add_command(label="SkyVector chart",
                            command=lambda c=ident: webbrowser.open(f"https://skyvector.com/airport/{c}"))
            sub.add_command(label="OpenAIP (worldwide, free)",
                            command=lambda c=ident: webbrowser.open(f"https://www.openaip.net/?search={c}"))
            if a.get("wiki"):
                sub.add_command(label="Wikipedia article",
                                command=lambda u=a["wiki"]: webbrowser.open(u))
            m.add_cascade(label=f"{ident}  {a['name'][:34]}", menu=sub)
        if not seen:
            return
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    # ======================================================================
    # Scoring and logbook
    # ======================================================================
    def _build_logbook(self, f):
        self.logbook = xp_score.Logbook(core.CACHE_DIR / "logbook.json")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.l_stats = ttk.Label(top, text="", style="Head.TLabel")
        self.l_stats.pack(side="left")
        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=(2, 0))
        ttk.Button(row2, text="End flight & save now", command=self.stop_grader).pack(side="left")
        ttk.Button(row2, text="Favourite", command=self.log_fav).pack(side="left", padx=4)
        ttk.Button(row2, text="Delete", command=self.log_delete).pack(side="left")
        ttk.Button(row2, text="Export CSV", command=self.log_export).pack(side="left", padx=4)
        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)
        lf = ttk.Frame(body)
        cols = ("when", "title", "acf", "route", "nm", "min", "ldg", "score")
        self.tv_log = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
        for col, h, w in zip(cols, ("When", "Flight", "Aircraft", "Route", "nm", "min", "Ldg", "Score"),
                             (95, 150, 110, 100, 40, 40, 34, 44)):
            self.tv_log.heading(col, text=h)
            self.tv_log.column(col, width=w, anchor="w" if col in ("title", "acf", "route") else "center",
                               stretch=col == "title")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tv_log.yview)
        self.tv_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.theme.fit_columns(self.tv_log)
        self.tv_log.pack(fill="both", expand=True)
        self.tv_log.bind("<<TreeviewSelect>>", lambda e: self.log_show())
        rf = ttk.Frame(body)
        self.log_txt = ScrolledText(rf, wrap="word", font=MONO, height=18, width=52)
        self.theme.track(self.log_txt, "text")
        self.log_txt.pack(fill="both", expand=True)
        self.log_img = tk.Label(rf, text="", background="#20252b", foreground="#ccc")
        self.log_img.pack(fill="x", pady=(4, 0))
        self.log_cv = tk.Canvas(rf, height=self.theme.px(150), background="#e9eef1")
        self.theme.track(self.log_cv, "canvas")
        self.log_cv.pack(fill="x", pady=(4, 0))
        body.add(lf, weight=3)
        body.add(rf, weight=2)
        self.fill_logbook()

    def fill_logbook(self):
        self.tv_log.delete(*self.tv_log.get_children())
        for i, e in enumerate(self.logbook.entries):
            self.tv_log.insert("", "end", iid=str(i), values=(
                time.strftime("%d %b %H:%M", time.localtime(e.get("time", 0))),
                ("* " if e.get("favourite") else "") + e.get("title", ""), e.get("aircraft", ""),
                "-".join(e.get("route", []))[:22], f"{e.get('distance_nm', 0):.0f}",
                f"{e.get('minutes', 0):.0f}", len(e.get("landings", [])), e.get("score", "")))
        st = self.logbook.stats()
        self.l_stats.config(text=f"{st['flights']} flights  |  {st['hours']:.1f} h  |  {st['nm']:,.0f} nm  |  "
                                 f"{st['landings']} landings  |  {st['airports']} airports  |  "
                                 f"avg score {st['avg_score']:.0f}"
                                 + (f"  |  best touchdown {st['best_fpm']:.0f} fpm" if st["best_fpm"] else ""))

    def _log_sel(self):
        s = self.tv_log.selection()
        return self.logbook.entries[int(s[0])] if s else None

    def log_show(self):
        e = self._log_sel()
        if not e:
            return
        self.log_txt.delete("1.0", "end")
        self.log_txt.insert("1.0", xp_score.report(e))
        shots = [l.get("screenshot") for l in e.get("landings", []) if l.get("screenshot")]
        img = pics.load_image(shots[-1], 420, 200) if shots else None
        self.log_img.config(image=img or "", text="" if img else "(no landing screenshot)")
        self.log_img.image = img
        track = [{"lat": la, "lon": lo, "id": "", "elev": 0, "name": "", "tower": False, "rwys": []}
                 for la, lo in e.get("track", [])]
        if len(track) > 2:
            pics.draw_route_map(self.log_cv, [track[0], track[-1]], track, title="Track flown")
        else:
            self.log_cv.delete("all")

    def log_fav(self):
        e = self._log_sel()
        if e:
            e["favourite"] = not e.get("favourite")
            self.logbook.save()
            self.fill_logbook()

    def log_delete(self):
        e = self._log_sel()
        if e and messagebox.askyesno("Logbook", f"Delete '{e.get('title')}' from the logbook?"):
            self.logbook.remove(e)
            self.fill_logbook()

    def log_export(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="xplane_logbook.csv",
                                         filetypes=[("CSV", "*.csv")])
        if p:
            self.logbook.export_csv(p)
            self.log(f"Logbook exported to {p}")

    def start_grader(self, idea, acname, stops):
        self.stop_grader(save=False)
        api = self.api()
        self.grader = xp_score.FlightGrader(api, idea, acname, self.airports or [], self.logbook,
                                            on_status=lambda t: self.q.put(("live2", t)),
                                            on_event=lambda t: self.log(t),
                                            on_done=lambda e: self.ui(lambda: self.grade_done(e)),
                                            on_sample=self.on_live_sample, xplane_root=self.root())
        self.grader.start()
        self.log("Scoring this flight - land normally and stop; it saves itself to the logbook.")

    def stop_grader(self, save=True):
        g = getattr(self, "grader", None)
        if g and g.is_alive():
            g.stop(save=save)
            if save:
                self.log("Saving the flight to your logbook...")
        self.grader = None if not save else getattr(self, "grader", None)

    def grade_done(self, entry):
        self.fill_logbook()
        try:
            self.fill_career()
        except Exception:
            pass
        self.nb.select(self.tab_log)
        kids = self.tv_log.get_children()
        if kids:
            self.tv_log.selection_set(kids[0])
        self.log(f"Flight scored {entry['score']}/100 and saved to the logbook.")
        self.emergency_debrief(entry)
        leg = getattr(self, "_trip_leg", None)
        if leg and entry.get("route"):
            trip, l = leg
            if l["from"] == entry["route"][0] and l["to"] == entry["route"][-1]:
                self.trips.mark(trip, l, True, entry["score"])
                self.fill_trips()
                self._trip_leg = None

    def emergency_debrief(self, entry=None):
        """After a flight that had a failure, say what happened and how it went."""
        m = getattr(self, "monitor", None)
        kind = getattr(m, "fired_kind", None) if m else None
        if not kind:
            return
        title, advice = link.EMERGENCIES.get(kind, (kind, ""))
        lat, lon, agl, when = (getattr(m, "fired_at", None) or (None, None, None, None))
        lines = [f"EMERGENCY DEBRIEF: {title}"]
        near = None
        if lat is not None and self.airports:
            spot = {"lat": lat, "lon": lon, "id": "?", "name": ""}
            usable = [a for a in self.airports if (self.gen.usable(a) if self.gen else True)]
            if usable:
                near = min(usable, key=lambda a: core.d(spot, a))
                lines.append(f"It happened at {agl:,.0f} ft AGL, {core.d(spot, near):.0f} nm from "
                             f"{near['id']} ({near['name']}) - the nearest field you could have used.")
        if entry and entry.get("route"):
            where = entry["route"][-1]
            if near is not None:
                lines.append(f"You finished at {where}."
                             + ("  Same field - good decision."
                                if where == near["id"] else
                                f"  The nearest was {near['id']}; carrying on is sometimes right, but be "
                                f"honest about why you did it."))
            else:
                lines.append(f"You finished at {where}.")
            if entry.get("minutes") and when:
                mins = max(0.0, (time.time() - when) / 60)
                lines.append(f"You flew about {mins:.0f} more minutes after it broke.")
        lines.append("What the drill looks like: " + advice)
        for t in lines:
            self.log(t)
        messagebox.showinfo("Emergency debrief", "\n\n".join(lines))
        m.fired_kind = None

    # ======================================================================
    # Trips
    # ======================================================================
    def _build_trips(self, f):
        self.trips = exp.TripBook(core.CACHE_DIR / "trips.json")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Trips are multi-leg journeys you fly over several sessions.",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Delete trip", command=self.trip_delete).pack(side="right")
        ttk.Button(top, text="Build a tour...", command=self.build_tour).pack(side="right", padx=6)
        body = ttk.PanedWindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)
        lf = ttk.Frame(body)
        self.tv_trip = ttk.Treeview(lf, columns=("name", "acf", "legs", "done"), show="headings", selectmode="browse")
        for col, h, w in zip(("name", "acf", "legs", "done"), ("Trip", "Aircraft", "Legs", "Flown"),
                             (220, 130, 50, 60)):
            self.tv_trip.heading(col, text=h)
            self.tv_trip.column(col, width=w, anchor="w" if col in ("name", "acf") else "center",
                                stretch=col == "name")
        self.theme.fit_columns(self.tv_trip)
        self.tv_trip.pack(fill="both", expand=True)
        self.tv_trip.bind("<<TreeviewSelect>>", lambda e: self.trip_show())
        rf = ttk.Frame(body)
        self.tv_leg = ttk.Treeview(rf, columns=("leg", "from", "to", "state", "score"), show="headings",
                                   selectmode="browse", height=10)
        for col, h, w in zip(("leg", "from", "to", "state", "score"), ("#", "From", "To", "Status", "Score"),
                             (30, 70, 70, 80, 50)):
            self.tv_leg.heading(col, text=h)
            self.tv_leg.column(col, width=w, anchor="center")
        self.theme.fit_columns(self.tv_leg)
        self.tv_leg.pack(fill="both", expand=True)
        b = ttk.Frame(rf)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Fly this leg  >>", style="Big.TButton", command=self.trip_fly).pack(side="left")
        ttk.Button(b, text="Mark flown", command=lambda: self.trip_mark(True)).pack(side="left", padx=4)
        ttk.Button(b, text="Mark not flown", command=lambda: self.trip_mark(False)).pack(side="left")
        body.add(lf, weight=2)
        body.add(rf, weight=3)
        self.fill_trips()

    def fill_trips(self):
        self.tv_trip.delete(*self.tv_trip.get_children())
        for i, t in enumerate(self.trips.trips):
            done, tot = self.trips.progress(t)
            self.tv_trip.insert("", "end", iid=str(i), values=(t["name"], t.get("aircraft", ""), tot,
                                                               f"{done}/{tot}"))
        self.trip_show()

    def _trip_sel(self):
        s = self.tv_trip.selection()
        return self.trips.trips[int(s[0])] if s else None

    def trip_show(self):
        self.tv_leg.delete(*self.tv_leg.get_children())
        t = self._trip_sel()
        if not t:
            return
        for i, l in enumerate(t["legs"], 1):
            self.tv_leg.insert("", "end", iid=str(i - 1), values=(i, l["from"], l["to"],
                                                                  "flown" if l["done"] else "to fly",
                                                                  l.get("score") or ""))
        nxt = self.trips.next_leg(t)
        if nxt:
            self.tv_leg.selection_set(str(t["legs"].index(nxt)))

    def trip_from_idea(self):
        if not self.idea or len({a["id"] for a in self.idea.stops}) < 2:
            messagebox.showinfo("Trips", "Pick an idea that goes somewhere (at least two different airports).")
            return
        t = self.trips.add_from_idea(self.idea, self.ac()["name"])
        self.fill_trips()
        self.nb.select(self.tab_trips)
        self.log(f"Saved '{t['name']}' as a trip with {len(t['legs'])} legs.")

    def build_tour(self):
        """Make a multi-leg tour (scenic or mixed) and save it as a trip."""
        win = tk.Toplevel(self)
        win.title("Build a tour")
        win.transient(self)
        ttk.Label(win, text="Where:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        v_area = tk.StringVar(value="Whole world")
        ttk.Combobox(win, textvariable=v_area, values=list(core.CONTINENTS), state="readonly",
                     width=26).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(win, text="Legs:").grid(row=1, column=0, sticky="w", padx=6)
        v_legs = tk.StringVar(value="6")
        ttk.Spinbox(win, textvariable=v_legs, from_=2, to=30, width=5).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(win, text="Style:").grid(row=2, column=0, sticky="w", padx=6)
        v_style = tk.StringVar(value="Scenic highlights")
        ttk.Combobox(win, textvariable=v_style, values=["Scenic highlights", "Hidden gems", "Anything nearby"],
                     state="readonly", width=26).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(win, text="Start near (optional):").grid(row=3, column=0, sticky="w", padx=6)
        v_start = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v_start, width=10).grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(win, text="Name:").grid(row=4, column=0, sticky="w", padx=6)
        v_name = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v_name, width=30).grid(row=4, column=1, sticky="w", padx=6)

        def go():
            # everything that touches a Tk variable has to happen here, on the main thread
            area, legs = v_area.get(), int(self.num(v_legs, 6))
            style, start_id, name = v_style.get(), v_start.get().strip(), v_name.get().strip()
            try:
                finder = self.scenic_finder()
            except RuntimeError as e:
                messagebox.showinfo("Tour", str(e))
                return
            rng_max = self.ac()["range"]
            win.destroy()
            self.log(f"Building a {legs}-leg tour ({style.lower()}, {area})...")

            def work():
                try:
                    cands = finder.candidates(None, area, style != "Hidden gems", style != "Scenic highlights") \
                        if style != "Anything nearby" else []
                    stops = []
                    if cands:
                        finder.rng.shuffle(cands)
                        start = finder.gen.find(start_id) if start_id else None
                        pool = [c["stops"][-1] for c in cands]
                        cur = start or pool[0]
                        stops = [cur]
                        left = list(pool)
                        while len(stops) <= legs and left:
                            left.sort(key=lambda a: core.d(cur, a))
                            nxt = next((a for a in left if a["id"] not in {s["id"] for s in stops}
                                        and core.d(cur, a) <= rng_max * 0.85), None)
                            if not nxt:
                                break
                            stops.append(nxt)
                            left.remove(nxt)
                            cur = nxt
                    if len(stops) < 3:
                        gen = finder.gen
                        cur = (gen.find(start_id) if start_id else None) or gen.home()
                        stops = [cur]
                        for _ in range(legs):
                            nxt = gen.pick(gen.within(cur, 25, min(rng_max * 0.5, 250),
                                                      lambda a: a["id"] not in {s["id"] for s in stops}))
                            if not nxt:
                                break
                            stops.append(nxt)
                            cur = nxt
                    if len(stops) < 3:
                        raise ValueError("Couldn't find enough airports there. Try a bigger area, "
                                         "or 'Anything nearby'.")
                    m = finder.rng.randrange(12)
                    idea = core.Idea("tour", name or f"Tour: {stops[0]['id']} to {stops[-1]['id']}",
                                     stops, f"A {len(stops) - 1}-leg tour - fly one leg at a time and tick "
                                            f"them off in the Trips tab.",
                                     month=m, tod="morning", wx=finder.gen.mkwx(stops[-1], m),
                                     notes=[f"{len(stops)} stops, {sum(core.d(stops[i], stops[i + 1]) for i in range(len(stops) - 1)):.0f} nm in total."])
                    self.ui(lambda: self._tour_done(idea))
                except Exception as e:
                    msg = str(e)
                    self.ui(lambda: (self.log("Tour failed: " + msg),
                                     messagebox.showerror("Tour", f"Couldn't build that tour:\n{msg}")))
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(win, text="Build it", command=go).grid(row=5, column=1, sticky="e", padx=6, pady=8)

    def _tour_done(self, idea):
        t = self.trips.add_from_idea(idea, self.ac()["name"])
        self.fill_trips()
        self.nb.select(self.tab_trips)
        self.log(f"Tour saved: {t['name']} with {len(t['legs'])} legs.")

    def trip_delete(self):
        t = self._trip_sel()
        if t and messagebox.askyesno("Trips", f"Delete the trip '{t['name']}'?"):
            self.trips.remove(t)
            self.fill_trips()

    def trip_mark(self, done):
        t = self._trip_sel()
        s = self.tv_leg.selection()
        if t and s:
            self.trips.mark(t, t["legs"][int(s[0])], done)
            self.fill_trips()

    def trip_fly(self):
        t = self._trip_sel()
        s = self.tv_leg.selection()
        if not (t and s):
            messagebox.showinfo("Trips", "Pick a trip and a leg first.")
            return
        leg = t["legs"][int(s[0])]
        try:
            if not self.gen:
                self.gen = self.make_gen(random.randrange(1_000_000))
            idea = self.gen.custom([leg["from"], leg["to"]])
        except (KeyError, ValueError, RuntimeError) as e:
            messagebox.showerror("Trips", str(e.args[0]))
            return
        idea.title = f"{t['name']} - leg {int(s[0]) + 1}: {leg['from']} to {leg['to']}"
        idea.mission = t.get("mission") or idea.mission
        self._trip_leg = (t, leg)
        self._add_idea(idea)
        self.nb.select(1)

    def stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
            self.v_live.set("")

    def repair(self):
        api = self.api()

        def work():
            try:
                api.repair_all()
                self.log("Twist failures repaired.")
            except Exception as e:
                self.log(f"Repair: {e}")
        threading.Thread(target=work, daemon=True).start()


class AirportPicker(tk.Toplevel):
    """Search every airport in the scenery and send one straight into a flight."""

    def __init__(self, app, scope=None):
        super().__init__(app)
        self.app, self.scope = app, scope
        app.theme.track(self, "window")
        self.title("Browse airports")
        self.geometry("980x620")
        self.transient(app)
        q = ttk.Frame(self, padding=6)
        q.pack(fill="x")
        ttk.Label(q, text="Search (code, name or city):").grid(row=0, column=0, sticky="w")
        self.v_q = tk.StringVar()
        e = ttk.Entry(q, textvariable=self.v_q, width=28)
        e.grid(row=0, column=1, sticky="w", padx=4)
        e.bind("<Return>", lambda ev: self.search())
        e.focus_set()
        ttk.Label(q, text="Country:").grid(row=0, column=2, sticky="e")
        self.v_country = tk.StringVar()
        self.cb_country = ttk.Combobox(q, textvariable=self.v_country, width=24,
                                       values=[""] + list(getattr(app, "country_labels", [])))
        self.cb_country.grid(row=0, column=3, sticky="w")
        ttk.Label(q, text="Near:").grid(row=0, column=4, sticky="e")
        self.v_near = tk.StringVar()
        ttk.Entry(q, textvariable=self.v_near, width=8).grid(row=0, column=5, sticky="w")
        self.v_rad = tk.StringVar(value="100")
        ttk.Spinbox(q, textvariable=self.v_rad, from_=5, to=3000, increment=25, width=6).grid(row=0, column=6)
        ttk.Label(q, text="nm").grid(row=0, column=7, sticky="w")

        f2 = ttk.Frame(self, padding=(6, 0))
        f2.pack(fill="x")
        ttk.Label(f2, text="Runway at least").pack(side="left")
        self.v_minrwy = tk.StringVar(value="0")
        ttk.Spinbox(f2, textvariable=self.v_minrwy, from_=0, to=15000, increment=500, width=7).pack(side="left", padx=2)
        ttk.Label(f2, text="ft").pack(side="left")
        self.v_surf = tk.StringVar(value="any")
        ttk.Label(f2, text="   Surface:").pack(side="left")
        ttk.Combobox(f2, textvariable=self.v_surf, values=["any", "paved", "unpaved", "water", "helipad"],
                     state="readonly", width=9).pack(side="left", padx=2)
        self.v_tower = tk.BooleanVar()
        self.v_ils = tk.BooleanVar()
        self.v_fit = tk.BooleanVar(value=True)
        ttk.Checkbutton(f2, text="towered", variable=self.v_tower).pack(side="left", padx=6)
        ttk.Checkbutton(f2, text="has ILS", variable=self.v_ils).pack(side="left")
        ttk.Checkbutton(f2, text="my plane can use it", variable=self.v_fit).pack(side="left", padx=6)
        self.v_type = tk.StringVar(value="any")
        ttk.Label(f2, text="Type:").pack(side="left")
        ttk.Combobox(f2, textvariable=self.v_type, state="readonly", width=14,
                     values=["any", "large airport", "medium airport", "small airport", "heliport",
                             "seaplane base", "has airline service"]).pack(side="left", padx=2)
        ttk.Label(f2, text="Elevation").pack(side="left", padx=(10, 2))
        self.v_elo = tk.StringVar(value="")
        self.v_ehi = tk.StringVar(value="")
        ttk.Entry(f2, textvariable=self.v_elo, width=6).pack(side="left")
        ttk.Label(f2, text="to").pack(side="left")
        ttk.Entry(f2, textvariable=self.v_ehi, width=6).pack(side="left")
        ttk.Label(f2, text="ft").pack(side="left")
        ttk.Button(f2, text="Search", command=self.search).pack(side="right")

        cols = ("id", "name", "where", "elev", "rwy", "surf", "extra", "dist")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col, h, w in zip(cols, ("Code", "Name", "Where", "Elev ft", "Longest", "Surface", "", "nm"),
                             (70, 230, 150, 65, 70, 70, 90, 55)):
            self.tv.heading(col, text=h, command=lambda c=col: self.sort(c))
            self.tv.column(col, width=w, anchor="w" if col in ("id", "name", "where", "extra") else "center",
                           stretch=col == "name")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        app.theme.fit_columns(self.tv)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True, padx=6, pady=4)
        self.tv.bind("<Double-1>", lambda e: self.use("from"))
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.preview())
        self.cv = tk.Canvas(self, height=app.theme.px(150), background="#f3f1ea")
        app.theme.track(self.cv, "canvas")
        self.cv.pack(fill="x", padx=6)
        b = ttk.Frame(self, padding=6)
        b.pack(fill="x")
        ttk.Button(b, text="Depart from here", style="Big.TButton", command=lambda: self.use("from")).pack(side="left")
        ttk.Button(b, text="Search around here", command=lambda: self.use("near")).pack(side="left", padx=4)
        ttk.Button(b, text="Add to the route box", command=lambda: self.use("route")).pack(side="left")
        ttk.Button(b, text="Fly here from...", command=lambda: self.use("to")).pack(side="left", padx=4)
        self.l_info = ttk.Label(b, text="", style="Muted.TLabel")
        self.l_info.pack(side="left", padx=8)
        ttk.Button(b, text="Close", command=self.destroy).pack(side="right")
        self.rows = []
        self.search()

    # ---- searching -----------------------------------------------------------
    def search(self):
        app = self.app
        text = self.v_q.get().strip().upper()
        iso = ""
        t = self.v_country.get().strip()
        m = re.search(r"\(([A-Za-z0-9]{2,3})\)\s*$", t)
        if m:
            iso = m.group(1).upper()
        elif len(t) == 2 and t.isalpha():
            iso = t.upper()
        centre = app.gen.find(self.v_near.get()) if (app.gen and self.v_near.get().strip()) else None
        if self.v_near.get().strip() and not centre:
            centre = next((a for a in app.airports if a["id"].upper() == self.v_near.get().strip().upper()), None)
        rad = app.num(self.v_rad, 100)
        minr = app.num(self.v_minrwy, 0)
        elo = app.num(self.v_elo, -2000)
        ehi = app.num(self.v_ehi, 30000)
        surf = self.v_surf.get()
        gen = app.gen
        out = []
        for a in app.airports:
            if iso and (a.get("iso") or ("US" if core.is_us(a) else "")) != iso:
                continue
            if text and not (a["id"].upper().startswith(text) or text in a["name"].upper()
                             or text in (a.get("city") or "").upper()):
                continue
            if not (elo <= a["elev"] <= ehi):
                continue
            if self.v_tower.get() and not a["tower"]:
                continue
            if self.v_ils.get() and not a.get("ils"):
                continue
            rws = [r for r in a["rwys"] if surf == "any" or
                   (surf == "paved" and r["s"] == "paved") or
                   (surf == "unpaved" and r["s"] in ("grass", "dirt", "gravel", "snow", "lakebed")) or
                   (surf == "water" and r["s"] == "water") or (surf == "helipad" and r["s"] == "helipad")]
            if not rws:
                continue
            longest = max((r["len"] for r in rws), default=0)
            if longest < minr:
                continue
            if self.v_fit.get() and gen and not gen.usable(a):
                continue
            want = self.v_type.get()
            if want != "any":
                if want == "has airline service":
                    if not a.get("sched"):
                        continue
                elif xp_online.TYPE_NAMES.get(a.get("oa_type", ""), "") != want:
                    continue
            dd = core.d(centre, a) if centre else None
            if centre and dd > rad:
                continue
            out.append((a, longest, dd))
            if len(out) > 4000:
                break
        out.sort(key=lambda t: (t[2] if t[2] is not None else 0, -t[1]))
        self.rows = out[:800]
        self.fill()
        self.l_info.config(text=f"{len(out):,} matches" + (" (showing 800)" if len(out) > 800 else ""))

    def fill(self):
        self.tv.delete(*self.tv.get_children())
        for i, (a, longest, dd) in enumerate(self.rows):
            rws = [r for r in a["rwys"] if r["s"] != "helipad"]
            surf = max(rws, key=lambda r: r["len"])["s"] if rws else "helipad"
            extra = ("tower " if a["tower"] else "") + ("ILS" if a.get("ils") else "")
            where = ", ".join(x for x in (a.get("city"), a.get("state"),
                                          a.get("country") or a.get("iso")) if x)[:34]
            self.tv.insert("", "end", iid=str(i), values=(a["id"], a["name"][:40], where, f"{a['elev']:,}",
                                                          f"{longest:,}" if longest else "", surf, extra,
                                                          f"{dd:.0f}" if dd is not None else ""))

    def sort(self, col):
        keys = {"id": lambda t: t[0]["id"], "name": lambda t: t[0]["name"], "where": lambda t: t[0].get("state", ""),
                "elev": lambda t: -t[0]["elev"], "rwy": lambda t: -t[1], "surf": lambda t: t[0]["rwys"][0]["s"],
                "extra": lambda t: (not t[0]["tower"], not t[0].get("ils")),
                "dist": lambda t: t[2] if t[2] is not None else 0}
        self.rows.sort(key=keys[col])
        self.fill()

    def selected(self):
        s = self.tv.selection()
        return self.rows[int(s[0])][0] if s else None

    def preview(self):
        a = self.selected()
        if a:
            pics.draw_airport(self.cv, a)

    def use(self, what):
        a = self.selected()
        if not a:
            return
        app = self.app
        v = getattr(app, "rt_" + self.scope, None) if self.scope else None
        if what == "from":
            (v["from"] if v else app.v_from).set(a["id"])
            app.log(f"Departures set to {a['id']} {a['name']}.")
        elif what == "near":
            (v["near"] if v else app.v_near).set(a["id"])
            if not v:
                app.v_area.set(AREAS["near"])
                app.on_area()
            app.log(f"Searching around {a['id']}.")
        elif what == "route":
            app.v_custom.set((app.v_custom.get() + " " + a["id"]).strip())
            app.log(f"Added {a['id']} to the route box - press 'Use route' when it's complete.")
        elif what == "to":
            start = app.v_from.get().strip() or (app.idea.stops[0]["id"] if app.idea else "")
            if not start:
                messagebox.showinfo("Airports", "Set a departure airport first (or use 'Depart from here').")
                return
            app.v_custom.set(f"{start} {a['id']}")
            app.custom_route()
            self.destroy()


class Tooltip:
    def __init__(self, w, text):
        self.w, self.text, self.tip = w, text, None
        w.bind("<Enter>", self.show)
        w.bind("<Leave>", self.hide)

    def show(self, e=None):
        x, y = self.w.winfo_rootx() + 20, self.w.winfo_rooty() + 22
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=4, pady=2).pack()

    def hide(self, e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)   # crisp text on high-DPI Windows screens
    except Exception:
        pass
    App().mainloop()
