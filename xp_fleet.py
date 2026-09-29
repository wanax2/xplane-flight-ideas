"""
xp_fleet.py - your aeroplanes stay where you left them.

Every flight in this app has been a fresh start: pick an aircraft, pick an
airport, go. Which is fine, but it means nothing accumulates. Fly from Denver to
Aspen and the aeroplane is back in Denver next time, with full tanks, as though
the flight never happened.

This keeps a short record per aircraft - where it is, how many hours it has, how
much fuel is left, when you last flew it - and updates it from the logbook after
every scored flight. Switch "continue from where I left it" on, and the next
flight has to start where the last one ended.

It is a bookkeeping file, not a simulation. Maintenance, wear and money are not
modelled and deliberately so: this exists to make a string of flights feel like
one continuing thing, not to give you a second job.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class Fleet:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.planes = {}
        try:
            self.planes = json.loads(self.path.read_text())
        except Exception:
            self.planes = {}

    def save(self):
        try:
            self.path.write_text(json.dumps(self.planes, indent=1))
        except OSError:
            pass

    # ---- reading ---------------------------------------------------------
    def get(self, acf):
        """The state of one aeroplane, or None if it has never been flown."""
        return self.planes.get(self._key(acf))

    def where(self, acf):
        p = self.get(acf)
        return (p or {}).get("at")

    def all(self):
        """Every aeroplane, most recently flown first."""
        return sorted(self.planes.items(), key=lambda kv: -(kv[1].get("last") or 0))

    @staticmethod
    def _key(acf):
        return str(acf or "").replace("\\", "/").strip()

    # ---- writing ---------------------------------------------------------
    def note_flight(self, acf, name, entry):
        """Update from a logbook entry once a flight is graded."""
        k = self._key(acf)
        if not k:
            return None
        landed = [a for a in (entry.get("flown_to") or ()) if a]
        planned = [a for a in (entry.get("route") or ()) if a]
        at = landed[-1] if landed else (planned[-1] if planned else None)
        p = self.planes.setdefault(k, {"name": name, "hours": 0.0, "landings": 0, "flights": 0})
        p["name"] = name or p.get("name") or k
        p["hours"] = round(p.get("hours", 0.0) + (entry.get("minutes") or 0) / 60.0, 2)
        p["landings"] = p.get("landings", 0) + len(entry.get("landings") or ())
        p["flights"] = p.get("flights", 0) + 1
        p["last"] = entry.get("time") or time.time()
        if at:
            p["at"] = at
        if entry.get("fuel_left") is not None:
            p["fuel_frac"] = max(0.0, min(1.0, float(entry["fuel_left"])))
        self.save()
        return p

    def set_at(self, acf, ident):
        k = self._key(acf)
        if not k:
            return
        p = self.planes.setdefault(k, {"hours": 0.0, "landings": 0, "flights": 0})
        p["at"] = ident
        p["last"] = time.time()
        self.save()

    def forget(self, acf):
        self.planes.pop(self._key(acf), None)
        self.save()

    # ---- words -----------------------------------------------------------
    def line(self, acf):
        """One line about where this aeroplane is."""
        p = self.get(acf)
        if not p:
            return "Never flown - it starts wherever you send it."
        bits = []
        if p.get("at"):
            bits.append(f"at {p['at']}")
        if p.get("hours"):
            bits.append(f"{p['hours']:.1f} h")
        if p.get("landings"):
            bits.append(f"{p['landings']} landings")
        if p.get("last"):
            days = (time.time() - p["last"]) / 86400.0
            bits.append("flown today" if days < 1 else f"last flown {days:.0f} days ago")
        return " · ".join(bits) or "No history yet."
