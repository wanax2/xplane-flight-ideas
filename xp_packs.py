"""
xp_packs.py - putting scenery_packs.ini back in the right order.

X-Plane draws scenery top-down: the first pack in Custom Scenery/scenery_packs.ini
that has something to say about a tile wins, and everything below it is ignored
for that tile. So the file is a priority list, and if it is in the wrong order the
symptoms are the classic ones - your custom airport buried under a mesh, ortho
photos hidden behind default terrain, autogen buildings sitting in a field that
should be a runway.

X-Plane writes that file itself, alphabetically, whenever it finds a new folder.
Alphabetical is almost never the order you want.

The order this uses, highest priority first:

    1. custom airports            the airport you installed beats everything
    2. Global Airports            X-Plane's own, below yours and above the ground
    3. overlays                   buildings, roads, forests - simHeaven X-World
                                  and the like
    4. libraries                  objects the overlays refer to
    5. photo ground / ortho       X-Plane Map Enhancement, Ortho4XP, zOrtho
    6. terrain mesh               HD/UHD Mesh, AlpilotX
    7. X-Plane's own global scenery

Overlays above photo scenery is the arrangement that lets two big packages
coexist: one supplies the ground, the other supplies what stands on it.

One rule matters more than the sorting: a package that ships its folders numbered
- simHeaven's X-World is the obvious one, with its 1-vfr-landmarks, 2-extras,
3-regions and so on - has already told you the order it wants its own parts in.
That order is kept exactly as the numbers say, and the family is kept together as
a block. Sorting those alphabetically is how people break X-World.

Nothing here writes anything without being asked, and when it does write it keeps
a timestamped copy of the file it replaced.
"""
from __future__ import annotations

import itertools
import os
import re
import time
from pathlib import Path

PACK = re.compile(r"^\s*SCENERY_PACK\s+(.*?)\s*$", re.I)
DISABLED = re.compile(r"^\s*SCENERY_PACK_DISABLED\s+(.*?)\s*$", re.I)

# What a folder's name suggests it is. Checked in order; folder contents win where known.
HINTS = [
    # an explicit "overlay" in the name wins - yOrtho4XP_Overlays is an overlay, not ground
    ("overlay", re.compile(r"overlay", re.I)),
    ("ortho", re.compile(r"map[\s_-]*enhance|xpme|ortho4xp|zortho|z_?ortho|photo[\s_-]*scenery|"
                         r"^yOrtho|_ortho|orthophoto|truearth|photoreal", re.I)),
    ("mesh",  re.compile(r"hd[\s_-]*mesh|uhd[\s_-]*mesh|alpilotx|forkboy|terrain[\s_-]*mesh|"
                         r"\bmesh\b|dem[\s_-]*scenery", re.I)),
    ("overlay", re.compile(r"simheaven|x-?world|autogen|overlay|osm|world2xplane|w2xp|"
                           r"vfr[\s_-]*landmark|landmark|scenery[\s_-]*gateway[\s_-]*overlay", re.I)),
    ("library", re.compile(r"library|libraries|opensceneryx|\blib\b|handyobjects|ruscenery|"
                           r"world[\s_-]*models|misterx|3d[\s_-]*people|flags[\s_-]*of", re.I)),
]

RANK = {"airport": 10, "global_airports": 20, "overlay": 30, "library": 40,
        "ortho": 50, "mesh": 60, "unknown": 45, "gone": 80, "global": 90}

WHAT = {"airport": "custom airport", "global_airports": "X-Plane's Global Airports",
        "overlay": "overlay (buildings, roads, forests)", "library": "object library",
        "ortho": "photo ground / ortho", "mesh": "terrain mesh",
        "global": "X-Plane's own global scenery", "unknown": "can't tell",
        "gone": "not on disk any more"}

# how to count them in one line
PLURAL = {"airport": ("custom airport", "custom airports"),
          "global_airports": ("Global Airports", "Global Airports"),
          "overlay": ("overlay", "overlays"), "library": ("library", "libraries"),
          "ortho": ("photo/ortho pack", "photo/ortho packs"),
          "mesh": ("mesh pack", "mesh packs"), "global": ("global scenery", "global scenery"),
          "unknown": ("unidentified pack", "unidentified packs"),
          "gone": ("missing folder", "missing folders")}

# A family is a package that ships several numbered folders and cares about their order.
FAMILY = [
    ("simHeaven X-World", re.compile(r"^(.*?simheaven[^0-9]*?)[-_ ]*(\d+)[-_ ]", re.I)),
    ("numbered set", re.compile(r"^(.*?)[-_ ](\d+)[-_ ][a-z]", re.I)),
]


class Entry:
    """One line of scenery_packs.ini."""

    def __init__(self, raw, path=None, enabled=True, kind="unknown", order=0):
        self.raw = raw                 # the line exactly as it was
        self.path = path or ""         # "Custom Scenery/Whatever/"
        self.enabled = enabled
        self.kind = kind
        self.order = order             # where it was in the original file
        self.family = None             # ("simHeaven X-World", 3) when it belongs to a set
        self.note = ""

    @property
    def name(self):
        p = self.path.replace("\\", "/").rstrip("/")
        return p.rsplit("/", 1)[-1] if p else self.raw.strip()

    def line(self):
        head = "SCENERY_PACK " if self.enabled else "SCENERY_PACK_DISABLED "
        return head + self.path

    def __repr__(self):
        return f"<{self.kind} {self.name}{'' if self.enabled else ' [off]'}>"


# ==========================================================================
# Reading
# ==========================================================================
def parse(text):
    """scenery_packs.ini -> entries, plus whatever header line it had."""
    out, header = [], ""
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if not s:
            continue
        m = DISABLED.match(line)
        if m:
            out.append(Entry(line, m.group(1), False, order=i))
            continue
        m = PACK.match(line)
        if m:
            out.append(Entry(line, m.group(1), True, order=i))
            continue
        if not out and not header:
            header = s                 # the "I" / "1000 Version" / "SCENERY" preamble
    return out, header


def folder_for(entry, custom_scenery=None):
    """Where this entry's folder actually is on disk, or None.

    Most lines are relative ("Custom Scenery/Whatever/"), but a pack can live
    anywhere and be listed by absolute path - a streaming package like XPME writes
    one of those, pointing at its own folder on another drive. Resolving an absolute
    path against Custom Scenery is how you come to tell someone their scenery has
    vanished when it is sitting there perfectly well two drives over, and then offer
    to helpfully delete the line.
    """
    p = (entry.path or "").strip().rstrip("/").rstrip("\\")
    if not p:
        return None
    windows_abs = len(p) > 2 and p[1] == ":" and p[2] in "\\/"
    unc = p.startswith("\\\\")
    if windows_abs or unc or p.startswith("/"):
        return Path(p.replace("\\", "/"))
    if custom_scenery:
        return Path(custom_scenery) / entry.name
    return None


def classify(entry, custom_scenery=None):
    """What kind of pack this is. The folder itself is the best evidence."""
    p = entry.path.strip()
    if "*GLOBAL_AIRPORTS*" in p.upper():
        entry.kind = "global_airports"
        return entry
    if p.upper().startswith("*") or "GLOBAL SCENERY" in p.upper().replace("_", " "):
        entry.kind = "global"
        return entry
    folder = None
    if custom_scenery:
        folder = folder_for(entry, custom_scenery)
        if folder is None or not folder.is_dir():
            folder = None
            entry.note = "this folder isn't there any more"
            entry.kind = "gone"
            entry.family = None
            return entry
    kind = None
    if folder:
        kind = _from_folder(folder)
    if kind in (None, "unknown"):
        for name, rx in HINTS:
            if rx.search(entry.name):
                kind = name
                break
    entry.kind = kind or "unknown"
    entry.family = _family(entry.name)
    return entry


def _from_folder(folder: Path):
    """Look inside: an apt.dat means airports, a library.txt means a library."""
    end = folder / "Earth nav data"
    if (folder / "library.txt").exists():
        return "library"
    if (end / "apt.dat").exists():
        n = sum(1 for _ in end.rglob("*.dsf")) if end.is_dir() else 0
        return "airport" if n <= 2 else None
    if (folder / "textures").is_dir() or (folder / "terrain").is_dir():
        return "ortho"
    return None


def _family(name):
    for label, rx in FAMILY:
        m = rx.match(name)
        if m:
            return (label + ":" + m.group(1).strip(" -_").lower(), int(m.group(2)))
    return None


def read(path, custom_scenery=None):
    """Read and classify a scenery_packs.ini. (entries, header)"""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    entries, header = parse(text)
    cs = custom_scenery or Path(path).parent
    for e in entries:
        classify(e, cs)
    return entries, header


# ==========================================================================
# Sorting
# ==========================================================================
def _key(e):
    """Rank first; inside a family, the package's own numbering; then the old order."""
    fam, num = (e.family or ("", 0))
    return (RANK.get(e.kind, 45), fam, num, e.order)


def sort_entries(entries):
    """The order the file should be in. Stable, so anything equal keeps its place."""
    return sorted(entries, key=_key)


def dedupe(entries):
    """Drop repeated listings of the same folder, keeping the first.

    X-Plane reads top-down and acts on the first line it finds, so the first one
    is the one that has been deciding what you see - keeping it changes nothing
    about how the sim behaves, it just stops the file lying to you.
    """
    seen, out, dropped = set(), [], []
    for e in entries:
        k = e.name.lower()
        if k in seen:
            dropped.append(e)
            continue
        seen.add(k)
        out.append(e)
    return out, dropped


def changed(old, new):
    """The packs that actually move, as (name, from, to)."""
    where = {id(e): i for i, e in enumerate(new)}
    out = []
    for i, e in enumerate(old):
        j = where[id(e)]
        if i != j:
            out.append((e.name, i + 1, j + 1))
    return out


# ==========================================================================
# What's wrong with it
# ==========================================================================
def problems(entries, custom_scenery=None, extra_folders=None):
    """Everything worth telling someone about, worst first."""
    out = []
    order = sort_entries(entries)
    moved = changed(entries, order)
    if moved:
        out.append(("order", f"{len(moved)} of {len(entries)} packs are in the wrong place.",
                    "X-Plane reads this file top-down and the first pack that covers a tile wins, "
                    "so the order decides what you actually see."))

    # the classic one: ground above the things that stand on it
    ranks = [(i, e) for i, e in enumerate(entries) if e.enabled]
    first_ground = next((i for i, e in ranks if e.kind in ("ortho", "mesh")), None)
    late_overlay = [e.name for i, e in ranks if e.kind == "overlay" and first_ground is not None
                    and i > first_ground]
    if late_overlay:
        out.append(("buried", f"{len(late_overlay)} overlay pack(s) sit below photo or mesh scenery.",
                    "Overlays are the buildings, roads and forests. Below the ground layer they are "
                    "invisible: " + ", ".join(late_overlay[:4])
                    + ("..." if len(late_overlay) > 4 else "") + "."))
    late_airport = [e.name for i, e in ranks if e.kind == "airport" and first_ground is not None
                    and i > first_ground]
    if late_airport:
        out.append(("airports", f"{len(late_airport)} custom airport(s) sit below ground scenery.",
                    "Your custom airport loses to the ground underneath it: "
                    + ", ".join(late_airport[:4]) + ("..." if len(late_airport) > 4 else "") + "."))

    # families split up
    fams = {}
    for i, e in enumerate(entries):
        if e.family:
            fams.setdefault(e.family[0], []).append((i, e.family[1]))
    for fam, items in fams.items():
        rows = [i for i, _n in items]
        if rows and max(rows) - min(rows) + 1 != len(rows):
            out.append(("split", f"{fam.split(':', 1)[-1] or fam} is split up in the list.",
                        "A package that numbers its own folders wants them together and in its own "
                        "order. Other packs have got in between."))
        nums = [n for _i, n in sorted(items)]
        if nums != sorted(nums):
            out.append(("scrambled", f"{fam.split(':', 1)[-1] or fam} is in the wrong internal order.",
                        "Its folders are numbered for a reason - 1 before 2 before 3."))

    gone = [e.name for e in entries if e.note]
    if gone:
        out.append(("missing", f"{len(gone)} pack(s) in the list aren't on disk any more.",
                    "Harmless, but they're clutter: " + ", ".join(gone[:5])
                    + ("..." if len(gone) > 5 else "") + "."))

    if extra_folders:
        out.append(("new", f"{len(extra_folders)} folder(s) in Custom Scenery aren't in the list.",
                    "X-Plane adds them at the top next time it starts, which is rarely where they "
                    "belong: " + ", ".join(sorted(extra_folders)[:5])
                    + ("..." if len(extra_folders) > 5 else "") + "."))

    seen, dupes = set(), []
    for e in entries:
        k = e.name.lower()
        if k in seen:
            dupes.append(e.name)
        seen.add(k)
    if dupes:
        out.append(("dupes", f"{len(dupes)} pack(s) are listed twice.",
                    "Duplicates: " + ", ".join(dupes[:5]) + "."))

    hollow = unmounted(entries, custom_scenery)
    if hollow:
        out.append(("hollow", f"{len(hollow)} pack(s) have scenery tiles but no terrain to draw "
                              f"them with.",
                    "X-Plane will cancel every tile in them and fall back to default ground: "
                    + ", ".join(hollow[:4]) + ("..." if len(hollow) > 4 else "")
                    + ". Either the imagery half never finished extracting, or it's a streaming "
                      "package like XPME that creates its terrain folder only while it is "
                      "running - in which case start it before X-Plane and check the folder "
                      "appears."))
    return out


def unmounted(entries, custom_scenery=None):
    """Packs with DSF tiles and nothing to texture them with.

    A folder with Earth nav data full of .dsf files but no terrain, no textures, no
    apt.dat and no library.txt is a pack X-Plane cannot draw: it looks for
    'terrain/....ter', doesn't find it, and cancels the tile. That is what a
    half-extracted ortho set looks like, and it is also exactly what a streaming
    package looks like when the thing that streams it isn't running.
    """
    out = []
    if not custom_scenery:
        return out
    for e in entries:
        if not e.enabled or e.kind in ("global", "global_airports", "gone"):
            continue
        folder = folder_for(e, custom_scenery)
        if folder is None or not folder.is_dir():
            continue
        end = folder / "Earth nav data"
        try:
            if not end.is_dir():
                continue
            if (folder / "library.txt").exists() or (end / "apt.dat").exists():
                continue
            if (folder / "terrain").is_dir() or (folder / "textures").is_dir():
                continue
            if not any(True for _ in itertools.islice(end.rglob("*.dsf"), 1)):
                continue
        except OSError:
            continue
        out.append(e.name)
    return out


def missing_folders(entries, custom_scenery):
    """Folders sitting in Custom Scenery that the file doesn't mention."""
    cs = Path(custom_scenery)
    if not cs.is_dir():
        return []
    listed = {e.name.lower() for e in entries}
    out = []
    for p in sorted(cs.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        if p.name.lower() in listed:
            continue
        if (p / "Earth nav data").is_dir() or (p / "library.txt").exists():
            out.append(p.name)
    return out


def add_missing(entries, names, custom_scenery=None):
    """Put folders the file never mentioned into it, classified like the rest."""
    n = max((e.order for e in entries), default=0)
    for i, name in enumerate(sorted(names)):
        e = Entry("", f"Custom Scenery/{name}/", True, order=n + 1 + i)
        classify(e, custom_scenery)
        e.note = "added - it was in Custom Scenery but not in the list"
        entries.append(e)
    return entries


# ==========================================================================
# Writing
# ==========================================================================
def render(entries, header="I"):
    """The file X-Plane expects: its three-line preamble, then one line per pack."""
    head = (header or "I").strip() or "I"
    lines = [head, "1000 Version", "SCENERY", ""]
    lines += [e.line() for e in entries]
    return "\n".join(lines) + "\n"


def backup_name(path):
    return Path(path).with_name(Path(path).name + time.strftime(".%Y-%m-%d_%H%M%S.backup"))


def write(path, entries, header="I"):
    """Write the new order, keeping a copy of what was there. Returns the backup's path.

    Written to a temporary file beside it and then moved into place, because a
    half-written scenery_packs.ini is the worst thing this app could leave behind:
    X-Plane would start with most of the scenery missing and nothing to say why.
    os.replace is atomic on Windows and on POSIX, so the file ends up as either the
    old one or the new one and never something in between. The backup is written
    and flushed to disk before anything is touched.
    """
    path = Path(path)
    body = render(entries, header)
    backup = None
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        backup = backup_name(path)
        with open(backup, "w", encoding="utf-8") as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise
    return backup


def writable(path):
    """(ok, why) - whether this file could actually be rewritten, checked before trying.

    Finding out halfway through that the folder is read-only is how you end up with
    a backup and no scenery_packs.ini.
    """
    path = Path(path)
    folder = path.parent
    if not folder.is_dir():
        return False, f"There's no folder at {folder}."
    if not os.access(folder, os.W_OK):
        return False, (f"Windows won't let this app write into {folder}. If X-Plane is "
                       f"installed under Program Files, that folder needs administrator "
                       f"rights - or move the install somewhere else.")
    if path.exists() and not os.access(path, os.W_OK):
        return False, (f"{path.name} is read-only. Clear the read-only tick in its "
                       f"Properties, or close whatever has it open.")
    return True, ""


# ==========================================================================
# Words
# ==========================================================================
def summary(entries):
    counts = {}
    for e in entries:
        counts[e.kind] = counts.get(e.kind, 0) + 1
    bits = []
    for k, n in sorted(counts.items(), key=lambda kv: RANK.get(kv[0], 45)):
        one, many = PLURAL.get(k, (WHAT.get(k, k), WHAT.get(k, k) + "s"))
        bits.append(f"{n} {one if n == 1 else many}")
    off = sum(1 for e in entries if not e.enabled)
    line = f"{len(entries)} packs: " + ", ".join(bits)
    return line + (f" ({off} switched off)" if off else "")


def listing(entries, mark=None):
    """The list as it would be written, one line each."""
    out = []
    for i, e in enumerate(entries, 1):
        tag = WHAT.get(e.kind, e.kind)
        flag = "" if e.enabled else "  [off]"
        move = ""
        if mark and e.name in mark:
            move = f"   <- was {mark[e.name]}"
        out.append(f"{i:3d}. {e.name[:52]:<54} {tag}{flag}{move}")
    return "\n".join(out)


def report(entries, probs, moved):
    L = [summary(entries), ""]
    if not probs:
        L.append("Nothing wrong with it. The order is already what X-Plane wants.")
        return "\n".join(L)
    for _key_, what, why in probs:
        L.append("- " + what)
        L.append("  " + why)
    if moved:
        L += ["", f"{len(moved)} pack(s) would move. The biggest jumps:"]
        for name, a, b in sorted(moved, key=lambda m: -abs(m[1] - m[2]))[:8]:
            L.append(f"    {name[:46]:<48} {a} -> {b}")
    return "\n".join(L)
