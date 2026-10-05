"""
xp_charts.py - where to find the real plates, free, for one airport.

The app works out its own approach and departure numbers from your scenery, and
those are the usual figures for that kind of procedure - not the ones off the
chart. When you want the chart itself, this is the shortest way to it.

Everything here is a free, no-account source. Nothing is downloaded: these are
links you open in your own browser. The US has the best of it, because the FAA
publishes its terminal procedures as public documents; elsewhere it depends on
what the national AIP puts in front of a login, so the worldwide links are
airport pages that gather what they can rather than the plates themselves.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# The sources
# --------------------------------------------------------------------------
# The FAA's IFP Information Gateway indexes every US instrument procedure -
# approaches, departures (DP/SID) and arrivals (STAR) - by the airport's NASR
# id, which is the identifier without its leading K.
FAA_IFP = ("https://www.faa.gov/AIR_TRAFFIC/FLIGHT_INFO/AERONAV/PROCEDURES/"
           "application/index.cfm?event=procedure.results&tab=charts&nasrId={nasr}")
FAA_DTPP = ("https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/"
            "dtpp/search/?cycle=current&ident={icao}")
AIRNAV = "https://www.airnav.com/airport/{icao}"
SKYVECTOR = "https://skyvector.com/airport/{icao}"
OPENNAV = "https://opennav.com/airport/{icao}"
OPENAIP = "https://www.openaip.net/?search={icao}"


def nasr_id(ident):
    """The FAA's own identifier: KDEN is DEN to them, but 06C is still 06C."""
    ident = (ident or "").strip().upper()
    if len(ident) == 4 and ident.startswith("K"):
        return ident[1:]
    return ident


def is_us(a, core=None):
    if core is not None:
        try:
            return bool(core.is_us(a))
        except Exception:
            pass
    iso = (a.get("iso") or "").upper()
    if iso:
        return iso == "US"
    return str(a.get("id", "")).upper().startswith("K")


def links(a, core=None, kind="all"):
    """[(label, url, note)] for one airport.

    kind is "approach", "departure" or "all" - it only changes the wording, since
    every source listed carries both; there is no free page that serves up one
    plate and not the other.
    """
    ident = str(a.get("id", "")).strip().upper()
    if not ident:
        return []
    what = {"approach": "approach plates", "departure": "departure procedures"}.get(
        kind, "approach plates, departures and arrivals")
    out = []
    if is_us(a, core):
        out.append(("FAA procedures - " + what,
                    FAA_IFP.format(nasr=nasr_id(ident)),
                    "official and current, straight from the FAA"))
        out.append(("FAA digital terminal procedures",
                    FAA_DTPP.format(icao=ident),
                    "the whole booklet for this airport, as published PDFs"))
        out.append(("AirNav airport page",
                    AIRNAV.format(icao=ident),
                    "runways, frequencies, fuel, and the procedure list"))
    out.append(("SkyVector", SKYVECTOR.format(icao=ident),
                "the sectional, and the plates where it has them"))
    out.append(("OpenNav", OPENNAV.format(icao=ident),
                "worldwide procedures, free"))
    out.append(("OpenAIP", OPENAIP.format(icao=ident),
                "worldwide airport data, free and crowd-checked"))
    if a.get("wiki"):
        out.append(("Wikipedia", a["wiki"], "what the place is"))
    return out


def best_link(a, core=None, kind="all"):
    """One link, when there is only room for one."""
    got = links(a, core, kind)
    return got[0] if got else None
