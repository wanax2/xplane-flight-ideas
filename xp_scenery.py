"""
xp_scenery.py - what scenery you actually have installed.

X-Plane's Custom Scenery folder tells us a lot: which airports come from an add-on
rather than the default global set, and which one-degree tiles have photo (ortho)
or custom mesh scenery. The app uses that to send you where your sim looks good,
and to point out the packs you have never flown into.

Everything here is local - no internet, no downloads.
"""
from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path

TILE = re.compile(r"([+-]\d{2})([+-]\d{3})\.dsf$", re.I)
ORTHO_HINT = re.compile(r"ortho|zortho|photo|simheaven|aerofly|xp12_ortho", re.I)
MESH_HINT = re.compile(r"mesh|hd_scenery|uhd|terrain|alpilotx|forkboy|simheaven", re.I)
LIB_HINT = re.compile(r"library|lib$|opensceneryx|r2_library|handyobjects|ruscenery|world models", re.I)


def tile_key(lat, lon):
    import math
    return f"{int(math.floor(lat)):+03d}{int(math.floor(lon)):+04d}"


class Scenery:
    """Packs in Custom Scenery, with the airports and map tiles each one covers."""

    def __init__(self, cache_dir: Path):
        self.file = Path(cache_dir) / "scenery.json.gz"
        self.packs = {}        # name -> {"kind", "tiles": n, "airports": [ids], "disabled": bool}
        self.tiles = {}        # "+39-106" -> pack name (ortho/mesh only)
        self.scanned = 0.0
        self.root = ""
        try:
            with gzip.open(self.file, "rt", encoding="utf-8") as f:
                d = json.load(f)
            self.packs, self.tiles = d["packs"], d["tiles"]
            self.scanned, self.root = d.get("t", 0), d.get("root", "")
        except Exception:
            pass

    # ------------------------------------------------------------------ scan
    def scan(self, root, airports=None, log=print, max_tiles_per_pack=4000):
        root = Path(root)
        cs = root / "Custom Scenery"
        packs, tiles = {}, {}
        disabled = self._disabled(cs)
        if cs.is_dir():
            names = sorted(p for p in cs.iterdir() if p.is_dir())
            for i, p in enumerate(names):
                if i % 25 == 0:
                    log(f"  scenery: {i}/{len(names)} packs...")
                info = self._one(p, max_tiles_per_pack)
                if not info:
                    continue
                info["disabled"] = p.name in disabled
                packs[p.name] = info
                if info["kind"] in ("ortho", "mesh") and not info["disabled"]:
                    for t in info.pop("tile_keys", ()):
                        tiles.setdefault(t, p.name)
                info.pop("tile_keys", None)
        # which airports each airport pack gave us (from the airports the app already loaded)
        if airports:
            for a in airports:
                pk = a.get("pack")
                if pk and pk in packs:
                    packs[pk].setdefault("airports", []).append(a["id"])
        self.packs, self.tiles = packs, tiles
        self.scanned, self.root = time.time(), str(root)
        try:
            with gzip.open(self.file, "wt", encoding="utf-8") as f:
                json.dump({"packs": packs, "tiles": tiles, "t": self.scanned, "root": self.root}, f)
        except OSError:
            pass
        log(f"  scenery: {len(packs)} packs, {len(tiles):,} tiles with custom mesh or photo scenery.")
        return self

    def _disabled(self, cs: Path):
        out = set()
        ini = cs / "scenery_packs.ini"
        try:
            for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().upper().startswith("SCENERY_PACK_DISABLED"):
                    out.add(Path(line.split(None, 1)[1].strip().rstrip("/\\").replace("\\", "/")).name)
        except OSError:
            pass
        return out

    def _one(self, p: Path, cap):
        end = p / "Earth nav data"
        has_apt = (end / "apt.dat").exists()
        keys, n = [], 0
        if end.is_dir():
            for f in end.rglob("*.dsf"):
                n += 1
                m = TILE.search(f.name)
                if m and len(keys) < cap:
                    keys.append(m.group(1) + m.group(2))
                if n >= cap:
                    break
        name = p.name
        if not has_apt and not n:
            if LIB_HINT.search(name) or (p / "library.txt").exists():
                return {"kind": "library", "tiles": 0, "airports": []}
            return None
        if has_apt and n <= 2:
            kind = "airport"
        elif ORTHO_HINT.search(name):
            kind = "ortho"
        elif MESH_HINT.search(name) or n > 40:
            kind = "mesh"
        elif has_apt:
            kind = "airport"
        else:
            kind = "mesh"
        return {"kind": kind, "tiles": n, "airports": [], "tile_keys": keys}

    # ------------------------------------------------------------- questions
    def age_days(self):
        return (time.time() - self.scanned) / 86400 if self.scanned else None

    def has_ortho(self, a):
        return tile_key(a["lat"], a["lon"]) in self.tiles

    def pack_of(self, a):
        return a.get("pack")

    def quality(self, a):
        """0 = default scenery, 1 = custom mesh/photo, 2 = add-on airport, 3 = both."""
        q = 0
        if self.tiles and self.has_ortho(a):
            q += 1
        if a.get("pack"):
            q += 2
        return q

    def describe(self, a):
        bits = []
        if a.get("pack"):
            bits.append(f"add-on airport: {a['pack']}")
        if self.tiles and self.has_ortho(a):
            bits.append(f"custom mesh/photo scenery ({self.tiles[tile_key(a['lat'], a['lon'])]})")
        return " + ".join(bits)

    def airport_packs(self):
        return {k: v for k, v in self.packs.items() if v["kind"] == "airport" and not v.get("disabled")}

    def never_flown(self, visited_ids):
        """Airport packs none of whose airports appear in the logbook."""
        seen = {str(x).upper() for x in visited_ids}
        out = []
        for name, info in sorted(self.airport_packs().items()):
            ids = [i for i in info.get("airports", [])]
            if ids and not (seen & {i.upper() for i in ids}):
                out.append((name, ids))
        return out

    def summary_line(self):
        if not self.packs:
            return "Not scanned yet - the app will use every airport equally."
        ap = len(self.airport_packs())
        ort = sum(1 for v in self.packs.values() if v["kind"] == "ortho" and not v.get("disabled"))
        mesh = sum(1 for v in self.packs.values() if v["kind"] == "mesh" and not v.get("disabled"))
        off = sum(1 for v in self.packs.values() if v.get("disabled"))
        bits = [f"{ap} add-on airport packs", f"{len(self.tiles):,} tiles with custom mesh or photo scenery"]
        if ort or mesh:
            bits.append(f"{ort} ortho, {mesh} mesh packs")
        if off:
            bits.append(f"{off} disabled")
        return " - ".join(bits)
