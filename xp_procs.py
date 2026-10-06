"""
xp_procs.py - the real published procedures, read out of your own X-Plane.

X-Plane ships coded instrument procedures in CIFP/<ICAO>.dat - one file per
airport, holding every SID, STAR and instrument approach it knows about, as
ARINC-424-style rows. Navigraph's FMS data replaces the same files, so if the
user has that installed this reads their current cycle instead of the stock one.

What this gives the app is the names and the fix sequences: "runway 16L has
BAYLR6, TRUKN2 and SHEAD9", and the waypoints each one strings together. That is
enough to put a real departure in the GPS instead of an invented straight-out.

What it is NOT is the chart. The rows carry altitude and speed restrictions that
this module reads only loosely, and the leg types that aren't a simple fix-to-fix
(headings to an altitude, arcs, holds) are passed over rather than flown. Any
briefing built on this says so, and points at the plate.

  procs = read(xplane_root, "KDEN")
  procs.sids_for("16L")        -> ["BAYLR6", "SHEAD9", ...]
  procs.route("BAYLR6", "16L") -> ["BAYLR", "TOMSN", ...]
"""
from __future__ import annotations

from pathlib import Path

# ARINC 424 path-and-termination codes. We only fly the ones that go to a named
# fix; the rest are listed in the briefing as "see the plate".
PATH_TERM = {"AF", "CA", "CD", "CF", "CI", "CR", "DF", "FA", "FC", "FD", "FM",
             "HA", "HF", "HM", "IF", "PI", "RF", "TF", "VA", "VD", "VI", "VM", "VR"}
#: the ones that actually name a waypoint you can put in a flight plan
FIX_TERM = {"AF", "CD", "CF", "DF", "FC", "FD", "HF", "IF", "RF", "TF"}

#: ARINC route types, grouped into the three segments a procedure is built from
SID_RANK = {"1": 0, "4": 0, "F": 0, "T": 0,          # runway transition
            "2": 1, "5": 1, "M": 1,                  # common route
            "3": 2, "6": 2, "S": 2, "V": 2}          # enroute transition
STAR_RANK = {"1": 0, "4": 0, "7": 0, "F": 0,         # enroute transition
             "2": 1, "5": 1, "8": 1, "M": 1,         # common route
             "3": 2, "6": 2, "9": 2, "S": 2}         # runway transition

CIFP_DIRS = (("Custom Data", "CIFP"), ("Resources", "default data", "CIFP"))


def _num(v, default=None):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def rwy_key(end):
    """RW16L and 16L and 16 all mean the same runway end here."""
    e = str(end or "").strip().upper()
    if e.startswith("RW"):
        e = e[2:]
    return e.lstrip("0") or e


class Leg:
    """One row of a procedure."""

    __slots__ = ("seq", "fix", "region", "pt", "alt", "alt2", "spd", "course", "dist", "raw")

    def __init__(self, seq, fix, region, pt, alt=None, alt2=None, spd=None,
                 course=None, dist=None, raw=""):
        self.seq, self.fix, self.region, self.pt = seq, fix, region, pt
        self.alt, self.alt2, self.spd = alt, alt2, spd
        self.course, self.dist, self.raw = course, dist, raw

    @property
    def flyable(self):
        return bool(self.fix) and self.pt in FIX_TERM

    def __repr__(self):
        return f"<Leg {self.seq} {self.pt} {self.fix or '-'}>"


class Proc:
    """One named procedure, with its legs grouped by transition."""

    def __init__(self, kind, name):
        self.kind, self.name = kind, name
        self.segments = {}          # (rank, transition) -> [Leg]

    # ---- what it connects to ------------------------------------------
    @property
    def runways(self):
        """The runway ends this procedure has a transition for.

        An empty set means it doesn't care which runway you use. "ALL" in the
        transition column is the common segment, not a runway - a procedure with
        both RW16L and ALL serves 16L only, and reading ALL as "any runway" is
        what would offer you a Denver SID off a runway it was never drawn for.
        """
        return {rwy_key(t) for (_r, t) in self.segments if (t or "").upper().startswith("RW")}

    @property
    def transitions(self):
        """The named enroute transitions (not runways, not the common route)."""
        return sorted({t for (_r, t) in self.segments
                       if t and not t.upper().startswith("RW") and t.upper() != "ALL"})

    def serves(self, runway):
        rws = self.runways
        return not rws or rwy_key(runway) in rws

    # ---- the route it flies -------------------------------------------
    def legs(self, runway=None, transition=None):
        """Every leg, in the order it is flown, for one runway and transition."""
        want_rw = rwy_key(runway) if runway else None
        picked = []
        for (rank, trans), legs in self.segments.items():
            t = (trans or "").upper()
            if t.startswith("RW") or t == "ALL":
                if want_rw and t != "ALL" and rwy_key(t) != want_rw:
                    continue
            elif t:
                if transition and t != transition.upper():
                    continue
                if not transition:
                    continue           # don't guess which enroute transition you want
            picked.append((rank, trans, legs))
        picked.sort(key=lambda x: (x[0], x[1] or ""))
        out = []
        for _rank, _trans, legs in picked:
            out.extend(sorted(legs, key=lambda l: l.seq))
        return out

    def route(self, runway=None, transition=None):
        """Just the waypoint names, with repeats collapsed."""
        out = []
        for leg in self.legs(runway, transition):
            if leg.flyable and (not out or out[-1] != leg.fix):
                out.append(leg.fix)
        return out

    def unflyable(self, runway=None, transition=None):
        """The legs we deliberately leave out - headings, arcs, holds."""
        return [l for l in self.legs(runway, transition) if not l.flyable]

    def __repr__(self):
        return f"<{self.kind} {self.name} rwys={sorted(self.runways)}>"


class Procs:
    """Everything one airport publishes."""

    def __init__(self, icao, source=None):
        self.icao, self.source = icao, source
        self.sids, self.stars, self.approaches = {}, {}, {}

    def __bool__(self):
        return bool(self.sids or self.stars or self.approaches)

    def _of(self, kind):
        return {"SID": self.sids, "STAR": self.stars, "APPCH": self.approaches}[kind]

    def sids_for(self, runway):
        return sorted(p.name for p in self.sids.values() if p.serves(runway))

    def stars_for(self, runway):
        return sorted(p.name for p in self.stars.values() if p.serves(runway))

    def approaches_for(self, runway):
        """Approach names whose own runway matches - RNAV (GPS) Y 22 is 'R22-Y'."""
        r = rwy_key(runway)
        out = []
        for p in self.approaches.values():
            if appch_runway(p.name) == r:
                out.append(p.name)
        return sorted(out)

    def get(self, kind, name):
        return self._of(kind).get(str(name).upper())

    def route(self, kind, name, runway=None, transition=None):
        p = self.get(kind, name)
        return p.route(runway, transition) if p else []


#: ARINC 424 approach-type letters: (what it is, does it have a glideslope?)
#: None means "the code doesn't say" - an RNAV procedure may publish LPV, or only LNAV,
#: and which one is on the plate rather than in the coded data.
APPCH_KIND = {
    "B": ("localizer back course", False),
    "D": ("VOR/DME", False),
    "F": ("FMS", False),
    "G": ("IGS", True),
    "I": ("ILS", True),
    "J": ("GLS", True),
    "L": ("localizer only", False),
    "M": ("MLS", True),
    "N": ("NDB", False),
    "P": ("GPS", None),
    "Q": ("NDB/DME", False),
    "R": ("RNAV (GNSS)", None),
    "S": ("VOR with DME required", False),
    "T": ("TACAN", False),
    "U": ("SDF", False),
    "V": ("VOR", False),
    "X": ("LDA", False),
    "Y": ("MLS type B/C", True),
}


def appch_kind(name):
    """(letter, what it is, has a glideslope) for a coded approach name like I16LZ."""
    n = str(name or "").upper().strip()
    if not n:
        return "", "", None
    what, gs = APPCH_KIND.get(n[0], ("", None))
    return n[0], what, gs


def appch_runway(name):
    """The runway an approach's coded name belongs to: I22 -> 22, R16L-Y -> 16L."""
    n = str(name or "").upper().split("-")[0]
    digits = ""
    for ch in n[1:]:
        if ch.isdigit():
            digits += ch
        elif digits and ch in "LRC":
            digits += ch
            break
        elif digits:
            break
    return rwy_key(digits)


# --------------------------------------------------------------------------
# Reading the file
# --------------------------------------------------------------------------
def _path_term(fields):
    """Find the path-and-termination code without trusting a column number.

    The spec puts it at a fixed offset, but continuation records and the odd
    vendor file shift things, and a wrong guess silently drops a whole procedure.
    Scanning for the one two-letter token that is a real PT code is steadier.
    """
    for i in range(6, min(len(fields), 26)):
        v = fields[i].strip().upper()
        if len(v) == 2 and v in PATH_TERM:
            return v, i
    return "", -1


def parse(text):
    """[(kind, Proc)] from the contents of one CIFP file."""
    procs = {}
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        head, _, rest = line.partition(":")
        kind = head.strip().upper()
        if kind not in ("SID", "STAR", "APPCH"):
            continue
        fields = rest.split(",")
        if len(fields) < 5:
            continue
        seq = int(_num(fields[0], 0) or 0)
        rtype = (fields[1] or "").strip().upper()[:1]
        name = (fields[2] or "").strip().upper()
        trans = (fields[3] or "").strip().upper()
        fix = (fields[4] or "").strip().upper()
        region = (fields[5] or "").strip().upper() if len(fields) > 5 else ""
        if not name:
            continue
        pt, at = _path_term(fields)
        alt = alt2 = spd = None
        if at > 0:
            tail = [f.strip() for f in fields[at + 1:]]
            nums = [_num(t) for t in tail]
            got = [n for n in nums if n is not None and n >= 0]
            if got:
                alt = got[0] if got[0] >= 100 else None
                alt2 = next((n for n in got[1:] if n >= 100), None)
                spd = next((n for n in got if 0 < n < 400), None)
        key = (kind, name)
        p = procs.get(key)
        if p is None:
            p = procs[key] = Proc(kind, name)
        rank = (SID_RANK if kind == "SID" else STAR_RANK).get(rtype, 1) if kind != "APPCH" \
            else (0 if rtype == "A" else 1)
        p.segments.setdefault((rank, trans), []).append(
            Leg(seq, fix, region, pt, alt, alt2, spd, raw=line))
    return list(procs.values())


def cifp_file(root, icao):
    """Where this airport's procedures live - the user's own data wins."""
    icao = str(icao or "").strip().upper()
    if not icao:
        return None
    for parts in CIFP_DIRS:
        p = Path(root).joinpath(*parts) / f"{icao}.dat"
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def read(root, icao):
    """Every procedure published for one airport, or an empty Procs."""
    icao = str(icao or "").strip().upper()
    out = Procs(icao)
    path = cifp_file(root, icao)
    if not path:
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    out.source = path
    for p in parse(text):
        out._of(p.kind)[p.name] = p
    return out


def have_cifp(root):
    """Whether this install has any coded procedures at all."""
    for parts in CIFP_DIRS:
        d = Path(root).joinpath(*parts)
        try:
            if d.is_dir() and any(d.glob("*.dat")):
                return d
        except OSError:
            continue
    return None


# --------------------------------------------------------------------------
# Where the waypoints actually are
# --------------------------------------------------------------------------
def fixes(root, wanted=None):
    """{ident: (lat, lon)} from earth_fix.dat, for turning a route into a line.

    `wanted` keeps the dictionary small: the file has a few hundred thousand rows
    and we usually care about a dozen of them.
    """
    want = {str(w).upper() for w in wanted} if wanted else None
    out = {}
    for parts in (("Custom Data", "earth_fix.dat"),
                  ("Resources", "default data", "earth_fix.dat")):
        p = Path(root).joinpath(*parts)
        try:
            if not p.is_file():
                continue
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    t = line.split()
                    if len(t) < 3 or not t[0][0].isdigit() and t[0][0] not in "-+":
                        continue
                    ident = t[2].upper()
                    if want is not None and ident not in want:
                        continue
                    if ident in out:
                        continue
                    lat, lon = _num(t[0]), _num(t[1])
                    if lat is None or lon is None:
                        continue
                    out[ident] = (lat, lon)
        except OSError:
            continue
        if out and (want is None or len(out) >= len(want)):
            break
    return out


def positions(root, idents, core=None, navaids=None):
    """Positions for a route's waypoints, from fixes first and then navaids."""
    idents = [str(i).upper() for i in idents]
    out = dict(fixes(root, idents))
    missing = [i for i in idents if i not in out]
    if not missing:
        return out
    pool = navaids
    if pool is None and core is not None:
        pool = []
        for parts in (("Custom Data", "earth_nav.dat"),
                      ("Resources", "default data", "earth_nav.dat")):
            p = Path(root).joinpath(*parts)
            try:
                if p.is_file():
                    pool = core.parse_navaids(p)
                    break
            except (OSError, AttributeError):
                pool = []
    for n in (pool or []):
        ident = str(n.get("id", "")).upper()
        if ident in missing and ident not in out:
            out[ident] = (n["lat"], n["lon"])
    return out
