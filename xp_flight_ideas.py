#!/usr/bin/env python3
"""
xp_flight_ideas.py - generate interesting general-aviation flight ideas for X-Plane 11/12.

This is the engine (and a command-line tool). For the point-and-click version,
run  xp_flight_ideas_gui.py  - it can also start the flight in X-Plane 12.4+
(aircraft, position, time, weather) and push the route into the GPS/FMS.

It reads X-Plane's own airport database (apt.dat, including your Custom Scenery)
and nav data (for ILS approaches), then builds missions such as backcountry
strips, short-field challenges, high density-altitude arrivals, crosswind
practice, night currency, IFR approaches, island runs, multi-stop tours,
"mystery destination" dead-reckoning flights and curated scenic routes.

Command-line examples
    python xp_flight_ideas.py                       # 5 ideas, C172, anywhere in the US
    python xp_flight_ideas.py -a cub --from KMYL    # Super Cub ideas from McCall, ID
    python xp_flight_ideas.py -a baron -m ifr -n 3  # three IFR missions in a Baron
    python xp_flight_ideas.py --state CO --save     # Colorado ideas, write .fms plans
    python xp_flight_ideas.py --list                # list aircraft and mission types

First run scans X-Plane's scenery (can take 30-90 s); results are cached in
~/.xp_flight_ideas so later runs start in about a second.
Requires only Python 3.8+ (no extra packages).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xp_wx import CONTINENTS, in_area   # noqa: E402  (lat/lon boxes for continents)

VERSION = "6.1"
CACHE_DIR = Path.home() / ".xp_flight_ideas"
CACHE_FORMAT = 8

# --------------------------------------------------------------------------
# Aircraft profiles - edit or add your own.
#   cruise  : knots TAS          range   : nm, still air, with reserve
#   min_rwy : shortest runway (ft) you'd be comfortable with at sea level
#   surfaces: runway surfaces it can use   xwind : crosswind you want to practice up to
#   match   : words used to recognise this type from an X-Plane .acf file name
# --------------------------------------------------------------------------
SOFT = {"paved", "grass", "dirt", "gravel", "lakebed"}
AIRCRAFT = {
    "c172":   dict(name="Cessna 172 SP", cruise=115, range=450, min_rwy=1600, surfaces=SOFT,
                   xwind=15, ceiling=13000, night=True, ifr=True, water=False, heli=False, multi=False,
                   match=["172", "152", "150", "182", "archer", "pa28", "pa-28", "warrior", "da40", "c182"]),
    "cub":    dict(name="Piper PA-18 Super Cub", cruise=90, range=330, min_rwy=500, surfaces=SOFT | {"snow"},
                   xwind=12, ceiling=15000, night=False, ifr=False, water=False, heli=False, multi=False,
                   match=["cub", "pa18", "pa-18", "carbon", "husky", "savage", "aerolite", "ultralight"]),
    "l5":     dict(name="Stinson L-5 Sentinel", cruise=90, range=300, min_rwy=700, surfaces=SOFT,
                   xwind=10, ceiling=14000, night=False, ifr=False, water=False, heli=False, multi=False,
                   match=["l-5", "l5", "stinson", "cessna 140", "champ", "citabria", "j3"]),
    "rv10":   dict(name="Van's RV-10", cruise=155, range=800, min_rwy=1800, surfaces={"paved", "grass"},
                   xwind=15, ceiling=17000, night=True, ifr=True, water=False, heli=False, multi=False,
                   match=["rv-10", "rv10", "rv-", "bonanza", "mooney", "comanche", "arrow"]),
    "sr22":   dict(name="Cirrus SR22", cruise=170, range=900, min_rwy=2500, surfaces={"paved"},
                   xwind=18, ceiling=17500, night=True, ifr=True, water=False, heli=False, multi=False,
                   match=["sr22", "sr20", "cirrus sr", "columbia", "ttx", "cessna 400"]),
    "baron":  dict(name="Beechcraft Baron 58", cruise=190, range=900, min_rwy=3000, surfaces={"paved"},
                   xwind=20, ceiling=20000, night=True, ifr=True, water=False, heli=False, multi=True,
                   match=["baron", "seneca", "seminole", "da42", "da62", "310", "aztec", "twin"]),
    "kingair": dict(name="Beechcraft King Air C90", cruise=230, range=1100, min_rwy=3300,
                    surfaces={"paved", "gravel"}, xwind=22, ceiling=30000, night=True, ifr=True,
                    water=False, heli=False, multi=True,
                    match=["king air", "kingair", "c90", "b200", "b350", "pc-12", "pc12", "caravan", "c208"]),
    "evo":    dict(name="Lancair Evolution", cruise=270, range=1200, min_rwy=3000, surfaces={"paved"},
                   xwind=20, ceiling=28000, night=True, ifr=True, water=False, heli=False, multi=False,
                   match=["evolution", "lancair", "tbm", "m600", "meridian"]),
    "sf50":   dict(name="Cirrus SF50 Vision Jet", cruise=300, range=1000, min_rwy=4000, surfaces={"paved"},
                   xwind=16, ceiling=31000, night=True, ifr=True, water=False, heli=False, multi=False,
                   match=["sf50", "vision", "citation", "phenom", "hondajet", "eclipse", "cj"]),
    "kodiak": dict(name="Kodiak 100 (bush turboprop)", cruise=170, range=900, min_rwy=1000,
                   surfaces=SOFT | {"snow"}, xwind=20, ceiling=25000, night=True, ifr=True,
                   water=False, heli=False, multi=False, match=["kodiak", "porter", "pc-6", "twin otter", "dhc6"]),
    "float":  dict(name="Amphibian / floatplane (Beaver, Caravan amphib...)", cruise=120, range=400,
                   min_rwy=2000, surfaces={"paved", "grass"}, xwind=12, ceiling=15000, night=False,
                   ifr=False, water=True, heli=False, multi=False,
                   match=["float", "amphib", "beaver", "otter", "seaplane", "icon", "a5", "goose", "lake"]),
    "heli":   dict(name="Helicopter (R22, S-76...)", cruise=110, range=250, min_rwy=0, surfaces=set(),
                   xwind=15, ceiling=10000, night=True, ifr=False, water=False, heli=True, multi=False,
                   match=["r22", "r44", "r66", "s-76", "s76", "bell", "206", "407", "ec135", "h125", "as350",
                          "helicopter", "heli", "cabri", "robinson", "sikorsky"]),
}

NOT_GENERATED = ("custom", "shared")

MISSIONS = {
    "burger":      "The $100 hamburger - short hop for lunch and back",
    "backcountry": "Short unpaved strips, often up in the hills",
    "shortfield":  "The shortest runway your aircraft can reasonably use",
    "highalt":     "High-elevation airport on a hot day (density altitude)",
    "crosswind":   "Single-runway airport with a stiff crosswind",
    "xc":          "Classic cross-country with a touch-and-go en route",
    "tour":        "Multi-stop airport-hopping tour",
    "night":       "Night flight to a lighted runway",
    "ifr":         "Low IFR: fly the ILS to minimums, alternate planned",
    "mystery":     "Mystery destination: only a heading and distance",
    "scenic":      "Curated scenic destinations and routes (worldwide)",
    "island":      "Over-water run to an island airport",
    "bigairport":  "Small plane into a busy towered airport",
    "ferry":       "Long ferry flight with a fuel stop",
    "seaplane":    "Water landings (float/amphibian aircraft)",
    "medevac":     "Helicopter hospital run",
    "realwx":      "Live weather: fly into real bad weather happening right now (internet)",
    "cargo":       "Bush cargo run: heavy load into a short strip",
    "sightsee":    "Sightseeing tour: overfly the sights, land at the end",
    "aerobatic":   "Aerobatic / airwork practice overhead one airport",
    "soaring":     "Soaring task (gliders): a triangle with no engine",
    "alphabet":    "Alphabet challenge: land at airports A, B, C...",
    "mail":        "Mail run: several stops against the clock",
    "radionav":    "Radio navigation: VOR to VOR with no GPS",
    "checkride":   "Checkride: fly the whole practical test in one flight",
    "poker":       "Poker run: five airports, five cards, best hand",
    "photo":       "Aerial photography: get the shot at the right height and light",
    "organ":       "Urgent medical transport against a hard deadline",
    "sar":         "Search and rescue: fly a search pattern, then land nearby",
    "patrol":      "Pipeline / powerline patrol at low level",
    "timetrial":   "Time trial: fastest time between two airports",
    "hold":        "IFR holding pattern, then the approach",
    "circuits":    "Circuit practice: a set of patterns, each one different",
    "diversion":   "Diversion: your destination shuts and you divert in the air",
    "pass":        "Mountain pass crossing at the lowest safe level",
    "survey":      "Aerial survey: fly a grid of straight lines at a set height",
    "firewatch":   "Fire spotting patrol over the forest, then a short strip",
    "nordo":       "No radio: non-towered arrival with the radio out",
    "dawn":        "Dawn patrol: wheels up in the dark, sunrise on the way",
    "lowceil":     "Low ceiling: marginal VFR under a low overcast, with a decision to make",
    "lowvis":      "Low visibility: an approach down to minimums in fog or heavy haze",
    "custom":      "Your own route",
    "shared":      "A route another pilot shared (flightplandatabase.com)",
}

# Short friendly names and the groups the app shows them in
MISSION_NAMES = {
    "burger": "$100 hamburger", "backcountry": "Backcountry strips", "shortfield": "Short field",
    "highalt": "High and hot", "crosswind": "Crosswind", "xc": "Cross-country", "tour": "Airport tour",
    "night": "Night flight", "ifr": "IFR to minimums", "mystery": "Mystery destination",
    "scenic": "Scenic places", "island": "Island hop", "bigairport": "Into a big airport",
    "ferry": "Long ferry flight", "seaplane": "Water landings", "medevac": "Helicopter hospital run",
    "realwx": "Live weather now", "cargo": "Bush cargo run", "sightsee": "Sightseeing tour",
    "aerobatic": "Airwork and aerobatics", "soaring": "Soaring task", "alphabet": "Alphabet challenge",
    "mail": "Mail run", "radionav": "VOR and NDB only", "checkride": "Checkride", "poker": "Poker run",
    "photo": "Aerial photography", "organ": "Urgent transport", "sar": "Search and rescue",
    "patrol": "Pipeline patrol", "timetrial": "Time trial", "hold": "Holding pattern",
    "circuits": "Circuit practice", "diversion": "Diversion", "pass": "Mountain pass",
    "survey": "Survey grid", "firewatch": "Fire patrol", "nordo": "No radio", "dawn": "Dawn patrol",
    "lowceil": "Low ceiling", "lowvis": "Low visibility",
    "custom": "Your own route", "shared": "A shared route",
}

MISSION_GROUPS = {
    "Everyday flying":        ["burger", "xc", "tour", "night", "dawn", "circuits", "bigairport",
                               "ferry", "mail", "timetrial", "mystery"],
    "Backcountry & short fields": ["backcountry", "shortfield", "highalt", "cargo", "seaplane", "pass",
                                   "firewatch"],
    "Weather & instruments":  ["ifr", "hold", "lowceil", "lowvis", "crosswind", "diversion", "nordo",
                               "radionav", "realwx"],
    "Scenery & sightseeing":  ["scenic", "island", "sightsee", "photo", "survey", "patrol"],
    "Training & challenges":  ["checkride", "aerobatic", "soaring", "alphabet", "poker", "medevac",
                               "organ", "sar"],
}

MISSION_PRESETS = {
    "A bit of everything": [k for k in MISSIONS if k not in ("custom", "shared", "realwx")],
    "Easy day out":        ["burger", "xc", "tour", "scenic", "island", "sightsee", "dawn", "photo"],
    "IFR practice":        ["ifr", "hold", "lowceil", "lowvis", "radionav", "diversion", "crosswind"],
    "Bush and backcountry": ["backcountry", "shortfield", "highalt", "cargo", "pass", "firewatch",
                             "seaplane", "patrol"],
    "Sharpen your flying": ["checkride", "circuits", "crosswind", "shortfield", "timetrial", "diversion",
                            "nordo", "aerobatic"],
}


SCENIC_DEST = {
    "KLXV": "Leadville, CO - highest public-use airport in North America (~9,900 ft). Mind the density altitude.",
    "KTEX": "Telluride, CO - mesa-top runway at ~9,000 ft with a drop-off at both ends.",
    "KASE": "Aspen, CO - one way in, one way out, mountains on three sides.",
    "KSEZ": "Sedona, AZ - runway on top of a mesa surrounded by red rock.",
    "KGCN": "Grand Canyon, AZ - stay in the SFRA corridors and enjoy the view.",
    "KPGA": "Page, AZ - Lake Powell, Glen Canyon Dam and Horseshoe Bend nearby.",
    "KBCE": "Bryce Canyon, UT - hoodoos and pink cliffs at ~7,600 ft.",
    "KCNY": "Moab / Canyonlands, UT - Arches and Canyonlands right outside the window.",
    "L06":  "Furnace Creek, CA - Death Valley, runway below sea level.",
    "KMMH": "Mammoth Yosemite, CA - high Sierra, Long Valley caldera.",
    "KTRK": "Truckee-Tahoe, CA - Lake Tahoe just over the ridge.",
    "KAVX": "Catalina Island, CA - 'Airport in the Sky', a hilltop runway with a hump in the middle.",
    "KHAF": "Half Moon Bay, CA - coastal strip; fly the shoreline up past Pacifica.",
    "KMRY": "Monterey, CA - Big Sur coast and Pebble Beach.",
    "KMHV": "Mojave, CA - the aircraft boneyard and the spaceport.",
    "KJAC": "Jackson Hole, WY - inside Grand Teton National Park.",
    "KWYS": "West Yellowstone, MT - gateway to Yellowstone.",
    "KSUN": "Sun Valley / Hailey, ID - tight valley approach.",
    "3U2":  "Johnson Creek, ID - the classic Idaho backcountry strip.",
    "U60":  "Big Creek, ID - deep in the Frank Church wilderness.",
    "KFHR": "Friday Harbor, WA - San Juan Islands, watch for orcas.",
    "KORS": "Eastsound / Orcas Island, WA - San Juan Islands.",
    "KBID": "Block Island, RI - small island, big crosswinds.",
    "KMVY": "Martha's Vineyard, MA.",
    "KACK": "Nantucket, MA - 26 nm out to sea; fog loves it.",
    "KMCD": "Mackinac Island, MI - no cars on the island; take a carriage to town.",
    "3W2":  "Put-in-Bay, OH - Lake Erie islands.",
    "KFFA": "First Flight, NC - land next to the Wright Brothers memorial.",
    "W95":  "Ocracoke Island, NC - Outer Banks beach strip.",
    "TGI":  "Tangier Island, VA - Chesapeake Bay, crab-shack country.",
    "KEYW": "Key West, FL - end of the road, over-water all the way down the Keys.",
    "KOSH": "Oshkosh, WI - Wittman Regional, home of AirVenture.",
    "PHLU": "Kalaupapa, HI - under the world's tallest sea cliffs on Molokai.",
    "PHNY": "Lanai, HI.",
    "PAWD": "Seward, AK - fly Turnagain Arm and over the Kenai Mountains.",
    "PALH": "Lake Hood, AK - the world's busiest seaplane base.",
    # --- rest of the world ---
    "LFLJ": "Courchevel, France - an altiport in the Alps with a steeply sloped, very short runway.",
    "VNLK": "Lukla, Nepal - a short, sloping strip at ~9,300 ft; gateway to Everest.",
    "TNCS": "Saba - one of the shortest commercial runways anywhere, with cliffs at both ends.",
    "TFFJ": "St Barthelemy - dive over a hilltop road, land toward the beach.",
    "TNCM": "St Maarten - the famous low approach over Maho Beach.",
    "LXGB": "Gibraltar - the runway crosses the main road, with the Rock beside you.",
    "LPMA": "Madeira - a runway extended over the sea on pillars; tricky winds.",
    "EGPR": "Barra, Scotland - land on the beach (between tides).",
    "LOWI": "Innsbruck, Austria - a valley approach between the Alps.",
    "LSZS": "Samedan, Switzerland - Europe's highest airport, in the Engadin valley.",
    "NZQN": "Queenstown, New Zealand - between the Remarkables and Lake Wakatipu.",
    "NZMF": "Milford Sound, New Zealand - fly the fiords.",
    "VQPR": "Paro, Bhutan - a winding Himalayan valley approach.",
    "ENSB": "Svalbard - the far north, halfway to the pole.",
    "EKVG": "Vagar, Faroe Islands - fjord approach, wild weather.",
    "SAWH": "Ushuaia, Argentina - the end of the world, beside the Beagle Channel.",
    "ENTC": "Tromso, Norway - Arctic fjords (try it at night for the northern lights).",
}
SCENIC_ROUTES = [
    (["KCDW", "KFRG"], "Hudson River Corridor",
     "Enter the Hudson River exclusion below 1,300 ft, fly south past Midtown and the Statue of Liberty, "
     "then east along Long Island's south shore. Self-announce on 123.05."),
    (["KHYA", "KACK", "KMVY", "KBID"], "Cape Cod island hop", "Three islands, lots of water, maybe some fog."),
    (["KTMB", "KMTH", "KEYW"], "Down the Florida Keys", "Follow the Overseas Highway at 1,500 ft."),
    (["KTDZ", "3W2"], "Lake Erie islands", "Short hop over Lake Erie to the Bass Islands."),
    (["KBIH", "KMMH", "KTRK"], "Eastern Sierra crest", "Follow US-395 north with 14,000 ft peaks off the left wing."),
    (["KBIH", "L06"], "Into Death Valley", "Cross the Inyo Mountains and descend to below sea level."),
    (["KGCN", "KPGA"], "Grand Canyon to Lake Powell", "Use the Grand Canyon SFRA corridors."),
    (["KPGA", "KBCE", "KCNY"], "Utah canyon country", "Lake Powell, Bryce and Canyonlands in one day."),
    (["KMQI", "KFFA", "W95"], "Outer Banks", "Beach-hug down the Outer Banks from Manteo to Ocracoke."),
    (["KBLI", "KORS", "KFHR"], "San Juan Islands", "Island hopping in Puget Sound."),
    (["PHOG", "PHNY", "PHMK", "PHLU"], "Maui County hop", "Maui, Lanai, Molokai and the Kalaupapa sea cliffs."),
    (["KSBA", "KSBP", "KMRY", "KHAF"], "California coast", "Coast-hug from Santa Barbara to Half Moon Bay."),
    (["KJAC", "KWYS"], "Tetons to Yellowstone",
     "Fly up the Teton range, then over Yellowstone Lake (stay above 2,000 ft AGL in the park)."),
    (["KMYL", "3U2", "U60"], "Idaho backcountry", "River canyons and dirt strips in the Frank Church wilderness."),
    (["KESN", "TGI"], "Chesapeake Bay", "Across the bay to Tangier Island."),
    (["PAMR", "PAWD"], "Turnagain Arm", "Follow the arm south from Anchorage through the pass to Seward."),
    (["KPLN", "KMCD"], "Straits of Mackinac", "Cross the Mackinac Bridge to the island."),
    (["LSZB", "LSZS", "LSGS"], "Swiss Alps", "Bern to Samedan to Sion - glaciers, passes and the Matterhorn nearby."),
    (["NZQN", "NZMF"], "Queenstown to Milford Sound", "Over the Southern Alps and into the fiord."),
    (["TNCM", "TFFJ", "TNCS"], "Caribbean island hop", "Maho Beach, St Barth's hill and Saba's cliffs."),
    (["EGPO", "EGPR"], "Outer Hebrides", "Stornoway to the beach runway at Barra."),
    (["ENBR", "ENSG"], "Norwegian fjords", "Bergen to Sogndal along the Sognefjord."),
    (["VNKT", "VNLK"], "Himalaya", "Kathmandu to Lukla through the mountains."),
]

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico",
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
MONTH_TEMP = [3, 5, 10, 16, 21, 26, 29, 28, 24, 18, 11, 5]   # rough afternoon temps (C) near 40N

TIMES = {  # key: (label, hour or None for sunset-relative)
    "dawn": ("dawn", None), "morning": ("morning", 9.0), "midday": ("midday", 12.5),
    "afternoon": ("afternoon", 15.5), "golden": ("golden hour", None), "night": ("night", None),
}

# Sky presets: text, cloud layers [(type, cover 0-1, base ft AGL, thickness ft)], visibility SM, precip 0-1
SKY = {
    "clear":     ("Clear skies, 10+ SM", [], 30, 0),
    "few":       ("Few clouds at 6,500 ft AGL", [("cumulus", 0.15, 6500, 2000)], 25, 0),
    "sct":       ("Scattered at 4,500 ft AGL, 10 SM", [("cumulus", 0.4, 4500, 2500)], 10, 0),
    "cu":        ("Scattered cumulus at 5,500 ft AGL", [("cumulus", 0.45, 5500, 4000)], 15, 0),
    "highovc":   ("High thin overcast at 20,000 ft", [("cirrus", 0.9, 20000, 2000)], 20, 0),
    "bkn28":     ("Broken at 2,800 ft AGL, 5 SM in haze", [("stratus", 0.7, 2800, 1800)], 5, 0),
    "sctbkn":    ("Scattered 1,800 ft, broken 3,500 ft AGL, 6 SM",
                  [("cumulus", 0.4, 1800, 1200), ("stratus", 0.7, 3500, 2000)], 6, 0),
    "ovc8":      ("Overcast 800 ft AGL, 3 SM in light rain", [("stratus", 1.0, 800, 4000)], 3, 0.3),
    "ovc3":      ("Overcast 300 ft AGL, 3/4 SM in mist", [("stratus", 1.0, 300, 2500)], 0.75, 0),
    "ovc5ra":    ("Overcast 500 ft AGL, 1 1/2 SM in rain", [("stratus", 1.0, 500, 6000)], 1.5, 0.5),
    "vv2":       ("Fog: vertical visibility 200 ft, 1/2 SM", [("stratus", 1.0, 200, 1500)], 0.5, 0),
    "bkn4ovc12": ("Broken 400 ft, overcast 1,200 ft AGL, 2 SM drizzle",
                  [("stratus", 0.7, 400, 600), ("stratus", 1.0, 1200, 4000)], 2, 0.3),
    "tstorm":    ("Scattered thunderstorms, bases 4,000 ft AGL", [("cumulonimbus", 0.4, 4000, 25000)], 8, 0.6),
    # --- low ceilings (v4.6) ---
    "ovc25":     ("Overcast 2,500 ft AGL, 8 SM", [("stratus", 1.0, 2500, 3000)], 8, 0),
    "bkn15":     ("Broken 1,500 ft AGL, 6 SM", [("stratus", 0.7, 1500, 2000)], 6, 0),
    "ovc12ra":   ("Overcast 1,200 ft AGL, 4 SM in rain", [("stratus", 1.0, 1200, 5000)], 4, 0.4),
    "ovc10":     ("Overcast 1,000 ft AGL, 3 SM - MVFR/IFR line", [("stratus", 1.0, 1000, 4000)], 3, 0.1),
    "bkn6":      ("Broken 600 ft AGL, 2 SM", [("stratus", 0.7, 600, 2500)], 2, 0),
    "ovc4sn":    ("Overcast 400 ft AGL, 1 SM in snow", [("stratus", 1.0, 400, 5000)], 1, 0.5),
    "ovc2":      ("Overcast 200 ft AGL, 1/2 SM - CAT I minimums",
                  [("stratus", 1.0, 200, 3000)], 0.5, 0.1),
    "ovc1":      ("Overcast 100 ft AGL, 1/4 SM - below CAT I",
                  [("stratus", 1.0, 100, 2500)], 0.25, 0),
    # --- low visibility with a high or no ceiling (v4.6) ---
    "haze3":     ("Hazy, few clouds, 3 SM in haze", [("cumulus", 0.15, 7000, 2000)], 3, 0),
    "haze15":    ("Thick haze, 1 1/2 SM, clear above", [], 1.5, 0),
    "smoke1":    ("Smoke or dust, 1 SM, sun barely visible", [], 1, 0),
    "mist34":    ("Mist under a high overcast, 3/4 SM", [("stratus", 1.0, 3500, 3000)], 0.75, 0),
    "fog12":     ("Shallow fog, 1/2 SM, clear above", [], 0.5, 0),
    "fog14":     ("Dense fog, 1/4 SM", [("stratus", 1.0, 100, 1200)], 0.25, 0),
}
VFR_GOOD = ["clear", "few", "sct", "cu", "highovc"]
VFR_MARG = ["bkn28", "sctbkn", "ovc25", "bkn15", "haze3"]
IFR_SKY = ["ovc3", "ovc5ra", "vv2", "bkn4ovc12", "ovc10", "bkn6", "ovc4sn", "ovc12ra"]
LOW_CEILING = ["ovc10", "bkn6", "ovc4sn", "ovc2", "ovc1", "ovc3", "bkn4ovc12", "ovc5ra"]
LOW_VIS = ["haze15", "smoke1", "mist34", "fog12", "fog14", "vv2", "ovc2", "ovc1"]
MINIMUMS = ["ovc2", "ovc1", "vv2", "fog14"]

M_TO_FT = 3.28084


# ==========================================================================
# Geometry helpers
# ==========================================================================
def dist_nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(a)))


def course(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def d(a, b):
    return dist_nm(a["lat"], a["lon"], b["lat"], b["lon"])


def crs(a, b):
    return course(a["lat"], a["lon"], b["lat"], b["lon"])


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def _dest_point(lat, lon, brg, dist_nm):
    R = 3440.065
    p1, l1, b, dr = math.radians(lat), math.radians(lon), math.radians(brg), dist_nm / R
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def interp(a, b, f):
    """Point a fraction f of the way from a to b (fine for GA distances)."""
    return {"lat": a["lat"] + (b["lat"] - a["lat"]) * f, "lon": a["lon"] + (b["lon"] - a["lon"]) * f, "id": "_pt"}


def _solar(month, lat=40.0):
    """(sunrise, sunset) in local clock hours - rough, with daylight saving outside the tropics."""
    doy = 15 + 30.4 * month
    amp = max(-5.5, min(5.5, 1.5 * lat / 40 * (1 + max(0, abs(lat) - 45) / 25)))
    half = 6 + amp * math.cos((doy - 172) / 365 * 2 * math.pi)
    half = max(1.0, min(11.5, half))
    if lat > 23:
        dst = 1 if 2 <= month <= 9 else 0
    elif lat < -23:
        dst = 1 if month >= 9 or month <= 2 else 0
    else:
        dst = 0
    noon = 12.3 + dst
    return noon - half, noon + half


def sunset_hour(month, lat=40.0):
    return _solar(month, lat)[1]


def hour_for(tod, month, lat=40.0):
    lbl, h = TIMES[tod]
    if h is not None:
        return h
    rise, ss = _solar(month, lat)
    return {"dawn": rise - 0.2, "golden": ss - 1.0, "night": min(23.5, ss + 2.0)}[tod]


def fmt_hour(h):
    h = h % 24
    return f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}"


# ==========================================================================
# Weather
# ==========================================================================
def vis_str(sm):
    """Visibility the way a METAR reads it: 1/4, 1/2, 3/4, 1 1/2, 3, 10+..."""
    fr = {0.25: "1/4", 0.5: "1/2", 0.75: "3/4", 1.25: "1 1/4", 1.5: "1 1/2", 1.75: "1 3/4", 2.5: "2 1/2"}
    for k, v in fr.items():
        if abs(sm - k) < 0.02:
            return v + " SM"
    if sm >= 10:
        return "10+ SM"
    return f"{sm:g} SM"


def cover_word(c):
    return "Few" if c < 0.25 else "Scattered" if c < 0.5 else "Broken" if c < 0.9 else "Overcast"


def sky_phrase(layers, vis):
    """Plain-English sky for a set of cloud layers, e.g. 'Broken 600 ft AGL, 1/2 SM'."""
    if not layers:
        base = "Clear skies"
    else:
        bits = []
        for i, (t, c, b, th) in enumerate(sorted(layers, key=lambda l: l[2])[:3]):
            word = "fog: vertical visibility" if (c >= 0.9 and b <= 300) else cover_word(c).lower()
            bits.append(f"{word} {b:,.0f} ft")
        base = ", ".join(bits) + " AGL"
        base = base[0].upper() + base[1:]
    return f"{base}, {vis_str(vis)}"


class Wx:
    """Structured weather that can be described in words and sent to X-Plane."""

    def __init__(self, sky="clear", wind_dir=0, wind_spd=0, gust=0, temp=15, altimeter=29.92, vis=None,
                 layers=None, sky_text=None, precip=None):
        """sky is a key of SKY - or pass layers/sky_text/precip for custom weather (e.g. a live METAR)."""
        self.custom = layers is not None
        if self.custom:
            sky = "metar"
            self._layers, self._text, self._precip = list(layers), sky_text or "Custom clouds", precip or 0.0
        self.sky, self.wind_dir, self.wind_spd, self.gust = sky, int(wind_dir) % 360, int(wind_spd), int(gust)
        self.temp, self.altimeter = int(round(temp)), altimeter
        self.vis = vis if vis is not None else (10 if self.custom else SKY[sky][2])
        self.wind_text = ""   # filled in by the generator (favoured runway etc.)
        self.extra = ""
        self.metar = None     # raw METAR text when built from live weather

    @property
    def layers(self):
        return self._layers if self.custom else SKY[self.sky][1]

    @property
    def sky_text(self):
        return self._text if self.custom else SKY[self.sky][0]

    @property
    def precip(self):
        return self._precip if self.custom else SKY[self.sky][3]

    @property
    def ceiling(self):
        """Height AGL of the lowest broken/overcast layer, or None if there isn't one."""
        for t, c, b, th in self.layers:
            if c >= 0.5:
                return int(b)
        return None

    def set_ceiling(self, ft):
        """Move (or create) the ceiling. ft=None or 0 clears it; anything else is ft AGL."""
        layers = [list(x) for x in self.layers]
        low = next((l for l in layers if l[1] >= 0.5), None)
        if not ft:
            layers = [l for l in layers if l[1] < 0.5]
        elif low:
            shift = int(ft) - low[2]
            for l in layers:
                l[2] = max(100, l[2] + shift)
        else:
            layers.append(["stratus", 1.0, max(100, int(ft)), 2500])
        layers.sort(key=lambda l: l[2])
        self._layers = [tuple(l) for l in layers]
        self._precip = self.precip
        self._text = sky_phrase(self._layers, self.vis)
        self.custom = True
        self.sky = "metar"
        return self

    def set_vis(self, sm):
        sm = max(0.05, float(sm))
        if not self.custom and abs(sm - SKY[self.sky][2]) > 0.01:
            self._layers, self._precip = list(self.layers), self.precip
            self.custom, self.sky = True, "metar"
        self.vis = sm
        if self.custom:
            self._text = sky_phrase(self._layers, self.vis)
        return self

    def flight_rules(self):
        """VFR / MVFR / IFR / LIFR from the ceiling and visibility, the usual US thresholds."""
        c, v = self.ceiling, self.vis
        if (c is not None and c < 500) or v < 1:
            return "LIFR"
        if (c is not None and c < 1000) or v < 3:
            return "IFR"
        if (c is not None and c < 3000) or v < 5:
            return "MVFR"
        return "VFR"

    def copy(self):
        w = Wx(self.sky, self.wind_dir, self.wind_spd, self.gust, self.temp, self.altimeter, self.vis,
               *((self._layers, self._text, self._precip) if self.custom else ()))
        w.wind_text, w.extra, w.metar = self.wind_text, self.extra, self.metar
        w.station = getattr(self, "station", None)
        return w

    def wind_str(self):
        if self.wind_spd <= 2:
            return "wind calm"
        return f"wind {self.wind_dir or 360:03d}@{self.wind_spd}" + (f"G{self.wind_spd + self.gust}" if self.gust else "")

    def describe(self):
        txt = self.sky_text
        if not self.custom and self.vis != SKY[self.sky][2]:
            txt += f" (vis {vis_str(self.vis)})"
        rules = self.flight_rules()
        c = self.ceiling
        tag = f" [{rules}" + (f", ceiling {c:,} ft" if c is not None else "") + "]" if rules != "VFR" else ""
        return (f"{txt}, {self.temp} C, altimeter {self.altimeter:.2f}, "
                f"{self.wind_text or self.wind_str()}{self.extra}{tag}")

    def to_xplane(self, lat, lon, elev_ft):
        """X-Plane 12.4 flight-initialization 'weather' object (custom definition)."""
        layers, precip = self.layers, self.precip
        xp_type = {"cumulonimbus": "cumulunimbus"}   # X-Plane's spelling
        clouds = [{"type": xp_type.get(t, t), "cover_ratio": c, "bases_in_feet_msl": int(elev_ft + b),
                   "tops_in_feet_msl": int(elev_ft + b + th)} for t, c, b, th in layers][:3]
        turb = min(1.0, 0.05 + self.gust / 40)
        winds = [
            {"altitude_in_feet_msl": int(elev_ft + 500), "speed_in_knots": self.wind_spd,
             "direction_in_degrees_true": self.wind_dir, "gust_increase_in_knots": self.gust,
             "shear_in_degrees": 0, "turbulence_ratio": round(turb, 2)},
            {"altitude_in_feet_msl": int(elev_ft + 3500), "speed_in_knots": int(self.wind_spd * 1.25 + 4),
             "direction_in_degrees_true": (self.wind_dir + 15) % 360, "gust_increase_in_knots": 0,
             "shear_in_degrees": 0, "turbulence_ratio": round(turb / 2, 2)},
            {"altitude_in_feet_msl": int(max(elev_ft + 7000, 10000)), "speed_in_knots": int(self.wind_spd * 1.5 + 8),
             "direction_in_degrees_true": (self.wind_dir + 30) % 360, "gust_increase_in_knots": 0,
             "shear_in_degrees": 0, "turbulence_ratio": 0.05},
        ]
        return {"definition": {
            "latitude_in_degrees": lat, "longitude_in_degrees": lon,
            "elevation_in_meters": round(elev_ft / M_TO_FT, 1),
            "visibility_in_kilometers": round(self.vis * 1.609, 1),
            "temperature_in_degrees_celsius": self.temp,
            "altimeter_setting_in_hpa": round(self.altimeter * 33.8639, 2),
            "precipitation_ratio": precip,
            "clouds": clouds, "wind": winds}}


def density_alt(elev, oat):
    isa = 15 - 1.98 * elev / 1000
    return int(round((elev + 118.8 * (oat - isa)) / 100) * 100)


# ==========================================================================
# Finding X-Plane
# ==========================================================================
def _global_apt(root: Path):
    return root / "Global Scenery" / "Global Airports" / "Earth nav data" / "apt.dat"


def is_xplane_root(p) -> bool:
    try:
        return _global_apt(Path(p)).exists()
    except OSError:
        return False


def find_xplane(explicit=None):
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("XPLANE_ROOT"):
        cands.append(Path(os.environ["XPLANE_ROOT"]))
    cfg = load_config()
    if cfg.get("xplane_root"):
        cands.append(Path(cfg["xplane_root"]))
    reg_dirs = [os.environ.get("LOCALAPPDATA"), str(Path.home() / ".x-plane"),
                str(Path.home() / "Library" / "Preferences")]
    for rd in filter(None, reg_dirs):
        for ver in ("12", "11"):
            f = Path(rd) / f"x-plane_install_{ver}.txt"
            if f.exists():
                try:
                    cands += [Path(l.strip()) for l in f.read_text(errors="ignore").splitlines() if l.strip()]
                except OSError:
                    pass
    for drive in "CDEFG":
        for name in ("X-Plane 12", "X-Plane 11"):
            cands += [Path(f"{drive}:/{name}"), Path(f"{drive}:/Program Files/{name}"),
                      Path(f"{drive}:/Program Files (x86)/Steam/steamapps/common/{name}"),
                      Path(f"{drive}:/SteamLibrary/steamapps/common/{name}"), Path(f"{drive}:/Games/{name}")]
    for name in ("X-Plane 12", "X-Plane 11"):
        cands += [Path.home() / name, Path.home() / "Desktop" / name, Path("/Applications") / name,
                  Path.home() / ".steam/steam/steamapps/common" / name]
    for c in cands:
        if is_xplane_root(c):
            return c
    return None


def load_config() -> dict:
    try:
        return json.loads((CACHE_DIR / "config.json").read_text())
    except Exception:
        return {}


def save_config(**kw):
    cfg = load_config()
    cfg.update(kw)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "config.json").write_text(json.dumps(cfg, indent=1))


# ==========================================================================
# Parsing apt.dat / earth_nav.dat
# ==========================================================================
NAVAIDS = []      # VORs and NDBs from the last scenery scan
PAVED = {1, 2} | set(range(20, 39)) | set(range(50, 58))


def surf_class(code: int) -> str:
    if code in PAVED:
        return "paved"
    return {3: "grass", 4: "dirt", 5: "gravel", 12: "lakebed", 13: "water", 14: "snow"}.get(code, "other")


NEEDED = {"1", "16", "17", "100", "101", "102", "1302", "1300", "54", "1054", "50", "1050"}
KIND = {"1": "land", "16": "sea", "17": "heli"}
MAX_RAMPS = 40


def _finish(cur, out):
    if cur is None:
        return
    meta = cur.pop("_meta")
    pts = cur.pop("_pts")
    try:
        lat, lon = float(meta["datum_lat"]), float(meta["datum_lon"])
    except (KeyError, ValueError):
        if not pts:
            return
        lat = sum(p[0] for p in pts) / len(pts)
        lon = sum(p[1] for p in pts) / len(pts)
    cur["lat"], cur["lon"] = round(lat, 5), round(lon, 5)
    cur["city"] = meta.get("city", "")
    cur["state"] = meta.get("state", "")
    cur["iso"] = meta.get("iso_country", "")
    cur["country"] = meta.get("country", "")
    alias = {meta.get("faa_code", ""), meta.get("icao_code", ""), meta.get("iata_code", "")}
    cur["alias"] = sorted(a for a in alias if a and a != cur["id"])
    out[cur["id"]] = cur


def parse_apt_dat(path: Path, out: dict, pack=None):
    cur = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            code, _, rest = line.partition(" ")
            if code not in NEEDED:
                if code == "99":
                    break
                continue
            t = rest.split()
            try:
                if code in KIND:
                    _finish(cur, out)
                    cur = None
                    if len(t) < 4:
                        continue
                    cur = {"id": t[3], "name": " ".join(t[4:]).strip(), "kind": KIND[code],
                           "elev": int(float(t[0])), "rwys": [], "ramps": [], "tower": False, "atis": False,
                           "pack": pack, "_meta": {}, "_pts": []}
                elif cur is None:
                    continue
                elif code == "100" and len(t) >= 19:
                    la1, lo1, la2, lo2 = float(t[8]), float(t[9]), float(t[17]), float(t[18])
                    cur["_pts"] += [(la1, lo1), (la2, lo2)]
                    cur["rwys"].append({
                        "e": [t[7], t[16]], "len": int(dist_nm(la1, lo1, la2, lo2) * 6076.1),
                        "w": int(float(t[0]) * M_TO_FT), "s": surf_class(int(float(t[1]))),
                        "lit": t[5] != "0", "h": round(course(la1, lo1, la2, lo2), 1),
                        "c": [round(la1, 6), round(lo1, 6), round(la2, 6), round(lo2, 6)]})
                elif code == "101" and len(t) >= 8:
                    la1, lo1, la2, lo2 = float(t[3]), float(t[4]), float(t[6]), float(t[7])
                    cur["_pts"] += [(la1, lo1), (la2, lo2)]
                    cur["rwys"].append({
                        "e": [t[2], t[5]], "len": int(dist_nm(la1, lo1, la2, lo2) * 6076.1),
                        "w": int(float(t[0]) * M_TO_FT), "s": "water", "lit": False,
                        "h": round(course(la1, lo1, la2, lo2), 1),
                        "c": [round(la1, 6), round(lo1, 6), round(la2, 6), round(lo2, 6)]})
                elif code == "102" and len(t) >= 7:
                    cur["_pts"].append((float(t[1]), float(t[2])))
                    cur["rwys"].append({"e": [t[0]], "len": int(float(t[4]) * M_TO_FT),
                                        "w": int(float(t[5]) * M_TO_FT), "s": "helipad",
                                        "lit": False, "h": float(t[3]),
                                        "c": [round(float(t[1]), 6), round(float(t[2]), 6)]})
                elif code == "1300" and len(t) >= 6 and len(cur["ramps"]) < MAX_RAMPS:
                    # 1300 lat lon heading type aircraft_types name...
                    cur["ramps"].append([" ".join(t[5:]), t[3], t[4]])
                elif code == "1302" and len(t) >= 2:
                    cur["_meta"][t[0]] = " ".join(t[1:])
                elif code in ("54", "1054"):
                    cur["tower"] = True
                elif code in ("50", "1050"):
                    cur["atis"] = True
            except (ValueError, IndexError):
                continue
    _finish(cur, out)


def parse_navaids(path: Path):
    """VORs and NDBs from earth_nav.dat."""
    out = []
    kinds = {"2": "NDB", "3": "VOR"}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            code, _, rest = line.partition(" ")
            if code not in kinds:
                continue
            t = rest.split()
            if len(t) < 8:
                continue
            try:
                lat, lon, elev, freq = float(t[0]), float(t[1]), float(t[2]), float(t[3])
            except ValueError:
                continue
            ident = t[6]
            name = " ".join(t[8:]) if len(t) > 8 else ""
            out.append({"id": ident, "lat": round(lat, 5), "lon": round(lon, 5), "elev": int(elev),
                        "freq": freq / 100 if kinds[code] == "VOR" else freq, "navtype": kinds[code],
                        "name": name.strip(), "kind": "navaid", "rwys": [], "tower": False, "ils": [],
                        "city": "", "state": "", "iso": "", "country": "", "alias": [], "ramps": []})
    return out


def parse_ils(path: Path, out: dict):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            code, _, rest = line.partition(" ")
            if code != "4":
                continue
            t = rest.split()
            if len(t) >= 10:
                out.setdefault(t[7], set()).add(t[9])


def scenery_order(root: Path):
    """Custom Scenery folders, lowest priority first (X-Plane's own order when it has one)."""
    cs = Path(root) / "Custom Scenery"
    if not cs.is_dir():
        return []
    dirs = {p.name: p for p in cs.iterdir() if p.is_dir()}
    ini = cs / "scenery_packs.ini"
    ordered, off = [], set()
    if ini.exists():
        try:
            for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line.upper().startswith("SCENERY_PACK") or " " not in line:
                    continue
                name = Path(line.split(None, 1)[1].strip().rstrip("/\\").replace("\\", "/")).name
                if line.upper().startswith("SCENERY_PACK_DISABLED"):
                    off.add(name)                      # X-Plane ignores it, so we do too
                elif name in dirs and dirs[name] not in ordered:
                    ordered.append(dirs[name])
        except OSError:
            pass
    for name in off:
        dirs.pop(name, None)
    ordered = [p for p in ordered if p.name not in off]
    # X-Plane reads the file top-down, highest priority first: reverse it so the
    # best pack is parsed last and wins. Anything not listed goes at the bottom.
    ordered.reverse()
    rest = [p for n, p in sorted(dirs.items()) if p not in ordered]
    return rest + ordered


def apt_sources(root: Path):
    """[(apt.dat path, pack name)] lowest priority first, then the nav data file."""
    files = [(_global_apt(root), None)]
    for p in scenery_order(root):
        f = p / "Earth nav data" / "apt.dat"
        if f.exists() and f != files[0][0]:
            files.append((f, p.name))
    nav = None
    for n in (root / "Custom Data" / "earth_nav.dat", root / "Resources" / "default data" / "earth_nav.dat"):
        if n.exists():
            nav = n
            break
    return files, nav


def load_airports(root: Path, rebuild=False, log=None) -> list:
    log = log or (lambda m: print(m, file=sys.stderr))
    root = Path(root)
    files, nav = apt_sources(root)
    key = [[str(f), f.stat().st_mtime, f.stat().st_size]
           for f in [x[0] for x in files] + ([nav] if nav else [])]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / "airports.json.gz"
    if cache.exists() and not rebuild:
        try:
            with gzip.open(cache, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("format") == CACHE_FORMAT and data.get("key") == key:
                NAVAIDS[:] = data.get("navaids") or []
                return data["airports"]
        except Exception:
            pass
    t0 = time.time()
    log(f"Scanning X-Plane scenery in {root} (one-time, cached afterwards)...")
    out: dict = {}
    for i, (f, pack) in enumerate(files):  # custom scenery parsed last so it overrides global
        log(f"  [{i + 1}/{len(files)}] {pack or f.parent.parent.name}")
        try:
            parse_apt_dat(f, out, pack)
        except OSError as e:
            log(f"    skipped: {e}")
    ils: dict = {}
    if nav:
        log("  reading ILS data...")
        parse_ils(nav, ils)
    airports = list(out.values())
    for a in airports:
        a["ils"] = sorted(ils.get(a["id"], ()))
    navaids = parse_navaids(nav) if nav else []
    with gzip.open(cache, "wt", encoding="utf-8") as f:
        json.dump({"format": CACHE_FORMAT, "key": key, "airports": airports, "navaids": navaids}, f)
    NAVAIDS[:] = navaids
    log(f"  {len(airports):,} airports and {len(navaids):,} radio navaids loaded in {time.time() - t0:.0f} s")
    return airports


# ==========================================================================
# Airport helpers
# ==========================================================================
PRIVATE_RE = re.compile(r"^(\d{2}[A-Z]{2}|[A-Z]{2}\d{2}|\d[A-Z]{2}\d|[A-Z]{2}\d{2}[A-Z]?)$")


def is_private(a):
    return bool(PRIVATE_RE.match(a["id"])) or "PRIVATE" in a["name"].upper() or "PVT" in a["name"].upper()


def is_us(a):
    if a.get("iso"):
        return a["iso"] == "US"
    i = a["id"]
    if len(i) == 4 and i[0] == "K" and i.isalpha():
        return True
    if i[:2] in ("PA", "PF", "PO", "PP", "PH") and len(i) == 4:
        return True
    lat, lon = a["lat"], a["lon"]
    return (24 < lat < 49.3 and -125 < lon < -66.5) or (51 < lat < 72 and -170 < lon < -130) or \
           (18.5 < lat < 22.5 and -161 < lon < -154)


def rwy_str(r):
    if r["s"] == "helipad":
        return f"helipad {r['e'][0]}"
    return f"{'/'.join(r['e'])} {r['len']:,} ft {r['s']}{' lit' if r['lit'] else ''}"


def runway_ends(a):
    """[(end_id, true_heading, runway)] for every runway end (not helipads)."""
    out = []
    for r in a["rwys"]:
        if r["s"] == "helipad":
            continue
        for i, e in enumerate(r["e"]):
            out.append((e, (r["h"] + (180 if i else 0)) % 360, r))
    return out


def ete_min(dist, ac):
    return int(round(dist / ac["cruise"] * 60 + 6))


def cruise_alt(stops, ac, ifr=False):
    hi = max(a["elev"] for a in stops)
    if ac["heli"]:
        return int(round((hi + 1500) / 500) * 500)
    if len(stops) < 2:
        return hi + 3500
    c = crs(stops[0], stops[-1]) if d(stops[0], stops[-1]) > 5 else crs(stops[0], stops[1])
    base = hi + (3000 if hi < 3000 else 4500)
    th = math.ceil(base / 1000)
    east = c < 180  # true course; close enough for a suggestion
    if east != (th % 2 == 1):
        th += 1
    alt = th * 1000 + (0 if ifr else 500)
    while alt > ac["ceiling"] and alt - 2000 > hi + 1000:
        alt -= 2000
    return alt


def guess_profile(acf_path: str) -> str:
    s = acf_path.lower().replace("_", " ")
    best, score = "c172", 0
    for k, p in AIRCRAFT.items():
        for m in p["match"]:
            if m in s and len(m) > score:
                best, score = k, len(m)
    return best


# ==========================================================================
# Ideas
# ==========================================================================
class Idea:
    def __init__(self, kind, title, stops, mission, **kw):
        self.kind, self.title, self.stops, self.mission = kind, title, stops, mission
        self.month = kw.get("month", 5)
        self.tod = kw.get("tod", "morning")
        self.wx: Wx = kw.get("wx") or Wx()
        self.wx_at = kw.get("wx_at") or getattr(self.wx, "station", None) or stops[-1]  # where wx is "reported"
        self.notes = kw.get("notes", [])
        self.twist = kw.get("twist")
        self.failure = kw.get("failure")               # armable failure for the GUI monitor
        self.spoiler = kw.get("spoiler")
        self.hidden = kw.get("hidden", False)
        self.ifr = kw.get("ifr", False)
        self.moon = kw.get("moon", "")
        self._hour = kw.get("hour")        # fixed clock time (live-weather ideas)
        self.payload_kg = kw.get("payload_kg")
        self.overfly = set(kw.get("overfly", ()))   # stop ids you fly over rather than land at
        self.live = kw.get("live", False)

    @property
    def hour(self):
        return self._hour if self._hour is not None else hour_for(self.tod, self.month, self.stops[0]["lat"])

    def main_dest(self):
        """The stop the idea is 'about' (skips a return to home)."""
        s = self.stops
        if len(s) > 2 and s[-1]["id"] == s[0]["id"]:
            return s[len(s) // 2] if len(s) > 3 else s[1]
        return s[-1]

    def when_text(self):
        if self._hour is not None:
            return f"{MONTHS[self.month]}, right now (~{fmt_hour(self.hour)} your time) - live weather"
        return f"{MONTHS[self.month]}, {TIMES[self.tod][0]} (~{fmt_hour(self.hour)} local){self.moon}"

    def sun_text(self):
        """Sunrise/sunset at the departure airport, and how much daylight is left."""
        rise, ss = _solar(self.month, self.stops[0]["lat"])
        h = self.hour
        s = f"Sunrise {fmt_hour(rise)}, sunset {fmt_hour(ss)}"
        if h < rise - 0.1:
            s += f" - you take off {int((rise - h) * 60)} min before sunrise, so it's a night departure"
        elif h > ss:
            s += " - the whole flight is at night"
        else:
            left = ss - h
            s += f" - about {int(left)}h{int((left % 1) * 60):02d} of daylight left at take-off"
        return s


class Generator:
    def __init__(self, airports, ac, rng, opts):
        """opts: object/namespace with from_, near, radius, state, country, include_private"""
        self.ac, self.rng, self.args = ac, rng, opts
        self.all = airports
        self.by_id = {}
        for a in airports:
            for k in a.get("alias", []):
                self.by_id.setdefault(k.upper(), a)
        for a in airports:
            self.by_id[a["id"].upper()] = a
        self.pool = [a for a in airports if self.region_ok(a) and self.usable(a)
                     and (getattr(opts, "include_private", True) or not is_private(a))]
        self.fixed_home = self.lookup(opts.from_) if getattr(opts, "from_", None) else None
        self.center = self.lookup(opts.near) if getattr(opts, "near", None) else None
        self.max_leg = getattr(opts, "max_leg", None) or None
        self.payload_capacity = getattr(opts, "payload_capacity", None)
        self.metars = None          # live observations (list) for the realwx mission
        self.wx_kind = getattr(opts, "wx_kind", "any") or "any"
        self._obs_grid = None
        # scenery preference: 0 = ignore it, 1 = favour add-on scenery, 2 = only add-on scenery
        self.scenery = getattr(opts, "scenery", None)          # an xp_scenery.Scenery, or None
        self.scenery_pref = int(getattr(opts, "scenery_pref", 0) or 0)
        if self.scenery is not None and self.scenery_pref >= 2:
            good = [a for a in self.pool if self.scenery.quality(a) > 0]
            if len(good) >= 8:
                self.pool = good

    # ---- lookup / filters ------------------------------------------------
    def find(self, ident):
        return self.by_id.get((ident or "").strip().upper())

    def lookup(self, ident):
        a = self.find(ident)
        if not a:
            raise KeyError(f"Airport '{ident}' not found in your X-Plane data.")
        return a

    def search(self, text, limit=30):
        t = text.strip().upper()
        if not t:
            return []
        res = [a for a in self.all if a["id"].startswith(t)]
        if len(res) < limit:
            res += [a for a in self.all if t in a["name"].upper() and a not in res][:limit]
        return res[:limit]

    def region_ok(self, a):
        """Area filter: country (ISO code or ANY), optional state/province, optional continent."""
        args = self.args
        c = (getattr(args, "country", "US") or "ANY").upper()
        if c != "ANY":
            if c == "US":
                if not is_us(a):
                    return False
            elif a.get("iso", "").upper() != c:
                return False
        st = getattr(args, "state", None)
        if st:
            st = US_STATES.get(st.upper(), st) if c in ("US", "ANY") else st
            if a.get("state", "").lower() != st.lower():
                return False
        box = getattr(args, "box", None)
        if box and not (box[0] <= a["lat"] <= box[1] and box[2] <= a["lon"] <= box[3]):
            return False
        cont = getattr(args, "continent", None)
        if cont and cont != "Whole world" and not in_area(a, cont):
            return False
        return True

    def usable(self, a, night=False):
        ac = self.ac
        if ac["heli"]:
            return list(a["rwys"]) or [{"e": ["H"], "len": 0, "w": 0, "s": "helipad", "lit": False, "h": 0}]
        out = []
        for r in a["rwys"]:
            if r["s"] == "water":
                ok = ac["water"]
            elif r["s"] == "helipad":
                ok = False
            else:
                need = ac["min_rwy"] * (1 + max(0, a["elev"]) / 1000 * 0.08)  # ~8%/1000 ft
                ok = r["s"] in ac["surfaces"] and r["len"] >= need
            if ok and (not night or r["lit"]):
                out.append(r)
        return out

    def within(self, c, rmin, rmax, pred=None, exclude=()):
        if self.max_leg:
            rmax = min(rmax, self.max_leg)
        dl = rmax / 60.0
        dlon = rmax / (60.0 * max(0.2, math.cos(math.radians(c["lat"]))))
        ex = {e["id"] for e in exclude} | {c["id"]}
        res = []
        for a in self.pool:
            if abs(a["lat"] - c["lat"]) > dl or abs(a["lon"] - c["lon"]) > dlon or a["id"] in ex:
                continue
            dd = d(c, a)
            if rmin <= dd <= rmax and (pred is None or pred(a)):
                res.append(a)
        return res

    def scenery_ok(self, idea):
        """With 'only my add-ons' chosen, every stop has to be somewhere you have scenery."""
        if self.scenery is None or self.scenery_pref < 2:
            return True
        return all(self.scenery.quality(a) > 0 for a in idea.stops)

    def scenery_weight(self, a):
        """How much to favour an airport because you have good scenery there."""
        if self.scenery is None or not self.scenery_pref:
            return 1.0
        return (1.0, 2.2, 3.0, 4.5)[self.scenery.quality(a)]

    def pick(self, cands, score=None):
        if not cands:
            return None
        w = [max(0.01, (score(a) if score else 1.0)) * (0.35 if is_private(a) else 1.0)
             * self.scenery_weight(a) for a in cands]
        return self.rng.choices(cands, weights=w, k=1)[0]

    def home(self):
        if self.fixed_home:
            return self.fixed_home
        if self.center:
            cands = [a for a in self.pool if d(a, self.center) <= (self.args.radius or 150)] + [self.center]
        else:
            cands = self.pool
        return self.pick(cands, lambda a: 3 if (a["tower"] or len(a["id"]) == 4 and a["id"].isalpha()) else 1)

    def R(self, frac=1.0, cap=None):
        r = self.ac["range"] * frac
        return min(r, cap) if cap else r

    # ---- conditions -------------------------------------------------------
    def month(self, choices=None):
        return self.rng.choice(choices) if choices else self.rng.randrange(12)

    def tod(self, pool=("dawn", "morning", "midday", "afternoon", "golden")):
        return self.rng.choice(pool)

    def temp(self, m, a):
        lat = a["lat"]
        if abs(lat) < 23:
            base = 28
        else:
            base = MONTH_TEMP[(m + 6) % 12 if lat < 0 else m] + (40 - abs(lat)) * 0.5
        return int(base - a["elev"] / 1000 * 2 + self.rng.uniform(-4, 4))

    def favoured(self, a, wdir, wspd):
        """(end_id, heading, headwind, crosswind) of the best runway end for this wind."""
        best = None
        for end, h, r in runway_ends(a):
            if not self.ac["heli"] and r not in self.usable(a):
                continue
            ang = math.radians(wdir - h)
            head, cross = wspd * math.cos(ang), abs(wspd * math.sin(ang))
            if best is None or head - cross * 0.5 > best[2] - best[3] * 0.5:
                best = (end, h, head, cross)
        return best

    def set_wind_text(self, wx, a):
        txt = wx.wind_str()
        best = self.favoured(a, wx.wind_dir, wx.wind_spd)
        if best and wx.wind_spd > 2:
            txt += f" -> {a['id']} rwy {best[0]}: {best[3]:.0f} kt crosswind, " + \
                   (f"{best[2]:.0f} kt headwind" if best[2] >= 0 else f"{-best[2]:.0f} kt TAILWIND")
        wx.wind_text = txt
        wx.station = a
        return wx

    def mkwx(self, a, m, sky=None, good=True, wdir=None, wspd=None, gust=0, temp=None):
        if sky is None:
            sky = self.rng.choice(VFR_GOOD if good else VFR_MARG)
        wx = Wx(sky,
                self.rng.randrange(0, 360, 10) if wdir is None else wdir,
                self.rng.choice([0, 3, 5, 6, 8, 10, 12]) if wspd is None else wspd,
                gust, self.temp(m, a) if temp is None else temp,
                round(self.rng.uniform(29.70, 30.25), 2))
        return self.set_wind_text(wx, a)

    # ---- missions -----------------------------------------------------------
    def m_burger(self):
        h = self.home()
        dest = self.pick(self.within(h, 25, self.R(0.35, 110)), lambda a: 2 if a["tower"] or a["atis"] else 1)
        if not dest:
            return None
        m = self.month()
        return Idea("burger", "The $100 hamburger", [h, dest, h],
                    f"Fly to {dest['name']} for lunch (real or imagined), park on the ramp, and fly home. "
                    f"Try a different arrival than usual: a 45-degree entry to the downwind, or overfly midfield "
                    f"and teardrop in.", month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(dest, m))

    def m_backcountry(self):
        ac = self.ac
        if ac["heli"] or ac["min_rwy"] > 1500 or not ({"dirt", "grass", "gravel"} & ac["surfaces"]):
            return None
        h = self.home()

        def soft(a):
            return [r for r in self.usable(a) if r["s"] in ("dirt", "grass", "gravel") and r["len"] <= 3600]
        dest = self.pick(self.within(h, 12, self.R(0.45, 180), soft),
                         lambda a: 1 + a["elev"] / 2000 + (3600 - min(r["len"] for r in soft(a))) / 1000)
        if not dest:
            return None
        r = min(soft(dest), key=lambda r: r["len"])
        m = self.month([5, 6, 7, 8])
        wx = self.mkwx(dest, m, wspd=self.rng.choice([0, 3, 5]))
        notes = ["Fly a high recon pass first: look at the surface, windsock, obstacles and go-around options."]
        if dest["elev"] > 3000:
            notes.append(f"Density altitude at the strip is about {density_alt(dest['elev'], wx.temp):,} ft"
                         f" - lean for best power.")
        if is_private(dest):
            notes.append("Looks like a private strip: in real life you'd need permission to land.")
        return Idea("backcountry", f"Backcountry: {dest['name']}", [h, dest],
                    f"Land on {r['len']:,} ft of {r['s']} (rwy {'/'.join(r['e'])}) at {dest['elev']:,} ft. "
                    f"Soft-field technique, and plan your departure before you land.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=wx, notes=notes)

    def m_shortfield(self):
        if self.ac["heli"]:
            return None
        h = self.home()
        lim = self.ac["min_rwy"] * 1.4 + 400

        def longest(a):
            return max((r["len"] for r in self.usable(a) if r["s"] != "water"), default=0)
        dest = self.pick(self.within(h, 15, self.R(0.4, 150), lambda a: 0 < longest(a) <= lim),
                         lambda a: (lim - longest(a)) / 300 + 1)
        if not dest:
            return None
        L = longest(dest)
        m = self.month()
        return Idea("shortfield", f"Short field: {dest['id']}", [h, dest],
                    f"The longest runway at {dest['name']} is just {L:,} ft. Fly a stabilized approach at "
                    f"1.3 Vso, aim for the first third, and try to stop within {int(L * 0.5):,} ft. "
                    f"Then do a short-field takeoff out.", month=m, tod=self.tod(), wx=self.mkwx(dest, m))

    def m_highalt(self):
        h = self.home()
        cands = self.within(h, 20, self.R(0.5, 300), lambda a: a["elev"] >= 5000)
        if not cands:
            cands = self.within(h, 20, self.R(0.5, 300), lambda a: a["elev"] - h["elev"] >= 3000)
        dest = self.pick(cands, lambda a: a["elev"] / 1000)
        if not dest:
            return None
        m = self.month([6, 7])
        wx = self.mkwx(dest, m, temp=self.temp(m, dest) + 6)
        wx.extra = f" (density altitude ~{density_alt(dest['elev'], wx.temp):,} ft)"
        return Idea("highalt", f"Hot and high: {dest['name']}", [h, dest],
                    f"Field elevation {dest['elev']:,} ft on a hot afternoon. Expect a long takeoff roll and "
                    f"a lazy climb on the way out. Compute takeoff and landing distance before you go.",
                    month=m, tod="afternoon", wx=wx,
                    notes=["Mountain winds: cross ridges at 45 degrees, 2,000 ft above, and have an escape route."]
                    if dest["elev"] > 5000 else [])

    def m_crosswind(self):
        if self.ac["heli"]:
            return None
        h = self.home()

        def single(a):
            rs = [r for r in self.usable(a) if r["s"] not in ("water", "helipad")]
            return len(rs) == 1 and len([r for r in a["rwys"] if r["s"] != "helipad"]) == 1
        dest = self.pick(self.within(h, 20, self.R(0.35, 120), single))
        if not dest:
            return None
        r = self.usable(dest)[0]
        ang = self.rng.uniform(55, 85) * self.rng.choice([-1, 1])
        end_h = r["h"] if self.rng.random() < 0.5 else (r["h"] + 180) % 360
        wdir = round(((end_h + ang) % 360) / 10) * 10
        xw = self.ac["xwind"] * self.rng.uniform(0.75, 1.05)
        wspd = round(xw / abs(math.sin(math.radians(ang))))
        m = self.month()
        return Idea("crosswind", f"Crosswind: {dest['id']}", [h, dest],
                    f"{dest['name']} has one runway ({rwy_str(r)}) and today the wind isn't lined up with it. "
                    f"Wing-low all the way to touchdown, and full aileron into the wind on rollout. "
                    f"Three landings, then home.", month=m, tod=self.tod(("midday", "afternoon")),
                    wx=self.mkwx(dest, m, wdir=wdir, wspd=wspd, gust=self.rng.choice([0, 5, 7, 9])))

    def m_xc(self):
        h = self.home()
        lo, hi = max(100, self.ac["range"] * 0.3), self.R(0.8, 350)
        if self.max_leg:
            hi = min(hi, self.max_leg * 2)
        if hi <= lo:
            return None
        for _ in range(8):
            dest = self.pick(self.within(h, lo, hi) if not self.max_leg else
                             [a for a in self.pool if lo <= d(h, a) <= hi])
            if not dest:
                return None
            tp = self.pick(self.within(interp(h, dest, 0.5), 0, 25, exclude=[h, dest]))
            if tp:
                break
        else:
            return None
        m = self.month()
        pil = self.rng.random() < 0.5
        wx = self.mkwx(dest, m, wspd=self.rng.choice([8, 12, 15, 20]))
        wx.extra = " (winds aloft stronger, veering with height)"
        return Idea("xc", f"Cross-country to {dest['id']}", [h, tp, dest],
                    f"Plan checkpoints every 10-15 nm, compute wind correction and fuel, and do a "
                    f"touch-and-go at {tp['name']} on the way."
                    + (" Pilotage and dead reckoning only - cover the moving map." if pil else ""),
                    month=m, tod=self.tod(("morning", "midday")), wx=wx, wx_at=h)

    def m_tour(self):
        h = self.home()
        n = self.rng.randint(3, 5)
        leg_max = min(self.R(0.3, 90), self.max_leg or 9999)
        stops = [h]
        for _ in range(n):
            cur = stops[-1]
            back = crs(cur, stops[-2]) if len(stops) > 1 else None
            cands = self.within(cur, 20, leg_max, lambda a: a["id"] not in {s["id"] for s in stops}
                                and (back is None or angle_diff(crs(cur, a), back) > 80))
            nxt = self.pick(cands)
            if not nxt:
                break
            stops.append(nxt)
        if len(stops) < 3:
            return None
        if d(stops[-1], h) <= leg_max * (1.0 if self.max_leg else 1.3):
            stops.append(h)
        m = self.month()
        return Idea("tour", f"Airport-hopping tour ({len(stops) - 1} legs)", stops,
                    "Land at every stop - full stop at least once, touch-and-go the rest. "
                    "Use each airport's actual pattern altitude and traffic direction.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=self.mkwx(h, m), wx_at=h)

    def m_night(self):
        if not self.ac["night"]:
            return None
        h = self.home()
        dest = self.pick(self.within(h, 30, self.R(0.4, 160), lambda a: bool(self.usable(a, night=True))),
                         lambda a: 2 if a["tower"] else 1)
        if not dest:
            return None
        m = self.month()
        moon = self.rng.choice([", new moon - very dark", ", full moon", ", quarter moon"])
        return Idea("night", f"Night flight to {dest['id']}", [h, dest, h],
                    f"Three full-stop landings at {dest['name']} for night currency, then home. "
                    f"If it's non-towered, find the pilot-controlled lighting frequency (click 7 times).",
                    month=m, tod="night", moon=moon, wx=self.mkwx(dest, m),
                    notes=["Stay high over dark areas until you can see the runway - avoid the 'black hole' approach."])

    def m_ifr(self):
        if not self.ac["ifr"]:
            return None
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.6, 250), lambda a: bool(a["ils"])))
        if not dest:
            return None
        ils = self.rng.choice(dest["ils"])
        rh = next((hd for e, hd, _ in runway_ends(dest) if e == ils), None)
        alt = self.pick(self.within(dest, 15, 70, lambda a: bool(a["ils"]) or a["tower"], exclude=[h]))
        wdir = round(((rh if rh is not None else self.rng.randrange(360)) + self.rng.uniform(-25, 25)) % 360 / 10) * 10
        m = self.month([0, 1, 2, 9, 10, 11])
        wx = self.mkwx(dest, m, sky=self.rng.choice(IFR_SKY), wdir=wdir, wspd=self.rng.choice([6, 9, 12]))
        return Idea("ifr", f"Low IFR: ILS {ils} at {dest['id']}", [h, dest],
                    f"File IFR to {dest['name']}. Fly the ILS runway {ils} hand-flown to minimums. "
                    + (f"No runway at DA? Go missed and divert to {alt['id']} ({alt['name']})." if alt else ""),
                    month=m, tod=self.tod(), wx=wx, ifr=True,
                    notes=["The same low layer covers your departure - climb through it on instruments."]
                    + ([f"Alternate: {alt['id']} {alt['name']}, {d(dest, alt):.0f} nm from {dest['id']}."] if alt else []))

    def m_mystery(self):
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.45, 160)))
        if not dest:
            return None
        rs = self.usable(dest)
        r = max(rs, key=lambda r: r["len"]) if rs else None
        m = self.month()
        clue = [f"field elevation about {round(dest['elev'], -2):,.0f} ft"]
        if r and r["len"]:
            clue.append(f"longest usable runway ~{round(r['len'], -2):,} ft {r['s']}")
        clue.append("it has a control tower" if dest["tower"] else "no control tower")
        return Idea("mystery", "Mystery destination", [h, dest],
                    f"From {h['id']} fly {crs(h, dest):03.0f} deg TRUE for {d(h, dest):.0f} nm. "
                    f"Clues: {'; '.join(clue)}. No GPS - clock, compass and chart only. "
                    f"Identify the airport when you get there, then check the spoiler.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(h, m, wspd=0), wx_at=h,
                    spoiler=f"{dest['id']} - {dest['name']}", hidden=True)

    def m_scenic(self):
        R = self.R(0.5, 300)
        fixed = self.fixed_home or self.center
        opts = []
        for ids, title, blurb in SCENIC_ROUTES:
            aps = [self.by_id.get(i) for i in ids]
            if all(a and self.usable(a) and self.region_ok(a) for a in aps):
                opts.append(("route", aps, title, blurb))
        for i, blurb in SCENIC_DEST.items():
            a = self.by_id.get(i)
            if a and self.usable(a) and self.region_ok(a):
                opts.append(("dest", [a], a["name"], blurb))
        self.rng.shuffle(opts)
        h = self.home() if fixed else None
        for kind, aps, title, blurb in opts:
            if fixed:
                if d(h, aps[0]) > (R if kind == "dest" else 150):
                    continue
                stops = ([h] if h["id"] != aps[0]["id"] else []) + aps
            elif kind == "dest":
                h2 = self.pick(self.within(aps[0], 30, min(120, R)))
                if not h2:
                    continue
                stops = [h2, aps[0]]
            else:
                stops = aps
            if len(stops) < 2 or any(d(a, b) > self.ac["range"] * 0.8 for a, b in zip(stops, stops[1:])):
                continue
            m = self.month([4, 5, 6, 7, 8, 9])
            return Idea("scenic", f"Scenic: {title}", stops, blurb, month=m,
                        tod=self.tod(("morning", "golden")), wx=self.mkwx(stops[-1], m, sky=self.rng.choice(["clear", "few"])),
                        notes=["Turn the visibility slider up and slow down - this one's for the views."])
        return None

    def m_island(self):
        h = self.home()
        pat = re.compile(r"\b(ISLAND|ISLE|KEY|CAY|ISLANDS)\b")
        dest = self.pick(self.within(h, 15, self.R(0.5, 200), lambda a: bool(pat.search(a["name"].upper()))))
        if not dest:
            return None
        m = self.month()
        return Idea("island", f"Island run: {dest['name']}", [h, dest, h],
                    "Over-water leg. Before you go, work out how high you need to be to glide to shore "
                    "(~1.5 nm per 1,000 ft in a typical single) - climb for it or accept the risk knowingly.",
                    month=m, tod=self.tod(), wx=self.mkwx(dest, m, good=self.rng.random() < 0.7),
                    notes=["Island airports often have strong crosswinds and changing weather - have a plan B."])

    def m_bigairport(self):
        if self.ac["heli"]:
            return None
        h = self.home()

        def big(a):
            return a["tower"] and len([r for r in a["rwys"] if r["s"] == "paved" and r["len"] >= 7000]) >= 2
        dest = self.pick(self.within(h, 30, self.R(0.45, 180), big),
                         lambda a: len(a["rwys"]) + (3 if a["ils"] else 0))
        if not dest:
            return None
        m = self.month()
        return Idea("bigairport", f"Big-airport arrival: {dest['id']}", [h, dest],
                    f"Take your {self.ac['name']} into {dest['name']}. Use X-Plane ATC (or a plugin), "
                    f"keep your speed up on final if asked, and land beyond the jets' touchdown point "
                    f"to stay above their wake.", month=m, tod=self.tod(("morning", "afternoon")),
                    wx=self.mkwx(dest, m), notes=["Taxi with the airport diagram open; big airports are easy to get lost on."])

    def m_ferry(self):
        R = self.ac["range"]
        h = self.home()
        for _ in range(6):
            dest = self.pick([a for a in self.pool if R * 0.9 <= d(h, a) <= min(R * 1.5, 900)
                              and (a["tower"] or not is_private(a))])
            if not dest:
                return None
            fuel = self.pick([a for a in self.within(interp(h, dest, 0.5), 0, 40, exclude=[h, dest])
                              if d(a, h) < R * 0.85 and d(a, dest) < R * 0.85], lambda a: 3 if a["tower"] else 1)
            if fuel:
                break
        else:
            return None
        m = self.month()
        return Idea("ferry", f"Ferry flight to {dest['id']}", [h, fuel, dest],
                    f"The airplane has been sold and the new owner is waiting at {dest['name']}. "
                    f"Plan a fuel stop at {fuel['name']}. Check weather along the whole route.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=self.mkwx(h, m, good=self.rng.random() < 0.6), wx_at=h)

    def m_seaplane(self):
        if not self.ac["water"]:
            return None
        h = self.home()
        dest = self.pick(self.within(h, 8, self.R(0.45, 150), lambda a: any(r["s"] == "water" for r in a["rwys"])))
        if not dest:
            return None
        m = self.month([5, 6, 7, 8])
        return Idea("seaplane", f"Water landing: {dest['name']}", [h, dest],
                    "Glassy water today: set landing attitude, 150 fpm descent, and wait for it. "
                    "Pick a landing lane clear of boats and plan how you'll dock.",
                    month=m, tod=self.tod(("dawn", "golden")), wx=self.mkwx(dest, m, sky="clear", wspd=0))

    def m_medevac(self):
        if not self.ac["heli"]:
            return None
        pat = re.compile(r"HOSPITAL|MEDICAL|HEALTH|MED CTR|TRAUMA|CLINIC")
        h = self.home()
        pick_up = self.pick(self.within(h, 8, 60))
        if not pick_up:
            return None
        hosp = self.pick(self.within(pick_up, 5, 50, lambda a: bool(pat.search(a["name"].upper())), exclude=[h]))
        if not hosp:
            return None
        m = self.month()
        return Idea("medevac", "Medevac", [h, pick_up, hosp, h],
                    f"Launch from {h['id']}, pick up a patient at {pick_up['name']}, deliver them to "
                    f"{hosp['name']}, and return to base. Rooftop pads: steep approach, watch for obstacles.",
                    month=m, tod=self.tod(("midday", "afternoon", "night")),
                    wx=self.mkwx(hosp, m, good=self.rng.random() < 0.7, wspd=15, gust=7))

    def m_realwx(self, pick=None, depart_here=False, other=None):
        """Fly into (or out of) real weather happening now.
        pick: a xp_wx.find_bad_weather() result to use; depart_here: start AT the bad weather."""
        import xp_wx
        obs = self.metars
        if not obs:
            return None
        if pick is None:
            h = self.home() if (self.fixed_home or self.center) else None
            if h:
                found = [f for f in xp_wx.find_bad_weather(obs, self, self.wx_kind, home=h, max_nm=self.R(0.6, 300),
                                                           min_score=1.5, limit=40)
                         if f["apt"]["id"] != h["id"] and (f["home_dist"] or 0) >= 15]
            else:
                found = xp_wx.find_bad_weather(obs, self, self.wx_kind, min_score=1.5, limit=60)
            if not found:
                return None
            top = found[:25]
            pick = self.rng.choices(top, weights=[f["score"] for f in top], k=1)[0]
        bad, o = pick["apt"], pick["obs"]
        if self._obs_grid is None:
            self._obs_grid = xp_wx.Grid(obs)

        def cat_near(a):
            n = xp_wx.nearest_obs(self._obs_grid, a["lat"], a["lon"], 30)
            return n.get("cat") if n else None

        def good_airport_near(a, lo, hi):
            cands = self.within(a, lo, hi) or self.within(a, 8, hi)
            good = [c for c in cands if cat_near(c) == "VFR"] or [c for c in cands if cat_near(c) == "MVFR"]
            return self.pick(good or cands)

        if other is not None and other["id"] == bad["id"]:
            other = None
        if depart_here:
            other = other or good_airport_near(bad, 30, self.R(0.4, 150))
            if not other:
                return None
            stops = [bad, other]
        else:
            h = other or self.fixed_home
            if h is None or h["id"] == bad["id"]:
                h = good_airport_near(bad, 40, self.R(0.4, 150))
                if not h:
                    return None
            stops = [h, bad]
        wx = xp_wx.to_wx(o, sys.modules[__name__])
        self.set_wind_text(wx, bad)
        wx.metar = o.get("raw", "")
        hz = xp_wx.hazards(o)
        if self.wx_kind in hz and hz[self.wx_kind] > 0:
            main = self.wx_kind
        else:
            main = max(hz, key=lambda k: hz[k] * (1.3 if k == "ts" else 1.0))
        desc = xp_wx.describe(o)
        best = self.favoured(bad, wx.wind_dir, wx.wind_spd)
        ils = f" ILS {bad['ils'][0]}" if bad.get("ils") else ""
        if main == "ifr":
            advice = (f"File IFR and fly the{ils or ' instrument'} approach; be ready to go missed."
                      if self.ac["ifr"] and not depart_here else
                      "File IFR and climb straight through the layer on instruments." if self.ac["ifr"] else
                      "A classic VFR trap: practise the decision - turn back or divert while you can still see.")
        elif main == "wind":
            advice = ((f"Expect about {best[3]:.0f} kt of crosswind on runway {best[0]}. " if best else "") +
                      "Add half the gust factor to your approach speed and fly it all the way to the tie-down.")
        elif main == "ts":
            advice = "Plan around the cells, stay 20 nm from strong storms and keep an alternate ready."
        elif main == "ceiling":
            c = o.get("ceiling")
            advice = (f"The ceiling is about {c:,.0f} ft. " if c else "") + (
                f"File IFR and fly the{ils or ' instrument'} approach - you'll break out low."
                if self.ac["ifr"] and not depart_here else
                "Under a ceiling that low, everything happens close to the ground: know the terrain and the "
                "obstacles on your route before you go, and have a turn-back point.")
        elif main == "vis":
            v = o.get("vis")
            advice = (f"Visibility is down to {vis_str(v)}. " if v is not None else "") + (
                "Fly it on instruments and look for the approach lights, not the runway."
                if self.ac["ifr"] and not depart_here else
                "With no horizon, keep the wings level on the instruments and navigate by heading and clock.")
        elif main == "fog":
            advice = ("Fog: fly the approach to minimums and expect to see the lights only at the last moment."
                      if self.ac["ifr"] else
                      "Fog: a VFR pilot's nightmare - try it, and practise turning back before you lose the ground.")
        elif main == "dust":
            advice = ("Dust, sand or smoke: visibility can drop to nothing in minutes. Plan an alternate upwind "
                      "and keep the fuel for it.")
        elif main == "snow":
            advice = "Expect a contaminated runway and icing in cloud - stay out of visible moisture below freezing."
        else:
            advice = "Reduced visibility and a wet runway - plan for a longer roll."
        if depart_here:
            text = (f"Take off from {bad['name']} into the real weather ({desc}) and fly to "
                    f"{stops[1]['name']}, where it's {cat_near(stops[1]) or 'better'}. {advice}")
        else:
            text = f"{bad['name']} right now: {desc}. {advice}"
        notes = [f"METAR: {o.get('raw', '')}",
                 f"Observed {o.get('time', '')}. Weather keeps changing - choose 'Real-world weather' to fly it as it is now."]
        if not depart_here:
            for dd, a in xp_wx.Grid(self.pool).near(bad["lat"], bad["lon"], 70):
                if a["id"] not in (bad["id"], stops[0]["id"]) and dd > 10 and cat_near(a) == "VFR":
                    notes.append(f"Nearest VFR alternate: {a['id']} {a['name']}, {dd:.0f} nm from {bad['id']}.")
                    break
        lt = time.localtime()
        title = (f"Live weather: out of {bad['id']} ({xp_wx.SHORT[main]})" if depart_here
                 else f"Live weather: {bad['id']} - {xp_wx.SHORT[main]}")
        return Idea("realwx", title, stops, text, month=lt.tm_mon - 1, tod="midday",
                    hour=lt.tm_hour + lt.tm_min / 60, wx=wx, wx_at=bad, notes=notes,
                    ifr=(main in ("ifr", "ceiling", "vis", "fog") and self.ac["ifr"]), live=True)

    def m_cargo(self):
        ac = self.ac
        if ac["heli"] or ac.get("glider"):
            return None
        h = self.home()
        cap = self.payload_capacity or 250

        def shortest(a):
            rs = [r for r in self.usable(a) if r["s"] != "water"]
            return min((r["len"] for r in rs), default=0)

        def ok(a):
            L = shortest(a)
            return L and (L <= max(4500, ac["min_rwy"] * 2.2) or a["elev"] > 4500
                          or any(r["s"] in ("grass", "dirt", "gravel") for r in self.usable(a)))
        dest = self.pick(self.within(h, 20, self.R(0.45, 200), ok),
                         lambda a: 1 + a["elev"] / 3000 + (2 if is_private(a) else 0)
                         + max(0.0, (5000 - shortest(a)) / 1200))
        if not dest:
            return None
        load = int(round(self.rng.uniform(0.55, 0.95) * cap / 10) * 10)
        rs = [r for r in self.usable(dest) if r["s"] != "water"]
        r = min(rs, key=lambda r: r["len"])
        m = self.month([4, 5, 6, 7, 8, 9])
        wx = self.mkwx(dest, m)
        return Idea("cargo", f"Cargo run to {dest['id']}", [h, dest],
                    f"Load {load} kg of freight at {h['name']} and deliver it to {dest['name']} - "
                    f"{r['len']:,} ft of {r['s']} at {dest['elev']:,} ft. Work out your takeoff and landing "
                    f"distance at that weight before you go, and fly the numbers.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=wx, payload_kg=load,
                    notes=[f"Density altitude at the strip is about {density_alt(dest['elev'], wx.temp):,} ft.",
                           "The payload is set for you when you launch from the app."])

    def m_sightsee(self):
        h = self.home()
        pts = []
        cur = h
        for _ in range(self.rng.randint(2, 4)):
            nxt = self.pick(self.within(cur, 10, self.R(0.35, 90),
                                        lambda a: a["id"] not in {x["id"] for x in [h] + pts}),
                            lambda a: 1 + a["elev"] / 2500 + (1.5 if re.search(r"ISLAND|LAKE|CANYON|MOUNT|BAY|FALLS",
                                                                              a["name"].upper()) else 0))
            if not nxt:
                break
            pts.append(nxt)
            cur = nxt
        if len(pts) < 2:
            return None
        dest = pts[-1]
        stops = [h] + pts
        m = self.month([4, 5, 6, 7, 8, 9])
        return Idea("sightsee", f"Sightseeing tour from {h['id']}", stops,
                    "Fly the whole route low and slow (but legal and safe). Overfly each waypoint at about "
                    "1,500 ft AGL for the view, then land at the last one. No hurry - this one is for looking out "
                    "of the window.",
                    month=m, tod=self.tod(("morning", "golden")), wx=self.mkwx(dest, m, sky=self.rng.choice(["clear", "few"])),
                    overfly=[a["id"] for a in pts[:-1]],
                    notes=["Overfly the middle waypoints - only the last one is a landing."])

    def m_aerobatic(self):
        ac = self.ac
        if ac["heli"] or ac.get("glider") or ac["cruise"] > 260:
            return None
        h = self.home()
        rs = [r for r in self.usable(h) if r["s"] != "water"]
        if not rs:
            return None
        m = self.month()
        blocks = self.rng.choice([
            "two clearing turns, a power-on stall, a power-off stall, then three steep turns at 45 degrees",
            "slow flight, a falling-leaf stall, and lazy eights",
            "a loop, an aileron roll and a wingover (only if your aircraft is cleared for it)",
            "chandelles left and right, then a simulated engine failure from 4,000 ft AGL",
            "steep spirals down to 1,500 ft AGL, then a short-field landing"])
        return Idea("aerobatic", f"Airwork over {h['id']}", [h, h],
                    f"Take off from {h['name']}, climb overhead to 5,000 ft AGL and work through: {blocks}. "
                    f"Clear the area first, stay within gliding distance of the field, and finish with three "
                    f"landings.", month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(h, m, wspd=self.rng.choice([0, 3, 6])),
                    notes=["Watch your altitude and speed limits - this is practice, not showing off."])

    def m_soaring(self):
        if not self.ac.get("glider"):
            return None
        h = self.home()
        legs = []
        cur = h
        for _ in range(2):
            nxt = self.pick(self.within(cur, 15, 45, lambda a: a["id"] not in {x["id"] for x in [h] + legs}))
            if not nxt:
                return None
            legs.append(nxt)
            cur = nxt
        m = self.month([4, 5, 6, 7])
        return Idea("soaring", f"Soaring triangle from {h['id']}", [h] + legs + [h],
                    f"A {d(h, legs[0]) + d(legs[0], legs[1]) + d(legs[1], h):.0f} nm triangle: round "
                    f"{legs[0]['id']} and {legs[1]['id']} and come home - no engine. Work the thermals, and keep "
                    f"a landable field in reach at all times.",
                    month=m, tod=self.tod(("midday", "afternoon")), wx=self.mkwx(h, m, sky="cu"),
                    overfly=[a["id"] for a in legs],
                    notes=["Set thermals in X-Plane's weather (cumulus and a good thermal climb rate)."])

    def m_alphabet(self):
        h = self.home()

        def letter_of(a):
            i = a["id"].upper()
            return i[1] if len(i) == 4 and i[0] in "KPCEYLURSVZBNMOTGDFHWA" and i[1].isalpha() else i[0]
        best = []
        for _ in range(6):
            start = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            stops, cur = [h], h
            for i in range(4):
                L = chr((ord(start) - 65 + i) % 26 + 65)
                nxt = self.pick(self.within(cur, 12, self.R(0.35, 150),
                                            lambda a, L=L: letter_of(a) == L and
                                            a["id"] not in {x["id"] for x in stops}))
                if not nxt:
                    break
                stops.append(nxt)
                cur = nxt
            if len(stops) > len(best):
                best = stops
            if len(best) >= 4:
                break
        stops = best
        if len(stops) < 3:
            return None
        m = self.month()
        chain = " -> ".join(a["id"] for a in stops)
        return Idea("alphabet", f"Alphabet challenge ({len(stops) - 1} stops)", stops,
                    f"Land at an airport for each letter of the alphabet in turn: {chain}. "
                    f"Full stop at each one, and log it.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=self.mkwx(h, m), wx_at=h)

    def m_mail(self):
        if self.ac.get("glider"):
            return None
        h = self.home()
        stops, cur = [h], h
        for _ in range(self.rng.randint(2, 3)):
            nxt = self.pick(self.within(cur, 20, self.R(0.25, 80), lambda a: a["id"] not in {x["id"] for x in stops}))
            if not nxt:
                break
            stops.append(nxt)
            cur = nxt
        if len(stops) < 3:
            return None
        stops.append(h)
        m = self.month()
        idea = Idea("mail", f"Mail run ({len(stops) - 1} legs)", stops,
                    "The mail has to be there. Land at every stop, keep the turnarounds under 10 minutes, and "
                    "be home before the deadline.", month=m, tod=self.tod(("dawn", "morning")),
                    wx=self.mkwx(h, m, good=self.rng.random() < 0.7), wx_at=h)
        legs = list(zip(stops, stops[1:]))
        total = sum(ete_min(d(*l), self.ac) for l in legs) + 10 * (len(legs) - 1)
        dep = int(idea.hour * 60)
        idea.notes.append(f"Deadline: airborne at {dep // 60:02d}:{dep % 60:02d}, back at {stops[-1]['id']} by "
                          f"{((dep + total + 20) // 60) % 24:02d}:{(dep + total + 20) % 60:02d} local "
                          f"({total + 20} minutes for {sum(d(*l) for l in legs):.0f} nm).")
        return idea

    def m_radionav(self):
        if self.ac.get("glider") or not NAVAIDS:
            return None
        h = self.home()
        R = self.R(0.35, 120)

        def near_nav(c, lo, hi, used):
            out = []
            for n in NAVAIDS:
                if abs(n["lat"] - c["lat"]) > hi / 55 or abs(n["lon"] - c["lon"]) > hi / 40:
                    continue
                if n["id"] in used:
                    continue
                dd = d(c, n)
                if lo <= dd <= hi:
                    out.append(n)
            return out
        used = set()
        chain, cur = [], h
        for _ in range(self.rng.randint(2, 3)):
            cands = near_nav(cur, 15, R, used)
            if not cands:
                break
            n = self.rng.choice(cands)
            chain.append(n)
            used.add(n["id"])
            cur = n
        if not chain:
            return None
        dest = self.pick(self.within(chain[-1], 5, 60, exclude=[h]))
        if not dest:
            return None
        stops = [h] + chain + [dest]
        m = self.month()
        tune = "; ".join(f"{n['id']} {n['navtype']} on "
                         f"{n['freq']:.2f}" + (" MHz" if n["navtype"] == "VOR" else " kHz")
                         for n in chain)
        return Idea("radionav", f"Radio navigation to {dest['id']}", stops,
                    f"No GPS today. Navigate by radio: {tune}. Track to each one, note the time overhead, "
                    f"then fly the final leg to {dest['name']} by dead reckoning.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(dest, m),
                    overfly=[n["id"] for n in chain],
                    notes=["Cover the moving map. Identify each station by its Morse code before you trust it.",
                           "The middle waypoints are radio beacons - you fly over them, you don't land."])

    # ---- more mission types ---------------------------------------------------
    def m_checkride(self):
        ac = self.ac
        if ac["heli"] or ac.get("glider"):
            return None
        h = self.home()
        div = self.pick(self.within(h, 20, self.R(0.25, 70)))
        if not div:
            return None
        m = self.month()
        tasks = ["Normal takeoff and climb", "Steep turns, 45 degrees, both ways, +/-100 ft",
                 "Slow flight and a power-off stall", "A power-on stall", "Emergency descent",
                 f"Diversion: turn and go to {div['id']} ({div['name']}) - estimate the time and fuel first",
                 "Simulated engine failure: best glide, field chosen, checks done", "Short-field landing",
                 "Soft-field takeoff and landing", "Go-around from short final", "Normal landing to a full stop"]
        return Idea("checkride", f"Checkride out of {h['id']}", [h, div, h],
                    "Fly the whole practical test in one go: " + "; ".join(tasks[:4]) + "... (full list in the notes). "
                    "Hold altitude within 100 ft and heading within 10 degrees throughout.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(h, m), wx_at=h,
                    notes=[f"{i}. {t}" for i, t in enumerate(tasks, 1)]
                    + ["Grade yourself: any task outside the limits is a re-fly."])

    def m_poker(self):
        h = self.home()
        stops, cur = [h], h
        for _ in range(4):
            nxt = self.pick(self.within(cur, 15, self.R(0.25, 80), lambda a: a["id"] not in {x["id"] for x in stops}))
            if not nxt:
                break
            stops.append(nxt)
            cur = nxt
        if len(stops) < 4:
            return None
        deck = [f"{r} of {s}" for r in ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
                for s in ["hearts", "spades", "diamonds", "clubs"]]
        cards = self.rng.sample(deck, len(stops))
        m = self.month()
        return Idea("poker", f"Poker run ({len(stops)} airports)", stops,
                    "Land at each airport and draw a card. The hand is already dealt below - your job is to collect "
                    "it: a full stop at every stop, and no cheating by skipping one.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(h, m), wx_at=h,
                    notes=[f"{a['id']}: {c}" for a, c in zip(stops, cards)]
                    + ["Fly it with friends and compare hands, or beat your own best."])

    def m_photo(self):
        h = self.home()
        target = self.pick(self.within(h, 15, self.R(0.35, 120)),
                           lambda a: 1 + a["elev"] / 3000 + (2 if re.search(r"ISLAND|LAKE|CANYON|MOUNT|BAY|FALLS|"
                                                                            r"DAM|HARBOR|HARBOUR|BRIDGE",
                                                                            a["name"].upper()) else 0))
        if not target:
            return None
        alt = self.rng.choice([800, 1200, 1500, 2000, 2500])
        hdg = self.rng.randrange(0, 360, 45)
        m = self.month([4, 5, 6, 7, 8, 9])
        side = self.rng.choice(["left", "right"])
        return Idea("photo", f"Photo flight: {target['name']}", [h, target],
                    f"You're flying the photographer. Arrive overhead {target['name']} at {alt:,} ft AGL on a "
                    f"heading of {hdg:03d} degrees with the subject out of the {side} window, then orbit it twice "
                    f"in a {side} turn holding the height within 100 ft. Land there afterwards.",
                    month=m, tod=self.tod(("golden", "morning")), wx=self.mkwx(target, m, sky="clear", wspd=self.rng.choice([0, 3, 6])),
                    notes=["Golden hour light and low wind make the shot - that's why the time is set this way.",
                           "Use X-Plane's screenshot key at the best moment; the app can also grab one on landing."])

    def m_organ(self):
        if self.ac.get("glider"):
            return None
        h = self.home()
        dest = self.pick(self.within(h, 60, self.R(0.6, 300), lambda a: a["tower"] or bool(a["ils"])),
                         lambda a: 2 if a["ils"] else 1)
        if not dest:
            return None
        m = self.month()
        legmin = ete_min(d(h, dest), self.ac)
        slack = int(legmin * 0.12) + 5
        return Idea("organ", f"Urgent transport to {dest['id']}", [h, dest],
                    f"A transplant team is waiting at {dest['name']}. Wheels up within 15 minutes and on the ground "
                    f"in {legmin + slack} minutes or less - but not by cutting corners on the weather or the fuel. "
                    f"Brief a diversion before you start.",
                    month=m, tod=self.tod(("dawn", "night", "midday")), wx=self.mkwx(dest, m, good=self.rng.random() < 0.6),
                    ifr=self.ac["ifr"] and self.rng.random() < 0.5,
                    notes=["Direct routing is fine, but a rushed approach is how these flights go wrong.",
                           f"Planned time {legmin} min; you have {legmin + slack} min."])

    def m_sar(self):
        h = self.home()
        area = self.pick(self.within(h, 20, self.R(0.35, 120)))
        if not area:
            return None
        brg = self.rng.randrange(360)
        dist = self.rng.uniform(4, 12)
        c = _dest_point(area["lat"], area["lon"], brg, dist)
        legs = self.rng.choice([1, 2, 2, 3])
        m = self.month()
        return Idea("sar", f"Search and rescue near {area['id']}", [h, area],
                    f"An ELT is transmitting somewhere within 15 nm of {area['name']}. Fly to the area, then run an "
                    f"expanding square search at 1,000 ft AGL with {legs} nm legs, turning right each time. "
                    f"When you've covered it, land at {area['id']} and report.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(area, m, good=self.rng.random() < 0.7),
                    notes=[f"Spoiler - the target is at about {c[0]:.3f}, {c[1]:.3f} "
                           f"({dist:.0f} nm on the {brg:03d} radial from {area['id']}). Don't peek until you've "
                           f"searched.",
                           "Low and slow costs fuel and options: keep a landing field in reach."])

    def m_patrol(self):
        if self.ac.get("glider"):
            return None
        h = self.home()
        line, cur = [], h
        brg0 = self.rng.randrange(360)
        for _ in range(self.rng.randint(3, 4)):
            cands = self.within(cur, 12, self.R(0.2, 60),
                                lambda a: a["id"] not in {x["id"] for x in [h] + line}
                                and angle_diff(crs(cur, a), brg0) < 60)
            nxt = self.pick(cands)
            if not nxt:
                break
            line.append(nxt)
            cur = nxt
        if len(line) < 2:
            return None
        m = self.month()
        what = self.rng.choice(["a gas pipeline", "a power line", "a railway", "a fibre-optic route"])
        return Idea("patrol", f"Patrol flight from {h['id']}", [h] + line,
                    f"You're inspecting {what}. Follow the line between the waypoints at 800-1,000 ft AGL and "
                    f"about 90 knots, looking out of the window, not at the panel. Land at the far end.",
                    month=m, tod=self.tod(("morning", "afternoon")), wx=self.mkwx(line[-1], m),
                    overfly=[a["id"] for a in line[:-1]],
                    notes=["Low-level rules: know the obstacles, keep an escape route, and stay legal over towns.",
                           "Turns at low level bite - keep the bank below 30 degrees."])

    def m_timetrial(self):
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.5, 200)))
        if not dest:
            return None
        m = self.month()
        par = ete_min(d(h, dest), self.ac) - 4
        return Idea("timetrial", f"Time trial {h['id']} to {dest['id']}", [h, dest],
                    f"Fastest wheels-up to wheels-down wins. Par time is {par} minutes for {d(h, dest):.0f} nm. "
                    f"Plan the altitude for the best groundspeed, lean properly, and don't overcook the arrival.",
                    month=m, tod=self.tod(), wx=self.mkwx(dest, m, wspd=self.rng.choice([5, 10, 15, 20])),
                    notes=["The app's logbook records your flight time, so you can beat it next time.",
                           "Redline and low fuel are not a strategy."])

    def m_hold(self):
        if not self.ac["ifr"]:
            return None
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.5, 200), lambda a: bool(a["ils"])))
        if not dest:
            return None
        fix = None
        if NAVAIDS:
            near = [n for n in NAVAIDS if d(n, dest) < 40]
            fix = self.rng.choice(near) if near else None
        inbound = self.rng.randrange(0, 360, 10)
        turns = self.rng.choice(["right (standard)", "left (non-standard)"])
        ils = self.rng.choice(dest["ils"])
        m = self.month([0, 1, 2, 9, 10, 11])
        wx = self.mkwx(dest, m, sky=self.rng.choice(IFR_SKY))
        fixname = f"{fix['id']} {fix['navtype']}" if fix else f"the {ils} localizer outer marker area"
        return Idea("hold", f"Hold and approach at {dest['id']}", [h, dest],
                    f"File IFR. Before the approach, hold at {fixname}: inbound course {inbound:03d} degrees, "
                    f"{turns} turns, one-minute legs. Fly two complete laps with the correct entry, then the "
                    f"ILS {ils} to minimums.", month=m, tod=self.tod(), wx=wx, ifr=True,
                    notes=["Work out the entry (direct, parallel or teardrop) before you get there.",
                           "Correct for wind in the hold: triple the drift on the outbound leg."])

    def m_circuits(self):
        """A set of circuits at one airport, each with a different exercise."""
        if self.ac.get("glider"):
            return None
        h = self.pick([a for a in self.pool if self.usable(a) and len(runway_ends(a)) >= 2]) or self.home()
        drills = self.rng.sample(
            ["a normal circuit to a full stop", "a flapless approach and landing",
             "a glide approach from abeam the numbers - engine at idle all the way",
             "a short-field landing: touch down in the first third and stop as short as you can",
             "a soft-field take-off and landing, nose wheel light",
             "a go-around from 50 ft on short final",
             "a touch-and-go with a crosswind correction held all the way down",
             "one circuit flown at pattern altitude with no glances at the airspeed indicator"],
            k=self.rng.randint(4, 6))
        m = self.month()
        wspd = self.rng.choice([4, 8, 10, 14, 18])
        wx = self.mkwx(h, m, wspd=wspd)
        lines = [f"{i + 1}. {t}" for i, t in enumerate(drills)]
        return Idea("circuits", f"Circuit session at {h['id']}", [h, h],
                    "Stay in the pattern and fly this set, one circuit each:\n  " + "\n  ".join(lines) +
                    "\nFull stop at the end and write down which one you'd want to fly again.",
                    month=m, tod=self.tod(("morning", "midday", "afternoon")), wx=wx,
                    notes=["Every circuit is the same shape - the exercise changes, the picture out of the "
                           "window shouldn't.",
                           "Call your positions out loud even in the sim; it builds the habit."])

    def m_diversion(self):
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.6, 220), lambda a: self.usable(a)))
        if not dest:
            return None
        alts = self.within(dest, 15, 70, lambda a: self.usable(a) and a["id"] != h["id"])
        if not alts:
            return None
        alt = self.pick(alts)
        why = self.rng.choice([
            "a disabled aircraft closes the only runway", "the airport goes below minimums in fog",
            "a snow shower puts the runway out of limits", "a fuel spill shuts the field",
            "the runway lights fail as the sun goes down", "a TFR pops up over the field"])
        m = self.month()
        wx = self.mkwx(alt, m, good=False)
        return Idea("diversion", f"Diversion: {h['id']} towards {dest['id']}", [h, alt],
                    f"Plan the flight to {dest['id']} properly - route, fuel, weather, the lot. Then, about "
                    f"two-thirds of the way there, {why} and you have to go to {alt['id']} "
                    f"({d(dest, alt):.0f} nm away) instead. Do the diversion in the air: heading, time, fuel, "
                    f"and a plan for the arrival - no re-planning on the ground.",
                    month=m, tod=self.tod(), wx=wx,
                    notes=[f"Original destination: {dest['id']} ({dest['name']}).",
                           "Fly the aeroplane first, then navigate, then talk. In that order.",
                           "Check you still have the fuel for the alternate plus a reserve before you turn."])

    def m_pass(self):
        """Cross a mountain pass: two airports either side of high ground."""
        high = [a for a in self.pool if a["elev"] >= 3000]
        if len(high) < 2:
            return None
        for _ in range(40):
            h = self.rng.choice(high)
            if not self.usable(h):
                continue
            dest = self.pick(self.within(h, 30, self.R(0.5, 180),
                                         lambda a: self.usable(a) and abs(a["elev"] - h["elev"]) > 1200))
            if dest:
                break
        else:
            return None
        ridge = max(h["elev"], dest["elev"]) + self.rng.choice([2500, 3500, 4500])
        m = self.month([3, 4, 5, 6, 7, 8, 9])
        wspd = self.rng.choice([10, 15, 20, 25])
        wx = self.mkwx(dest, m, wspd=wspd)
        return Idea("pass", f"Mountain pass: {h['id']} to {dest['id']}", [h, dest],
                    f"Cross the high ground between the two. Plan to be at least 1,000 ft above the ridge - call "
                    f"it {ridge:,} ft - before you commit to the pass, and cross it at an angle so you can turn "
                    f"away. Wind is {wspd} kt, so expect the downdraught on the lee side.",
                    month=m, tod=self.tod(("dawn", "morning")), wx=wx,
                    notes=["Mountain rule: never fly up a valley you can't turn around in.",
                           "Morning is the smooth time. By early afternoon the same pass can be unflyable.",
                           "Fly the upwind side of the valley, where the air is going up."])

    def m_survey(self):
        h = self.home()
        area = self.pick(self.within(h, 20, self.R(0.35, 120)))
        if not area:
            return None
        n = self.rng.randint(4, 8)
        sp = self.rng.choice([0.5, 1.0, 1.5])
        alt = self.rng.choice([2000, 3000, 4000, 5000])
        hdg = self.rng.randrange(0, 180, 10)
        m = self.month()
        return Idea("survey", f"Survey grid near {area['id']}", [h, area],
                    f"Fly a survey grid centred on {area['id']} ({area['name']}): {n} parallel lines running "
                    f"{hdg:03d}/{(hdg + 180) % 360:03d} degrees, {sp} nm apart, {alt:,} ft above the ground, "
                    f"wings level and speed steady on every line. Turn at each end and come back the other way. "
                    f"Land at {area['id']} when the grid is done.",
                    month=m, tod=self.tod(("morning", "midday")), wx=self.mkwx(area, m),
                    overfly=[area["id"]],
                    notes=["The whole skill here is holding height and heading while you're bored.",
                           "Trim it out, pick a point on the horizon, and don't chase the altimeter.",
                           "Autopilot off - that's the point."])

    def m_firewatch(self):
        if self.ac.get("glider"):
            return None
        h = self.home()
        legs = []
        cur = h
        for _ in range(self.rng.randint(2, 3)):
            nxt = self.pick(self.within(cur, 15, self.R(0.25, 80),
                                        lambda a: a["id"] not in {x["id"] for x in [h] + legs}))
            if not nxt:
                break
            legs.append(nxt)
            cur = nxt
        if not legs:
            return None
        m = self.month([5, 6, 7, 8])
        wx = self.mkwx(legs[-1], m, wspd=self.rng.choice([8, 12, 18, 22]), temp=self.temp(m, legs[-1]) + 6)
        return Idea("firewatch", f"Fire patrol out of {h['id']}", [h] + legs,
                    "Hot, dry and windy - it's fire season. Fly the patrol at 1,500-2,000 ft AGL over the ridges "
                    "and drainages, orbit anything that looks like smoke long enough to fix its position, and "
                    "land at the far end to report it.",
                    month=m, tod=self.tod(("midday", "afternoon")), wx=wx,
                    overfly=[a["id"] for a in legs[:-1]],
                    notes=["Note the position of your 'smoke' as a bearing and distance from a known point.",
                           "Hot and high: your climb rate will be nothing like the book figure.",
                           "Orbits over rising ground eat height - keep one wing pointed at the valley."])

    def m_nordo(self):
        h = self.home()
        dest = self.pick(self.within(h, 25, self.R(0.5, 180), lambda a: self.usable(a) and not a["tower"]))
        if not dest:
            return None
        m = self.month()
        wspd = self.rng.choice([5, 8, 12, 15])
        wx = self.mkwx(dest, m, wspd=wspd)
        return Idea("nordo", f"No-radio arrival at {dest['id']}", [h, dest],
                    f"The radio quits on the way to {dest['id']}. It's non-towered, so nobody can tell you "
                    f"anything: work out the runway in use from the windsock and the other traffic, join the "
                    f"pattern where everyone else expects you, and keep your head on a swivel the whole way "
                    f"round. No radio calls at all from top of descent.",
                    month=m, tod=self.tod(("morning", "afternoon")), wx=wx,
                    notes=["Overfly 500-1,000 ft above pattern altitude first and look at the sock and the "
                           "traffic before you join.",
                           "Wide, predictable, well-lit: be where other people are looking.",
                           "Turn the landing light on - it's the only way you can 'talk'."])

    def m_dawn(self):
        h = self.home()
        dest = self.pick(self.within(h, 40, self.R(0.5, 200), lambda a: self.usable(a, night=True)))
        if not dest:
            return None
        m = self.month()
        wx = self.mkwx(dest, m, wspd=self.rng.choice([0, 3, 5]))
        return Idea("dawn", f"Dawn patrol to {dest['id']}", [h, dest],
                    f"Wheels up in the dark, and watch the sun come up on the way. The air at first light is "
                    f"glass-smooth and the visibility goes on forever. Depart {h['id']} in the last of the "
                    f"night, be level by first light, and land at {dest['id']} with the sun just up.",
                    month=m, tod="dawn", wx=wx,
                    notes=["Set the time so it's still dark at take-off - the app does this for you when it "
                           "sets up the flight.",
                           "Cold, still morning air means your aircraft will out-climb its own book figures.",
                           "Watch for fog forming in the valleys right at sunrise."])

    def m_lowceil(self):
        """Marginal VFR: low overcast, decent visibility, terrain to think about."""
        h = self.home()
        dest = self.pick(self.within(h, 30, self.R(0.5, 180), lambda a: self.usable(a)))
        if not dest:
            return None
        sky = self.rng.choice(["ovc25", "bkn15", "ovc12ra", "ovc10", "bkn6"])
        m = self.month([0, 1, 2, 3, 9, 10, 11])
        wx = self.mkwx(dest, m, sky=sky, wspd=self.rng.choice([6, 10, 14, 18]))
        ceil = wx.ceiling or 1000
        high = max(h["elev"], dest["elev"])
        alt = high + ceil
        notes = [f"The overcast is about {ceil:,} ft above the ground, so your cruise is roughly "
                 f"{alt:,} ft MSL - and that's 500 ft below the cloud, not in it.",
                 "Set yourself a hard turn-back point before you go: a ceiling, a visibility, and a time.",
                 "Scud running kills people. In the sim it's a decision-making exercise - practise turning round."]
        if self.ac["ifr"]:
            notes.append("You could file IFR instead. Deciding which is the right call is part of the flight.")
        return Idea("lowceil", f"Under the overcast: {h['id']} to {dest['id']}", [h, dest],
                    f"A low grey day. Ceiling {ceil:,} ft AGL, visibility {vis_str(wx.vis)}. Fly it VFR if you can "
                    f"do it legally and safely - and if you can't, turn round or divert. Plan the whole route "
                    f"below the cloud, and know the highest thing along it before you take off.",
                    month=m, tod=self.tod(("morning", "midday", "afternoon")), wx=wx, notes=notes)

    def m_lowvis(self):
        """Down to minimums: an approach in fog or heavy haze."""
        h = self.home()
        ifr = self.ac["ifr"]
        pred = (lambda a: bool(a["ils"])) if ifr else (lambda a: self.usable(a) and a["tower"])
        dest = self.pick(self.within(h, 30, self.R(0.5, 200), pred))
        if not dest:
            return None
        sky = self.rng.choice(MINIMUMS if ifr else ["haze15", "smoke1", "mist34", "haze3"])
        m = self.month([0, 1, 9, 10, 11])
        wx = self.mkwx(dest, m, sky=sky, wspd=self.rng.choice([0, 3, 5]))
        wx.extra = ""
        if ifr:
            ils = self.rng.choice(dest["ils"])
            mission = (f"File IFR. {dest['id']} is right at minimums: visibility {vis_str(wx.vis)}"
                       + (f", ceiling {wx.ceiling:,} ft" if wx.ceiling else "") +
                       f". Fly the ILS {ils} all the way down, decide at DH, and go missed if you haven't got "
                       f"the lights. Have the fuel for the miss and the alternate before you start.")
            notes = ["Brief the missed approach out loud before you're established.",
                     "Look for the approach lights, not the runway - that's what you'll see first.",
                     "Any drift after you break out means going around. Second attempts are for the fuel you "
                     "planned, not the fuel you hope you have."]
        else:
            mission = (f"Visibility is down to {vis_str(wx.vis)} in haze and smoke. VFR is legal, barely, and the "
                       f"horizon is gone. Navigate by instruments and the map, keep the wings level on the "
                       f"attitude indicator, and get into {dest['id']} before it gets any worse.")
            notes = ["With no horizon, trust the instruments - this is how VFR pilots get into trouble.",
                     "Fly a heading and a clock. Looking for landmarks in 1 mile of haze doesn't work.",
                     "Call it early: an en-route airport you can see beats a destination you can't."]
        return Idea("lowvis", f"Minimums at {dest['id']}", [h, dest], mission,
                    month=m, tod=self.tod(("dawn", "morning", "night")), wx=wx, ifr=ifr, notes=notes)

    def custom(self, idents, month=None, tod=None, sky=None):
        """Build an idea from your own list of airport idents."""
        stops = [self.lookup(i) for i in idents]
        if len(stops) < 2:
            raise ValueError("Enter at least two airports.")
        m = self.month() if month is None else month
        return Idea("custom", "Custom route: " + " - ".join(a["id"] for a in stops), stops,
                    "Your route, your rules.", month=m, tod=tod or self.tod(),
                    wx=self.mkwx(stops[-1], m, sky=sky))

    # ---- twists -------------------------------------------------------------
    def twist(self, idea):
        s = idea.stops
        opts = []   # (text, failure-or-None)
        legs = list(zip(s, s[1:]))
        a, b = max(legs, key=lambda l: d(*l))
        mid = interp(a, b, 0.5)
        near = self.within(mid, 0, 40, exclude=s)
        if near and not self.ac["heli"]:
            n = min(near, key=lambda x: d(mid, x))
            fail = {"type": "engine", "lat": mid["lat"], "lon": mid["lon"], "radius": 3,
                    "desc": f"engine failure halfway between {a['id']} and {b['id']}"}
            opts.append((f"Engine failure halfway between {a['id']} and {b['id']}. "
                         f"Spoiler - nearest usable field: {n['id']} {n['name']}, {d(mid, n):.0f} nm from the midpoint."
                         if not self.ac["multi"] else
                         f"Lose an engine halfway between {a['id']} and {b['id']}. Identify, verify, feather, "
                         f"and decide: continue or divert to {n['id']} ({d(mid, n):.0f} nm)?", fail))
        if s[-1]["tower"]:
            opts.append((f"Radio failure on arrival at {s[-1]['id']}: squawk 7600 and land using light-gun signals.",
                         {"type": "radio", "lat": s[-1]["lat"], "lon": s[-1]["lon"], "radius": 15,
                          "desc": f"radio failure 15 nm from {s[-1]['id']}"}))
        alt = self.within(s[-1], 8, 45, exclude=s)
        if alt:
            x = min(alt, key=lambda x: d(s[-1], x))
            opts.append((f"Destination weather goes down while you're en route - divert to {x['id']} "
                         f"({x['name']}, {d(s[-1], x):.0f} nm).", None))
        tot = sum(ete_min(d(*l), self.ac) for l in legs)
        dep = int(idea.hour * 60) + 15
        arr = dep + tot + 15 * (len(legs) - 1)
        opts.append((f"Schedule: take off at {dep // 60:02d}:{dep % 60:02d} and be on the ground at {s[-1]['id']} "
                     f"at exactly {(arr // 60) % 24:02d}:{arr % 60:02d} local (+/-2 min).", None))
        if not self.ac["heli"]:
            p = interp(s[0], s[1], min(1.0, 6 / max(1, d(s[0], s[1]))))
            opts += [("Vacuum failure after takeoff: fly partial panel (steam-gauge aircraft).",
                      {"type": "vacuum", "lat": p["lat"], "lon": p["lon"], "radius": 2,
                       "desc": f"vacuum failure ~6 nm out of {s[0]['id']}"}),
                     ("Nervous passenger: max 20 degrees of bank and 500 fpm descents all the way.", None),
                     ("Spot landing: touch down within 100 ft past the numbers on every landing.", None),
                     ("Depart with legal minimum fuel (trip + 30 min day / 45 min night). Plan it carefully.", None),
                     ("Go around from 200 ft on your first approach, whatever happens.", None)]
            if not idea.ifr:
                opts.append(("Pilotage only: no GPS, no moving map, no autopilot.", None))
        # a flight that is already about bad weather shouldn't also lose its instruments
        if idea.kind in ("lowvis", "lowceil", "ifr", "hold") or idea.wx.flight_rules() in ("IFR", "LIFR"):
            opts = [o for o in opts if (o[1] is None or o[1]["type"] != "vacuum")
                    and "partial panel" not in o[0] and "minimum fuel" not in o[0]]
        if idea.wx.vis < 3 or (idea.wx.ceiling or 9999) < 700:
            opts = [o for o in opts if "light-gun" not in o[0] and "Spot landing" not in o[0]]
        return self.rng.choice(opts) if opts else (None, None)

    # ---- driver -------------------------------------------------------------
    def generate(self, n, kinds, twist_chance):
        kinds = [k for k in kinds if k != "custom"]
        out, tries, last = [], 0, None
        seen = set()
        while kinds and len(out) < n and tries < n * 40:
            tries += 1
            k = self.rng.choice(kinds)
            if k == last and len(kinds) > 1:
                continue
            try:
                idea = getattr(self, "m_" + k)()
            except (IndexError, ValueError, ZeroDivisionError, KeyError):
                idea = None
            if not idea:
                continue
            if not self.scenery_ok(idea):
                continue
            sig = {a["id"] for a in idea.stops[1:]} - {idea.stops[0]["id"]}
            if sig & seen:
                continue
            seen |= sig
            last = k
            if self.rng.random() < twist_chance:
                idea.twist, idea.failure = self.twist(idea)
            out.append(idea)
        return out


# ==========================================================================
# Output
# ==========================================================================
def rwy_list(a):
    rs = [r for r in a["rwys"] if r["s"] != "helipad"]
    hp = len(a["rwys"]) - len(rs)
    txt = "; ".join(rwy_str(r) for r in sorted(rs, key=lambda r: -r["len"])[:4])
    out = "Rwy " + txt if txt else ""
    if hp:
        out += ("; " if out else "") + f"{hp} helipad{'s' if hp > 1 else ''}"
    return out or "(no runway data)"


def wrap(prefix, text, W):
    words, lines, cur = text.split(), [], prefix
    for w in words:
        if len(cur) + len(w) + 1 > W and cur.strip():
            lines.append(cur.rstrip())
            cur = " " * len(prefix)
        cur += w + " "
    lines.append(cur.rstrip())
    return lines


def fmt_idea(i, idea, ac, reveal, W=76):
    head = f" #{i}  {idea.title.upper()}" if i else f" {idea.title.upper()}"
    L = ["=" * W, head, f"     {MISSIONS[idea.kind]}  |  {ac['name']}", "-" * W]
    s = idea.stops
    total = 0
    if idea.hidden and not reveal:
        a = s[0]
        L.append(f" Depart:  {a['id']}  {a['name']} ({a['elev']:,} ft)")
        L.append(f"          {rwy_list(a)}")
    else:
        for j, a in enumerate(s):
            tag = "Depart:" if j == 0 else ("Arrive:" if j == len(s) - 1 else
                                            ("Overfly:" if a["id"] in getattr(idea, "overfly", ()) else f"Stop {j}:"))
            extra = []
            if a["tower"]:
                extra.append("towered")
            if a.get("ils"):
                extra.append("ILS " + ",".join(a["ils"]))
            loc = ", ".join(x for x in (a.get("city"), a.get("state")) if x)
            L.append(f" {tag:<8} {a['id']}  {a['name']} ({a['elev']:,} ft){'  - ' + loc if loc else ''}")
            if a.get("wonder"):
                L.append(f"          {a.get('notes') or 'A position, not an airport - fly over it.'}")
            else:
                L.append(f"          {rwy_list(a)}{'  [' + ', '.join(extra) + ']' if extra else ''}")
            if j < len(s) - 1:
                b = s[j + 1]
                dd = d(a, b)
                total += dd
                L.append(f"            |  {dd:.0f} nm, course {crs(a, b):03.0f} T, ~{ete_min(dd, ac)} min")
        L.append(f" Total:   {total:.0f} nm, ~{sum(ete_min(d(a, b), ac) for a, b in zip(s, s[1:]))} min flying,"
                 f" suggested {'IFR' if idea.ifr else 'VFR'} cruise {cruise_alt(s, ac, idea.ifr):,} ft")
    L.append("")
    L += wrap(" Mission: ", idea.mission, W)
    L += wrap(" When:    ", idea.when_text(), W)
    L += wrap(" Sun:     ", idea.sun_text(), W)
    L += wrap(" Weather: ", f"{idea.wx.describe()}  [at {idea.wx_at['id']}]", W)
    for n in idea.notes:
        L += wrap(" Note:    ", n, W)
    if idea.twist:
        L += wrap(" TWIST:   ", idea.twist, W)
    if idea.spoiler:
        L += wrap(" Spoiler: ", idea.spoiler if reveal else "(hidden - reveal it when you've landed)", W)
    return "\n".join(L)


def fms_text(idea, ac):
    s = idea.stops
    alt = cruise_alt(s, ac, idea.ifr)
    lines = ["I", "1100 Version", "CYCLE 2409", f"ADEP {s[0]['id']}", f"ADES {s[-1]['id']}", f"NUMENR {len(s)}"]
    for j, a in enumerate(s):
        via = "ADEP" if j == 0 else ("ADES" if j == len(s) - 1 else "DRCT")
        el = a["elev"] if via != "DRCT" else alt
        if a.get("spot"):
            typ = 28          # a plain lat/lon waypoint - X-Plane doesn't know your own spots
        elif a.get("kind") == "navaid":
            typ = {"VOR": 3, "NDB": 2}.get(a.get("navtype"), 1)
        else:
            typ = 1
        ident = a["id"].lstrip("*") if a.get("spot") else a["id"]
        lines.append(f"{typ} {ident} {via} {el:.6f} {a['lat']:.6f} {a['lon']:.6f}")
    return "\n".join(lines) + "\n"


def write_fms(path: Path, idea, ac):
    Path(path).write_text(fms_text(idea, ac))


def list_things():
    print("Aircraft profiles (-a):")
    for k, v in AIRCRAFT.items():
        print(f"  {k:<8} {v['name']:<48} {v['cruise']} kt, {v['range']} nm, min rwy {v['min_rwy']} ft")
    print("\nMission types (-m, comma-separated):")
    for k, v in MISSIONS.items():
        if k != "custom":
            print(f"  {k:<12} {v}")
    print("\nLive weather kinds (--live-weather KIND): any, ifr, wind, ts, snow, rain")


# ==========================================================================
def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Generate general-aviation flight ideas for X-Plane.",
                                epilog="Run with --list to see aircraft profiles and mission types. "
                                       "For the graphical version run xp_flight_ideas_gui.py")
    p.add_argument("-n", "--count", type=int, default=5, help="number of ideas (default 5)")
    p.add_argument("-a", "--aircraft", default="c172", help="aircraft profile (default c172)")
    p.add_argument("-m", "--missions", default="all", help="mission types, comma-separated (default all)")
    p.add_argument("--from", dest="from_", metavar="ICAO", help="always depart from this airport")
    p.add_argument("--near", metavar="ICAO", help="pick departure airports near this one")
    p.add_argument("--radius", type=float, default=150, help="radius around --near (nm, default 150)")
    p.add_argument("--max-leg", type=float, help="cap leg length (nm)")
    p.add_argument("--state", help="state/province (US: CO or Colorado; elsewhere as in X-Plane's data)")
    p.add_argument("--country", help="ISO country code (US, GB, NZ...), or ANY (default: US, or ANY with --near/--from/--continent)")
    p.add_argument("--continent", choices=[k for k in CONTINENTS if k != "Whole world"],
                   help="limit to a continent (use with --country ANY)")
    p.add_argument("--world", action="store_true", help="anywhere in the world (same as --country ANY)")
    p.add_argument("--scenic-world", dest="scenic_world", nargs="?", const="all", metavar="TAGS",
                   help="separate generator: scenic flights anywhere in the world. Optional TAGS, comma-separated: "
                        "mountains,islands,coast,ice,desert,volcano,water,landmark")
    p.add_argument("--scenic-source", default="all", metavar="SRC",
                   help="with --scenic-world, comma-separated: famous, wonders, gems, random, all "
                        "(default all but random)")
    p.add_argument("--anywhere", action="store_true",
                   help="throw a dart at the planet: random places anywhere in your scenery")
    p.add_argument("--wonders-near", dest="wonders_near", metavar="ICAO",
                   help="list the natural wonders nearest this airport and stop")
    p.add_argument("--no-private", dest="include_private", action="store_false", help="skip private strips")
    p.add_argument("--live-weather", dest="wx_kind", nargs="?", const="any", metavar="KIND",
                   help="add real-weather missions (downloads current METARs). KIND: any, ifr, wind, ts, snow, rain")
    p.add_argument("--twists", type=float, default=0.4, help="chance of a twist per idea, 0-1 (default 0.4)")
    p.add_argument("--reveal", action="store_true", help="show mystery-destination answers")
    p.add_argument("--save", action="store_true", help="write .fms plans into X-Plane's Output/FMS plans folder")
    p.add_argument("--fms-dir", metavar="DIR", help="write the .fms plans here instead (implies --save)")
    p.add_argument("--out", metavar="FILE", help="also save the ideas to a text file")
    p.add_argument("--seed", type=int, help="random seed (same seed = same ideas)")
    p.add_argument("--xplane", metavar="DIR", help="X-Plane install folder (auto-detected otherwise)")
    p.add_argument("--rebuild-cache", action="store_true", help="rescan scenery (after installing new scenery)")
    p.add_argument("--list", action="store_true", help="list aircraft profiles and mission types")
    args = p.parse_args()
    if args.fms_dir:
        args.save = True
    if args.world:
        args.country = "ANY"
    elif not args.country:
        args.country = "ANY" if (args.continent or args.near or args.from_) else "US"

    if args.list:
        list_things()
        return
    ac = AIRCRAFT.get(args.aircraft.lower())
    if not ac:
        sys.exit(f"Unknown aircraft '{args.aircraft}'. Options: {', '.join(AIRCRAFT)}")
    kinds = [k for k in MISSIONS if k not in NOT_GENERATED] if args.missions == "all" else \
        [k.strip() for k in args.missions.split(",")]
    if args.wx_kind and "realwx" not in kinds:
        kinds.append("realwx")
    bad = [k for k in kinds if k not in MISSIONS]
    if bad:
        sys.exit(f"Unknown mission type(s): {', '.join(bad)}. Options: {', '.join(MISSIONS)}")

    root = find_xplane(args.xplane)
    if not root:
        sys.exit("Couldn't find X-Plane. Pass the install folder, e.g.  --xplane \"C:\\X-Plane 12\"")
    save_config(xplane_root=str(root))

    airports = load_airports(root, args.rebuild_cache)
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    if args.wonders_near:
        import xp_scenic
        import xp_wonders
        finder = xp_scenic.ScenicFinder(sys.modules[__name__], airports, ac, random.Random(seed),
                                        args.include_private)
        ref = finder.by_id.get(args.wonders_near.strip().upper())
        if not ref:
            sys.exit(f"Airport '{args.wonders_near}' not found in your X-Plane data.")
        reach = {c["title"]: c for c in finder.wonders()}
        rows = sorted(((xp_wonders.nm(ref["lat"], ref["lon"], w["lat"], w["lon"]), w)
                       for w in xp_wonders.ALL), key=lambda x: x[0])
        print(f"Natural wonders nearest {ref['id']} {ref['name']}"
              f"   ({len(reach)} of {len(xp_wonders.ALL)} reachable in your scenery)\n")
        for d, w in rows[:args.count if args.count > 5 else 25]:
            mark = " " if w["name"] in reach else "*"
            print(f"{d:7,.0f} nm {mark} {w['name'][:28]:28s} {w['text']}")
        print("\n* = no usable runway near it in your scenery.")
        return
    if args.scenic_world or args.anywhere:
        import xp_scenic
        tags = (None if not args.scenic_world or args.scenic_world == "all"
                else [t.strip() for t in args.scenic_world.split(",")])
        src = {t.strip() for t in (args.scenic_source or "all").split(",")}
        allsrc = "all" in src
        finder = xp_scenic.ScenicFinder(sys.modules[__name__], airports, ac, random.Random(seed),
                                        args.include_private)
        if args.anywhere:
            ideas = finder.random_world(args.count, args.continent or "Whole world", tags)
        else:
            ideas = finder.surprise(args.count, tags, args.continent or "Whole world",
                                    allsrc or "famous" in src, allsrc or "gems" in src,
                                    allsrc or "wonders" in src, "random" in src)
        if not ideas:
            sys.exit("No scenic flights found with those settings.")
        print(f"Scenic flights anywhere in the world  (seed {seed})")
        for i, idea in enumerate(ideas, 1):
            print(fmt_idea(i, idea, ac, True))
        if args.save:
            fdir = Path(args.fms_dir) if args.fms_dir else root / "Output" / "FMS plans"
            fdir.mkdir(parents=True, exist_ok=True)
            for i, idea in enumerate(ideas, 1):
                write_fms(fdir / f"SCENIC{i:02d}_{idea.stops[0]['id']}_{idea.stops[-1]['id']}.fms", idea, ac)
            print(f"\nSaved {len(ideas)} flight plans to {fdir}")
        return
    try:
        gen = Generator(airports, ac, random.Random(seed), args)
    except KeyError as e:
        sys.exit(str(e.args[0]))
    if not gen.pool:
        sys.exit("No usable airports match that region/aircraft combination.")
    if "realwx" in kinds:
        import xp_wx
        src = xp_wx.MetarSource(CACHE_DIR)
        try:
            n = src.refresh()
            print(f"Live weather: {n:,} METARs", file=sys.stderr)
        except Exception as e:
            print(f"Live weather unavailable: {e}", file=sys.stderr)
        gen.metars = src.obs
        gen.wx_kind = args.wx_kind or "any"

    ideas = gen.generate(args.count, kinds, args.twists)
    if not ideas:
        sys.exit("Couldn't build any ideas with those settings - try other mission types or a bigger area.")

    text = [f"X-Plane flight ideas  (seed {seed}, {len(gen.pool):,} usable airports)"]
    for i, idea in enumerate(ideas, 1):
        text.append(fmt_idea(i, idea, ac, args.reveal))
    print("\n".join(text))

    if args.save:
        fdir = Path(args.fms_dir) if args.fms_dir else root / "Output" / "FMS plans"
        fdir.mkdir(parents=True, exist_ok=True)
        print("\nSaved flight plans:")
        for i, idea in enumerate(ideas, 1):
            if idea.hidden and not args.reveal:
                print(f"  #{i}: mystery flight - no plan saved (that would spoil it)")
                continue
            name = f"IDEA{i:02d}_{idea.stops[0]['id']}_{idea.stops[-1]['id']}.fms"
            write_fms(fdir / name, idea, ac)
            print(f"  #{i}: {fdir / name}")
    if args.out:
        full = [text[0]] + [fmt_idea(i, idea, ac, True) for i, idea in enumerate(ideas, 1)]
        Path(args.out).write_text("\n".join(full) + "\n", encoding="utf-8")
        print(f"\nIdeas saved to {args.out}")


if __name__ == "__main__":
    main()
