"""
xp_avionics.py - setting the aeroplane up for the approach, not just putting it there.

X-Plane will drop you on final. It won't tune the localizer, set the course, put
the tower on COM1, wind the altitude bug to the missed approach height or arm the
autopilot. This works out what all of those should be and hands back a list of
datarefs to write and commands to send.

Two honest limits.

The datarefs here are X-Plane's built-in ones. A default Cessna, Baron or King Air
takes them. Study-level add-ons with their own avionics - the Zibo, most G1000
implementations, anything with a custom FMS - often ignore them and keep their own
state, so on those aircraft some of this quietly does nothing.

And there is no way through the Web API to load a published RNAV procedure. What
`rnav_fms` builds is a straight-in on the runway centreline with fixes at sensible
distances - it flies like the final segment of an RNAV approach, and it is not the
charted procedure. Don't use it to practise something you intend to fly for real.
"""
from __future__ import annotations

import math

import xp_approach

FT_PER_NM = 6076.12

# What each autopilot setting does.
AP_MODES = {
    "radios": "Radios and bugs only - the autopilot is left alone",
    "armed": "Bugs set and the approach armed, but the servos are off",
    "coupled": "Flying it: servos on, approach mode engaged",
}

# X-Plane's built-in avionics datarefs.
NAV1_FREQ = "sim/cockpit/radios/nav1_freq_hz"       # 10s of kHz: 11015 is 110.15
NAV1_OBS = "sim/cockpit/radios/nav1_obs_degm"
NAV2_FREQ = "sim/cockpit/radios/nav2_freq_hz"
NAV2_OBS = "sim/cockpit/radios/nav2_obs_degm"
COM1_FREQ = "sim/cockpit/radios/com1_freq_hz"
COM2_FREQ = "sim/cockpit/radios/com2_freq_hz"
BARO = "sim/cockpit/misc/barometer_setting"
AP_ALT = "sim/cockpit/autopilot/altitude"
AP_HDG = "sim/cockpit/autopilot/heading_mag"
AP_SPD = "sim/cockpit/autopilot/airspeed"
AP_VVI = "sim/cockpit/autopilot/vertical_velocity"
MAGVAR = "sim/flightmodel/position/magnetic_variation"

CMD_NAV = "sim/autopilot/NAV"
CMD_APPR = "sim/autopilot/approach"
CMD_HDG = "sim/autopilot/heading_hold"
CMD_ALT = "sim/autopilot/altitude_hold"
CMD_SERVOS_ON = "sim/autopilot/servos_on"
CMD_SERVOS_OFF = "sim/autopilot/servos_off"
CMD_FD_ON = "sim/autopilot/fdir_on"


def khz10(mhz):
    """110.15 MHz -> 11015, the units X-Plane's radio datarefs use."""
    return int(round(float(mhz) * 100))


def magnetic(true_deg, variation):
    """True to magnetic. X-Plane reports variation east-positive."""
    return (float(true_deg) - float(variation)) % 360


def approach_kind(opt, want="auto"):
    """What sort of approach this runway can actually offer.

    want: auto / ils / rnav. Returns (kind, sentence).
    """
    has_loc = bool(opt and opt.get("ils"))
    if want == "ils":
        if has_loc:
            return "ils", "ILS or localizer, tuned and identified."
        return "none", ("This runway has no localizer in your scenery, so there is no ILS to fly. "
                        "Switch to RNAV, or pick a runway with an ILS.")
    if want == "rnav":
        return "rnav", "RNAV (GPS) straight-in - built here, not the published procedure."
    if has_loc:
        return "ils", "ILS or localizer, tuned and identified."
    return "rnav", "No localizer here, so RNAV (GPS) straight-in - built here, not the published procedure."


def missed_altitude(apt, opt):
    """A sensible height to wind the altitude bug to for the missed approach."""
    base = apt["elev"] + (2000 if opt and opt.get("ils") else 2500)
    return int(round(base / 100.0) * 100)


def tower_freq(apt):
    """(frequency, what to call it). Falls back to the usual CTAF when nothing is published."""
    f = (apt.get("freqs") or {})
    if f.get("twr"):
        return f["twr"], "tower"
    if f.get("ctaf"):
        return f["ctaf"], "CTAF"
    if apt.get("tower"):
        return None, "tower (no frequency in your scenery)"
    return 122.8, "CTAF (122.8 assumed - your scenery doesn't say)"


def plan(apt, opt, dist_nm, ac, wx, ap_mode="armed", want="auto", variation=0.0):
    """Everything to set for this approach.

    Returns a dict:
      kind      - ils / rnav / none
      sets      - [(dataref, value, "what it is")]
      commands  - [(command, "what it does")]
      lines     - what to tell the person
      warnings  - what might not take
    """
    kind, kind_txt = approach_kind(opt, want)
    sets, cmds, lines, warn = [], [], [], []
    if not opt:
        return {"kind": "none", "sets": [], "commands": [], "lines": ["Pick a runway first."],
                "warnings": []}

    course_true = opt.get("course") if opt.get("course") is not None else opt["hdg"]
    course_mag = magnetic(course_true, variation)
    lines.append(kind_txt)

    if kind == "ils" and opt.get("freq"):
        sets.append((NAV1_FREQ, khz10(opt["freq"]), f"NAV1 {opt['freq']:.2f} ({opt.get('ident') or 'LOC'})"))
        sets.append((NAV1_OBS, round(course_mag), f"NAV1 course {course_mag:03.0f}° magnetic"))
        sets.append((NAV2_FREQ, khz10(opt["freq"]), "NAV2 on the same localizer, as a cross-check"))
        sets.append((NAV2_OBS, round(course_mag), f"NAV2 course {course_mag:03.0f}°"))
        lines.append(f"Localizer {opt.get('ident') or ''} {opt['freq']:.2f}, course {course_mag:03.0f}° "
                     f"magnetic ({course_true:03.0f}° true). Identify it before you trust it.")
    elif kind == "ils":
        warn.append("Your scenery knows this runway has a localizer but not its frequency, "
                    "so NAV1 is left alone.")
    else:
        sets.append((NAV1_OBS, round(course_mag), f"NAV1 course {course_mag:03.0f}°, for reference"))
        lines.append(f"Final approach course {course_mag:03.0f}° magnetic. The GPS flies the fixes; "
                     f"there is no localizer to back it up.")

    f, what = tower_freq(apt)
    if f:
        sets.append((COM1_FREQ, khz10(f), f"COM1 {f:.3f} ({what})"))
        lines.append(f"COM1 on {f:.3f} - {what}.")
    else:
        warn.append(f"No {what} frequency in your scenery, so COM1 is left alone.")
    atis = (apt.get("freqs") or {}).get("atis")
    if atis:
        sets.append((COM2_FREQ, khz10(atis), f"COM2 {atis:.3f} (ATIS)"))

    sets.append((BARO, round(float(wx.altimeter), 2), f"altimeter {wx.altimeter:.2f}"))

    if ap_mode in ("armed", "coupled"):
        miss = missed_altitude(apt, opt)
        vref = xp_approach.vref(ac)
        sets.append((AP_ALT, miss, f"altitude bug {miss:,} ft for the missed approach"))
        sets.append((AP_HDG, round(course_mag), f"heading bug {course_mag:03.0f}°"))
        sets.append((AP_SPD, round(vref + 10), f"speed bug {vref + 10:.0f} kt"))
        sets.append((AP_VVI, -round(xp_approach.descent_fpm(max(40.0, vref - opt["head"])) / 50) * 50,
                     "vertical speed bug for the glidepath"))
        lines.append(f"Altitude bug at {miss:,} ft - that is where you go if you don't see it. "
                     f"Heading bug on the final approach course.")
    if ap_mode == "armed":
        cmds.append((CMD_FD_ON, "flight director on"))
        cmds.append((CMD_APPR, "approach mode armed"))
        lines.append("The approach is armed and the flight director is showing, but the servos are off - "
                     "you are flying. Press the autopilot when you want it.")
    elif ap_mode == "coupled":
        cmds.append((CMD_SERVOS_ON, "autopilot servos on"))
        cmds.append((CMD_APPR, "approach mode engaged"))
        lines.append("The autopilot is flying the approach. Watch it, and take it away from it the "
                     "moment it does something you don't like.")
    else:
        lines.append("The autopilot is left exactly as you had it.")

    if not ac.get("ifr", True):
        warn.append("This aeroplane isn't set up for instrument flight, so some of this may have "
                    "nothing to act on.")
    warn.append("These are X-Plane's built-in avionics datarefs. Aircraft with their own avionics "
                "- most G1000s, most study-level add-ons - keep their own radios and may ignore them.")
    return {"kind": kind, "sets": sets, "commands": cmds, "lines": lines, "warnings": warn}


# ==========================================================================
# A straight-in for the GPS, when there's no localizer
# ==========================================================================
def along_course(lat, lon, course_true, nm):
    """A position `nm` out on the reciprocal of the approach course (ie out on final)."""
    brg = math.radians((course_true + 180) % 360)
    dlat = nm * math.cos(brg) / 60.0
    dlon = nm * math.sin(brg) / (60.0 * max(0.05, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def rnav_fixes(apt, opt, start_nm=6.0, fixes=True):
    """[(name, lat, lon, altitude)] from the initial fix down to the threshold."""
    lat, lon = opt.get("lat", apt["lat"]), opt.get("lon", apt["lon"])
    crs = opt.get("course") if opt.get("course") is not None else opt["hdg"]
    out = []
    if fixes:
        for nm, tag in ((max(start_nm, 6.0), "IF"), (4.0, "FAF"), (1.5, "MAP")):
            la, lo = along_course(lat, lon, crs, nm)
            out.append((f"{tag}{opt['end']}"[:8], la, lo,
                        int(apt["elev"] + xp_approach.height_at(nm))))
    out.append((f"RW{opt['end']}"[:8], lat, lon, int(apt["elev"])))
    return out


def rnav_fms(apt, opt, start_nm=6.0, fixes=True, dep=None):
    """An .fms 1100 plan that flies the straight-in. Waypoints are type 28 (lat/lon)."""
    pts = rnav_fixes(apt, opt, start_nm, fixes)
    rows = []
    if dep:
        rows.append(f"1 {dep['id']} ADEP {float(dep['elev']):.6f} {dep['lat']:.6f} {dep['lon']:.6f}")
    for i, (name, la, lo, alt) in enumerate(pts):
        last = i == len(pts) - 1
        rows.append(f"28 {name} {'ADES' if last else 'DRCT'} "
                    f"{float(alt):.6f} {la:.6f} {lo:.6f}")
    head = ["I", "1100 Version", "CYCLE 2409",
            f"ADEP {dep['id'] if dep else apt['id']}", f"ADES {apt['id']}",
            f"NUMENR {len(rows)}"]
    return "\n".join(head + rows) + "\n"
