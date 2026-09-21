"""
xp_scenic.py - "anywhere in the world" scenic flight generator.

Two sources:
  * FAMOUS  - a hand-picked list of well-known scenic airports and routes on every continent
  * GEMS    - "hidden gems" found automatically in YOUR X-Plane scenery: airports
              surrounded by much higher terrain (judged from nearby airport
              elevations), high-altitude strips, islands, glaciers, lakes, fjords,
              canyons... (from the airport data and names)

Every pick is checked against your scenery and aircraft. If your plane can't use
the famous strip itself, the flight overflies it and lands at the nearest
airport it can use.
"""
from __future__ import annotations

import math
import re

from xp_wx import CONTINENTS, in_area

TAGS = {
    "mountains": "Mountains",
    "islands":   "Islands",
    "coast":     "Coast & beaches",
    "ice":       "Glaciers & Arctic",
    "desert":    "Canyons & desert",
    "volcano":   "Volcanoes",
    "water":     "Lakes, rivers & fjords",
    "landmark":  "Landmarks & cities",
    "jungle":    "Jungle & wetlands",
    "bush":      "Bush & backcountry",
}

# (airport idents, title, tags, what to look at)
FAMOUS = [
    # ---------------- North America & Caribbean ----------------
    (["KLXV"], "Leadville", "mountains", "Highest public airport in North America (~9,900 ft) among Colorado's fourteeners."),
    (["KTEX"], "Telluride", "mountains", "Mesa-top runway at ~9,000 ft in the San Juan Mountains, drop-offs at both ends."),
    (["KASE"], "Aspen", "mountains", "Tight valley arrival past the Maroon Bells area."),
    (["KSEZ"], "Sedona", "desert", "Runway on a mesa surrounded by red rock."),
    (["KGCN", "KPGA"], "Grand Canyon to Lake Powell", "desert water", "Follow the SFRA corridors over the canyon, then Lake Powell and Horseshoe Bend."),
    (["KPGA", "KBCE", "KCNY"], "Utah canyon country", "desert", "Lake Powell, Bryce's hoodoos and Canyonlands in one day."),
    (["KBVU"], "Hoover Dam", "desert landmark water", "Boulder City - Lake Mead and Hoover Dam right next door."),
    (["KBIH", "L06"], "Into Death Valley", "desert mountains", "Cross the Inyo Mountains and descend below sea level."),
    (["KBIH", "KMMH", "KTRK"], "Eastern Sierra crest", "mountains water", "US-395 north with 14,000 ft peaks off the left wing; finish at Lake Tahoe."),
    (["KAVX"], "Catalina Island", "islands coast", "'Airport in the Sky' - a hilltop runway with a hump, 26 nm off LA."),
    (["KSBA", "KSBP", "KMRY", "KHAF"], "California coast", "coast", "Coast-hug from Santa Barbara past Big Sur to Half Moon Bay."),
    (["KCDW", "KFRG"], "Hudson River Corridor", "landmark water", "Down the Hudson below 1,300 ft past Midtown and the Statue of Liberty."),
    (["KBVS"], "Skagit Valley", "water mountains", "Puget Sound, the San Juans and Mt Baker on the horizon."),
    (["KBLI", "KORS", "KFHR"], "San Juan Islands", "islands water", "Island hopping in Puget Sound - watch for orcas."),
    (["KJAC", "KWYS"], "Tetons to Yellowstone", "mountains volcano", "Up the Teton range, then over Yellowstone Lake and the caldera."),
    (["KMYL", "3U2", "U60"], "Idaho backcountry", "mountains water", "River canyons and dirt strips in the Frank Church wilderness."),
    (["KHYA", "KACK", "KMVY", "KBID"], "Cape Cod island hop", "islands coast", "Three islands, lots of water, maybe fog."),
    (["KMQI", "KFFA", "W95"], "Outer Banks", "coast landmark", "Beach-hug to Ocracoke, past the Wright Brothers memorial."),
    (["KTMB", "KMTH", "KEYW"], "Florida Keys", "islands coast", "Follow the Overseas Highway to Key West."),
    (["KPLN", "KMCD"], "Mackinac", "islands water landmark", "Cross the Mackinac Bridge to the car-free island."),
    (["PAMR", "PAWD"], "Turnagain Arm", "mountains ice water", "South from Anchorage through the pass to Seward."),
    (["PAMR", "PATK"], "Toward Denali", "mountains ice", "Talkeetna - the base for Denali glacier landings."),
    (["PAJN", "PAGS"], "Juneau to Glacier Bay", "ice mountains water", "Mendenhall Glacier, then the tidewater glaciers of Glacier Bay."),
    (["PAKT"], "Ketchikan", "water coast", "Misty Fjords and floatplanes everywhere."),
    (["PAVD"], "Valdez", "mountains ice water", "Prince William Sound, Columbia Glacier, and famous STOL flying."),
    (["PALH"], "Lake Hood", "water", "The world's busiest seaplane base."),
    (["CYBA"], "Banff", "mountains", "A small strip in the heart of the Canadian Rockies."),
    (["CYYJ"], "Victoria", "coast islands", "Gulf Islands and the Olympic Mountains across the strait."),
    (["PHKO", "PHTO"], "Big Island volcanoes", "volcano islands", "Around Mauna Loa and Kilauea - lava fields and waterfalls."),
    (["PHLI"], "Kauai", "islands coast mountains", "Loop the Na Pali coast and Waimea Canyon."),
    (["PHOG", "PHNY", "PHMK", "PHLU"], "Maui County hop", "islands coast", "Maui, Lanai, Molokai and the Kalaupapa sea cliffs."),
    (["TNCM", "TFFJ", "TNCS"], "Caribbean island hop", "islands coast", "Maho Beach, St Barth's hilltop dive and Saba's cliffs."),
    (["MYEF"], "Exumas", "islands coast", "Turquoise shallows of the Bahamas' Exuma Cays."),
    (["MMSD"], "Los Cabos", "coast desert", "Land's End arch and the Sea of Cortez."),
    # ---------------- South America ----------------
    (["SAWH"], "Ushuaia", "mountains ice coast", "The end of the world - Beagle Channel and the Martial glacier."),
    (["SAWC"], "El Calafate", "ice mountains water", "Perito Moreno glacier and Lago Argentino."),
    (["SAZS"], "Bariloche", "mountains water", "Andean lakes district."),
    (["SLLP"], "La Paz / El Alto", "mountains", "One of the highest airports in the world (~13,300 ft) - watch your performance."),
    (["SPZO"], "Cusco", "mountains landmark", "Sacred Valley toward Machu Picchu."),
    (["SEGS"], "Galapagos", "islands volcano", "Baltra - volcanic islands in the Pacific."),
    (["SCIP"], "Easter Island", "islands landmark", "Rapa Nui and the moai - the most remote airport around."),
    (["SBRJ"], "Rio de Janeiro", "landmark coast mountains", "Santos Dumont, beside Sugarloaf; Christ the Redeemer above."),
    # ---------------- Europe ----------------
    (["LFLJ"], "Courchevel altiport", "mountains", "A steep, very short uphill runway in the French Alps."),
    (["LSZB", "LSZS", "LSGS"], "Swiss Alps", "mountains ice", "Bern to Samedan (Europe's highest airport) to Sion - glaciers and passes."),
    (["LSZA"], "Lugano", "mountains water", "A lake in a deep valley - a steep approach."),
    (["LOWI"], "Innsbruck", "mountains", "A valley approach between Alpine peaks."),
    (["LIPB"], "Bolzano", "mountains", "The Dolomites."),
    (["LXGB"], "Gibraltar", "landmark coast", "The runway crosses the main road; the Rock beside you."),
    (["LPMA"], "Madeira", "islands coast", "A runway on pillars over the sea; gusty cliffs."),
    (["GCLA", "GCHI"], "Canary Islands", "islands volcano", "La Palma's volcanoes to tiny El Hierro."),
    (["LGSR", "LGMK"], "Greek islands", "islands coast", "Santorini's caldera to Mykonos."),
    (["LGSK"], "Skiathos", "islands coast", "A short runway right on the water."),
    (["LDDU", "LYTV"], "Adriatic coast", "coast mountains", "Dubrovnik's walls to the Bay of Kotor."),
    (["LFKC"], "Calvi, Corsica", "islands mountains coast", "A mountain-ringed approach on the 'island of beauty'."),
    (["EGPO", "EGPR"], "Outer Hebrides", "islands coast", "Stornoway to the beach runway at Barra (between tides)."),
    (["EGEO", "EGPI"], "Scottish west coast", "islands coast", "Oban to Islay over the Inner Hebrides."),
    (["EIDL"], "Donegal", "coast", "Often voted the world's most scenic approach."),
    (["EGHE"], "Isles of Scilly", "islands coast", "Tiny islands off Land's End."),
    (["EGJA", "EGJB", "EGJJ"], "Channel Islands", "islands coast", "Alderney, Guernsey and Jersey."),
    (["ENBR", "ENSG"], "Norwegian fjords", "water mountains", "Bergen to Sogndal along the Sognefjord."),
    (["ENBO", "ENLK"], "Lofoten", "islands mountains coast", "Bodo to the jagged Lofoten wall."),
    (["ENTC"], "Tromso", "ice water mountains", "Arctic fjords - try it at night for the northern lights."),
    (["ENSB"], "Svalbard", "ice", "The far north, halfway to the pole."),
    (["EKVG"], "Faroe Islands", "islands coast", "A fjord approach in wild weather."),
    (["BIRK", "BIVM"], "Iceland south coast", "volcano ice islands", "Reykjavik past Eyjafjallajokull to Vestmannaeyjar."),
    (["BIAR"], "Akureyri", "mountains water ice", "A long fjord approach in north Iceland."),
    # ---------------- Africa ----------------
    (["FACT"], "Cape Town", "landmark coast mountains", "Table Mountain and the Cape Peninsula."),
    (["FAPG"], "Plettenberg Bay", "coast", "South Africa's Garden Route."),
    (["FVFA"], "Victoria Falls", "water landmark", "The smoke that thunders."),
    (["FBMN"], "Okavango Delta", "water", "Maun - wildlife and waterways from above."),
    (["HTKJ"], "Kilimanjaro", "mountains volcano", "Africa's highest mountain."),
    (["HKNW"], "Nairobi Wilson", "landmark", "Game parks on the city's doorstep."),
    (["FYWB"], "Namib dunes", "desert coast", "Walvis Bay - the dunes meet the Atlantic."),
    (["GMMX"], "Marrakech", "mountains desert", "The High Atlas behind the city."),
    (["HELX"], "Luxor", "desert landmark water", "The Nile and the Valley of the Kings."),
    (["FMEE"], "Reunion", "islands volcano mountains", "Piton de la Fournaise and deep cirques."),
    (["FIMP"], "Mauritius", "islands coast", "Lagoons and the underwater waterfall illusion."),
    (["FSIA"], "Seychelles", "islands coast", "Granite islands in the Indian Ocean."),
    # ---------------- Asia & Middle East ----------------
    (["VNKT", "VNLK"], "Himalaya", "mountains", "Kathmandu to Lukla (~9,300 ft), gateway to Everest."),
    (["VQPR"], "Paro, Bhutan", "mountains", "A winding Himalayan valley approach."),
    (["VILH"], "Leh", "mountains", "Ladakh at ~10,700 ft in the Indus valley."),
    (["OPGT"], "Gilgit", "mountains", "Karakoram - Nanga Parbat and the Hunza valley."),
    (["ZULS"], "Lhasa", "mountains", "The Tibetan plateau."),
    (["RJNS"], "Mt Fuji", "volcano mountains landmark", "Shizuoka - fly around Fuji-san."),
    (["WADD"], "Bali", "islands volcano coast", "Volcanoes, rice terraces and surf."),
    (["VTSM", "VTSP"], "Thai islands", "islands coast", "Koh Samui to Phuket - limestone karsts in Phang Nga Bay."),
    (["RPVP"], "Palawan", "islands coast", "Puerto Princesa - lagoons and karst cliffs."),
    (["WBKK"], "Mt Kinabalu", "mountains coast", "Kota Kinabalu - Borneo's highest peak."),
    (["VRMM"], "Maldives", "islands coast", "Atolls and seaplane docks everywhere."),
    (["OJAQ"], "Aqaba", "desert coast", "The Red Sea and Wadi Rum."),
    (["OMDB"], "Dubai", "landmark desert coast", "Burj Khalifa and the Palm - best at night."),
    # ---------------- Oceania & Pacific ----------------
    (["NZQN", "NZMF"], "Queenstown to Milford Sound", "mountains water ice", "Over the Southern Alps into the fiord."),
    (["NZMC"], "Aoraki / Mt Cook", "mountains ice", "Glaciers and New Zealand's highest peak."),
    (["YBCS", "YBHM"], "Great Barrier Reef", "islands coast", "Cairns down the reef to the Whitsundays."),
    (["YAYE"], "Uluru", "desert landmark", "Ayers Rock and Kata Tjuta at sunset."),
    (["YSSY"], "Sydney Harbour", "landmark coast", "The harbour bridge and opera house (VFR harbour scenic route)."),
    (["YLHI"], "Lord Howe Island", "islands coast mountains", "A tiny lagoon island with sheer peaks."),
    (["YBRM"], "Broome", "coast desert", "Kimberley coast and Cable Beach."),
    (["NTAA", "NTTM", "NTTB"], "Tahiti to Bora Bora", "islands coast", "Tahiti, Moorea and the Bora Bora lagoon."),
    (["NFFN"], "Fiji", "islands coast", "Mamanuca and Yasawa islands."),
    # ---------------- Arctic ----------------
    (["BGSF", "BGJN"], "Greenland", "ice", "Kangerlussuaq's ice cap to Ilulissat's iceberg fjord."),
    (["CYFB"], "Iqaluit", "ice", "Baffin Island's Arctic landscape."),
    (["PABR"], "Utqiagvik", "ice coast", "The northernmost town in the USA."),
    # ---------------- more, everywhere ----------------
    (["KSUN", "KJAC"], "Sawtooths to the Tetons", "mountains", "Idaho's Sawtooth range across to Jackson Hole."),
    (["KCEZ", "KDRO"], "Mesa Verde country", "desert mountains", "Cortez to Durango past the cliff dwellings."),
    (["KRAP"], "Black Hills", "mountains landmark", "Rapid City - Mount Rushmore and the Badlands nearby."),
    (["KSLC", "KPUC"], "Wasatch and the canyons", "mountains desert", "Salt Lake south over the Wasatch Plateau."),
    (["KEKO"], "Ruby Mountains", "mountains", "Elko - Nevada's alpine surprise."),
    (["KSAN", "KAVX"], "San Diego to Catalina", "coast islands", "Out over the Pacific to the island."),
    (["KMSO", "KGPI"], "Glacier National Park", "mountains ice", "Missoula up to Kalispell past the Mission range."),
    (["CYLW", "CYXC"], "Canadian Rockies", "mountains", "Kelowna to Cranbrook over the ranges."),
    (["CYZF"], "Great Slave Lake", "water ice", "Yellowknife - lakes, tundra and the aurora."),
    (["CYQX", "CYYT"], "Newfoundland", "coast", "Gander to St John's, the old transatlantic gateway."),
    (["MMZH", "MMCZ"], "Yucatan coast", "coast islands", "Chichen Itza country out to Cozumel."),
    (["MPTO", "MPMG"], "Panama Canal", "landmark water", "Fly the locks from Tocumen to Albrook."),
    (["SKSM", "SKRH"], "Caribbean Colombia", "coast", "Santa Marta to Riohacha along the Sierra Nevada coast."),
    (["SCRD"], "Robinson Crusoe Island", "islands coast", "A cliff-top strip in the Juan Fernandez islands."),
    (["LEGR", "LEZL"], "Sierra Nevada, Spain", "mountains", "Granada's snowy peaks down to Seville."),
    (["LIRN", "LICC"], "Vesuvius to Etna", "volcano coast", "Naples past Vesuvius, down to Catania under Etna."),
    (["LFMN", "LFKC"], "Riviera to Corsica", "coast islands", "Nice over the Med to Calvi."),
    (["EDMS", "LOWS"], "Bavaria to Salzburg", "mountains water", "Alpine lakes and castles."),
    (["EPKK", "LZTT"], "Tatra mountains", "mountains", "Krakow to the High Tatras."),
    (["LGKR", "LGKF"], "Ionian islands", "islands coast", "Corfu down to Kefalonia."),
    (["LTFE", "LTBS"], "Turquoise coast", "coast islands", "Bodrum to Dalaman along the Lycian coast."),
    (["HSSK", "HEGN"], "Red Sea", "desert coast", "Khartoum to Hurghada over the desert and the sea."),
    (["FQMA", "FMMI"], "Mozambique Channel", "coast islands", "Maputo across to Antananarivo."),
    (["FZAA"], "Congo River", "water", "Kinshasa - the great river from above."),
    (["OERK", "OEJN"], "Arabian crossing", "desert", "Riyadh to Jeddah over the Nejd."),
    (["VABB", "VOGO"], "Konkan coast", "coast", "Mumbai down the west coast to Goa."),
    (["VCBI", "VCCK"], "Sri Lanka", "islands coast", "Colombo to the tea country."),
    (["ZJSY", "VHHH"], "South China Sea", "islands coast", "Sanya across to Hong Kong."),
    (["RJCC", "RJEC"], "Hokkaido", "mountains ice", "Sapporo to Asahikawa, volcanoes and snow."),
    (["YMHB", "YMLT"], "Tasmania", "mountains coast", "Hobart to Launceston over the highlands."),
    (["YPPH", "YPKG"], "Nullarbor edge", "desert coast", "Perth east to Kalgoorlie's goldfields."),
    (["NZNS", "NZHK"], "West Coast glaciers", "ice mountains", "Nelson down to Hokitika past Franz Josef."),
    (["NZKI", "NZQN"], "Southern Alps crossing", "mountains ice", "Kaikoura to Queenstown across the spine."),
    # ---------------- even more ----------------
    (["PAOM", "PAOT"], "Arctic Alaska", "ice coast", "Nome to Kotzebue above the Arctic Circle."),
    (["PASI", "PAJN"], "Inside Passage", "water coast ice", "Sitka to Juneau between the islands."),
    (["CYDA", "CYXY"], "Klondike", "mountains ice", "Dawson City to Whitehorse over the Yukon."),
    (["CYZV", "CYYY"], "St Lawrence", "water coast", "Sept-Iles up the great river."),
    (["KFCA", "KMSO"], "Flathead and the Bitterroots", "mountains water", "Kalispell to Missoula."),
    (["KCDC", "KBCE"], "Zion and Bryce", "desert", "Cedar City past Zion to Bryce Canyon."),
    (["KLAS", "KGCN"], "Vegas to the canyon", "desert landmark", "The Strip, Lake Mead and the Grand Canyon."),
    (["KMRY", "KWVI"], "Monterey Bay", "coast", "Around the bay to Watsonville."),
    (["KEUG", "KOTH"], "Oregon coast", "coast", "Eugene west over the Coast Range to Coos Bay."),
    (["KSEA", "KCLM"], "Olympic Peninsula", "mountains coast", "Seattle to Port Angeles past the Olympics."),
    (["KPSP", "KTRM"], "Coachella and Salton", "desert", "Palm Springs down to the Salton Sea, below sea level."),
    (["MMPR", "MMZO"], "Jalisco coast", "coast", "Puerto Vallarta down the Pacific shore."),
    (["MHRO", "MHLM"], "Bay Islands", "islands coast", "Roatan to San Pedro Sula."),
    (["TJSJ", "TJPS"], "Puerto Rico", "islands coast mountains", "San Juan over El Yunque to Ponce."),
    (["SVMG", "TNCA"], "Southern Caribbean", "islands coast", "Margarita to Aruba."),
    (["SPJC", "SPQU"], "Andes crossing", "mountains desert", "Lima up to Arequipa and El Misti."),
    (["SCEL", "SCTE"], "Chilean lakes", "mountains volcano", "Santiago south to Puerto Montt past the volcanoes."),
    (["SBSP", "SBJR"], "Brazil coast", "coast landmark", "Sao Paulo to Rio along the Costa Verde."),
    (["EGPB", "EGPA"], "Shetland and Orkney", "islands coast", "Sumburgh to Kirkwall over the northern isles."),
    (["EGHI", "EGHH"], "Jurassic Coast", "coast", "Southampton west along the cliffs to Bournemouth."),
    (["EIWF", "EIKY"], "Ring of Kerry", "coast mountains", "Waterford to Kerry along Ireland's south coast."),
    (["ENAL", "ENBR"], "Geiranger country", "water mountains", "Alesund south past the fjords to Bergen."),
    (["ESSA", "ESNQ"], "Lapland", "ice water", "Stockholm north to Kiruna and the midnight sun."),
    (["EFHK", "EFRO"], "Finnish lakes", "water ice", "Helsinki to Rovaniemi on the Arctic Circle."),
    (["LFLP", "LFLJ"], "Mont Blanc", "mountains ice", "Annecy to Courchevel past Europe's highest peak."),
    (["LIMJ", "LIRQ"], "Ligurian coast", "coast", "Genoa to Florence over the Cinque Terre."),
    (["LEPA", "LEIB"], "Balearics", "islands coast", "Mallorca to Ibiza."),
    (["LPFR", "LPPT"], "Algarve to Lisbon", "coast", "Faro up the Atlantic coast."),
    (["LCLK", "LCPH"], "Cyprus", "islands coast", "Larnaca around to Paphos."),
    (["HTZA", "HTDA"], "Zanzibar channel", "islands coast", "Zanzibar to Dar es Salaam."),
    (["FAGG", "FACT"], "Garden Route", "coast mountains", "George west to Cape Town."),
    (["OMAA", "OOMS"], "Musandam", "desert coast mountains", "Abu Dhabi to Muscat past the fjords of Arabia."),
    (["OIKB", "OIFM"], "Persian plateau", "desert mountains", "Bandar Abbas north to Isfahan."),
    (["VNPK", "VNKT"], "Annapurna", "mountains", "Pokhara to Kathmandu under the giants."),
    (["VTCC", "VTCT"], "Golden Triangle", "mountains", "Chiang Mai to Chiang Rai."),
    (["WIOO", "WIHH"], "Sumatra to Java", "volcano islands", "Pontianak across to Jakarta."),
    (["RPLL", "RPVB"], "Philippine islands", "islands coast", "Manila down to Boracay."),
    (["RJFK", "RJKA"], "Kyushu volcanoes", "volcano islands", "Kagoshima and Sakurajima to Amami."),
    (["YSCB", "YMER"], "Snowy Mountains", "mountains water", "Canberra south to Merimbula over the Alps."),
    (["YBTL", "YBCS"], "Coral Sea coast", "coast islands", "Townsville north to Cairns."),
    (["NZGS", "NZNR"], "East Cape", "coast", "Gisborne to Napier along Hawke's Bay."),
    (["NFTF", "NFFN"], "South Pacific hop", "islands coast", "Tonga across to Fiji."),
    # ---------------- more, added in v4.5 ----------------
    # North America
    (["PAKT", "PAWG"], "Inside Passage south", "coast water ice", "Ketchikan to Wrangell between the islands and the Stikine delta."),
    (["PABE", "PADL"], "Bristol Bay", "water coast", "Bethel down to Dillingham over tundra and salmon rivers."),
    (["PAMC", "PAIN"], "Denali approach", "mountains ice", "McGrath to the north side of Denali."),
    (["CYXY", "CYDB"], "Yukon gold country", "mountains water", "Whitehorse to Burwash Landing along Kluane's icefields."),
    (["CYYE", "CYXJ"], "Peace River country", "mountains water", "Fort Nelson to Fort St John down the Rockies' eastern wall."),
    (["CYQQ", "CYAZ"], "Vancouver Island west", "coast islands", "Comox across to Tofino and the open Pacific."),
    (["CYFB", "CYVM"], "Baffin Island", "ice coast", "Iqaluit north to Broughton Island past the fjords."),
    (["CYGK", "CYOW"], "Thousand Islands", "water islands", "Kingston up the St Lawrence to Ottawa."),
    (["KJAC", "KCOD"], "Yellowstone loop", "mountains", "Jackson Hole over the Tetons and Yellowstone to Cody."),
    (["KRDD", "KMFR"], "Cascade volcanoes", "volcano mountains", "Redding north past Shasta to Medford."),
    (["KMRY", "KSBA"], "Big Sur", "coast", "Monterey down Highway 1 to Santa Barbara."),
    (["KAVX", "KSNA"], "Catalina", "islands coast", "The island in the channel, back into Orange County."),
    (["KTVL", "KTRK"], "Lake Tahoe", "water mountains", "South Lake Tahoe around the lake to Truckee."),
    (["KBIH", "KMMH"], "Owens Valley", "mountains desert", "Bishop under the Sierra crest to Mammoth."),
    (["KMOB", "KNEW"], "Gulf marshes", "water coast jungle", "Mobile Bay west across the Louisiana bayous."),
    (["KHXD", "KSAV"], "Lowcountry", "coast water", "Hilton Head to Savannah over the sea islands."),
    (["KBHB", "KRKD"], "Acadia", "coast islands", "Bar Harbor down the Maine island coast."),
    (["KLEB", "KMPV"], "White Mountains", "mountains", "Lebanon across the notches to Montpelier."),
    (["KGGW", "KBIL"], "Missouri Breaks", "water desert", "Glasgow up the river badlands to Billings."),
    (["MMZO", "MMPR"], "Mexican Riviera", "coast", "Manzanillo north to Puerto Vallarta."),
    (["MMCU", "MMLO"], "Copper Canyon", "desert mountains", "Chihuahua over the Barrancas del Cobre."),
    (["MPTO", "MPBO"], "Darien Gap", "jungle coast", "Panama City out to Bocas del Toro over the rainforest."),
    (["MKJS", "MKJP"], "Jamaica", "islands mountains", "Montego Bay over the Blue Mountains to Kingston."),
    (["TNCM", "TNCS"], "St Maarten hop", "islands coast", "Famous beach approach, then the short strip on Saba."),
    (["TAPA", "TKPK"], "Leeward Islands", "islands volcano", "Antigua up the arc to St Kitts."),
    (["TBPB", "TGPY"], "Windward Islands", "islands coast", "Barbados west to Grenada."),
    # South America
    (["SCTE", "SCBA"], "Chilean lake district", "volcano water", "Puerto Montt north past Osorno volcano to Balmaceda."),
    (["SCNT", "SCCI"], "Patagonian ice", "ice mountains", "Rio Gallegos across to Punta Arenas."),
    (["SAZS", "SAWH"], "Bariloche to the end", "mountains water", "The Andes lakes south to Ushuaia."),
    (["SAME", "SCEL"], "Aconcagua crossing", "mountains ice", "Mendoza over the Andes to Santiago - the classic high crossing."),
    (["SBGL", "SBSP"], "Rio to Sao Paulo", "coast landmark", "Sugarloaf, Copacabana, then the Serra do Mar."),
    (["SBFL", "SBCT"], "Santa Catarina coast", "coast islands", "Florianopolis north to Curitiba."),
    (["SBFI", "SBCA"], "Iguazu falls", "water jungle", "Circle the falls, then east over the forest."),
    (["SBMN", "SBTF"], "Amazon river", "jungle water", "Manaus up the Solimoes - green in every direction."),
    (["SPZO", "SPJC"], "Cusco to the coast", "mountains desert", "Out of the Andes at 11,000 ft down to Lima."),
    (["SPQU", "SPJL"], "Lake Titicaca", "water mountains", "Arequipa over the altiplano to Juliaca."),
    (["SEQM", "SETN"], "Avenue of the Volcanoes", "volcano mountains", "Quito south between Cotopaxi and Chimborazo."),
    (["SKRG", "SKCG"], "Colombian Caribbean", "coast mountains", "Medellin out of the valley to Cartagena."),
    (["SVMG", "SVCS"], "Los Roques", "islands coast", "Margarita across the archipelago to Caracas."),
    # Europe
    (["BIRK", "BIIS"], "Iceland west", "ice volcano", "Reykjavik north over the glaciers to Isafjordur's fjord."),
    (["BIEG", "BIHN"], "Iceland east", "ice water", "Egilsstadir down the eastern fjords."),
    (["ENSB", "ENTC"], "Svalbard run", "ice coast", "Longyearbyen south across the Barents Sea to Tromso."),
    (["ESKS", "ESPA"], "Swedish Lapland", "ice water", "Mora north to Lulea over endless forest and lakes."),
    (["EFIV", "EFKT"], "Finnish Arctic", "ice", "Ivalo to Kittila - snow, reindeer, and low sun."),
    (["EGPC", "EGPA"], "Orkney hop", "islands coast", "Wick across to Kirkwall - some of the shortest hops in the world."),
    (["EGPR", "EGPL"], "Barra beach landing", "islands coast", "The only scheduled beach runway, out to Benbecula."),
    (["EGEC", "EGPK"], "Mull of Kintyre", "coast islands", "Campbeltown up the Clyde coast."),
    (["EIDL", "EICK"], "Wild Atlantic Way", "coast", "Donegal south along Ireland's cliffs to Cork."),
    (["LFKJ", "LFKC"], "Corsica", "islands mountains", "Ajaccio around the granite spine to Calvi."),
    (["LIEO", "LIEA"], "Sardinia", "islands coast", "Olbia along the Costa Smeralda to Alghero."),
    (["LIPB", "LIPZ"], "Dolomites to Venice", "mountains landmark", "Bolzano through the peaks, out over the lagoon."),
    (["LGSM", "LGSA"], "Aegean islands", "islands coast", "Samos down past the Cyclades to Crete."),
    (["LGKF", "LGZA"], "Ionian", "islands coast", "Kefalonia to Zakynthos over Shipwreck Bay."),
    (["LDSP", "LDDU"], "Dalmatian coast", "islands coast", "Split down past Hvar and Korcula to Dubrovnik."),
    (["LQSA", "LYTV"], "Balkan mountains", "mountains", "Sarajevo over the Durmitor to the Bay of Kotor."),
    (["LTFC", "LTAZ"], "Cappadocia", "desert landmark", "Isparta east to the fairy chimneys of Nevsehir."),
    (["LEGE", "LEBL"], "Pyrenees to the Med", "mountains coast", "Girona over the Costa Brava into Barcelona."),
    # Africa & Middle East
    (["HKJK", "HKMO"], "Kenya coast", "coast bush", "Nairobi east across Tsavo to Mombasa."),
    (["FYWB", "FYSM"], "Skeleton Coast", "desert coast", "Walvis Bay north past shipwrecks and dunes."),
    (["FMMI", "FMNM"], "Madagascar", "jungle coast", "Antananarivo west to Mahajanga."),
    (["HESH", "HEGR"], "Sinai and the Red Sea", "desert coast", "Sharm el Sheikh up the gulf to Al Arish."),
    (["OJAQ", "OJAI"], "Wadi Rum", "desert", "Aqaba north over the red desert to Amman."),
    (["OASA", "OOSA"], "Dhofar monsoon", "mountains coast", "Salalah's green hills and the Empty Quarter's edge."),
    # Asia & Pacific
    (["UHPP", "UHSH"], "Kamchatka", "volcano ice", "Petropavlovsk north past the volcanic cones."),
    (["UIII", "UIUU"], "Lake Baikal", "water mountains", "Irkutsk around the deepest lake on earth."),
    (["UAAA", "UCFM"], "Tien Shan", "mountains ice", "Almaty over the Zailiysky Alatau to Bishkek."),
    (["ZULS", "ZUNZ"], "Tibetan plateau", "mountains ice", "Lhasa east down the Yarlung gorge - the roof of the world."),
    (["ZJSY", "VLPS"], "Mekong", "jungle water", "Sanya across to the Mekong at Pakse."),
    (["VQPR", "VNKT"], "Paro", "mountains", "Bhutan's valley approach, west along the Himalaya to Kathmandu."),
    (["VCBI", "VCCC"], "Sri Lanka hill country", "mountains jungle", "Colombo up to the tea plantations."),
    (["VOCI", "VOTV"], "Kerala backwaters", "water jungle coast", "Kochi south along the lagoons."),
    (["WADD", "WADL"], "Bali and Lombok", "volcano islands", "Denpasar east past Agung and Rinjani."),
    (["WAMM", "WAMH"], "Sulawesi", "islands jungle", "Manado down the coast past Tomohon's volcanoes."),
    (["ROAH", "RORS"], "Okinawa chain", "islands coast", "Naha down the Ryukyus to Miyako."),
    (["RKPC", "RKJJ"], "Jeju", "volcano islands", "The island volcano, back to the Korean mainland."),
    (["RCKH", "RCFN"], "Taroko gorge", "mountains coast", "Kaohsiung up Taiwan's east coast cliffs."),
    (["YPKU", "YPBR"], "Kimberley", "desert coast bush", "Kununurra west over the Bungle Bungles to Broome."),
    (["YAYE", "YPLM"], "Red centre", "desert bush", "Ayers Rock across the Gibson Desert."),
    (["YLHI", "YSDU"], "Lord Howe", "islands coast", "The island runway between two peaks, back to the mainland."),
    (["NZMF", "NZWF"], "Milford Sound", "water mountains", "Milford out through the fiords to Wanaka."),
    (["NTAA", "NTTM"], "Bora Bora", "islands coast", "Tahiti out to the lagoon."),
    (["PHNY", "PHTO"], "Hawaiian volcanoes", "volcano islands", "Lanai across to Hilo under Mauna Loa."),
    (["PGUM", "PTKK"], "Micronesia", "islands coast", "Guam out to Chuuk lagoon - a long way over water."),
    (["FZAA", "FZNA"], "Congo basin", "jungle bush", "Kinshasa east over unbroken rainforest to Goma's volcanoes."),
    (["SYGO", "SYCJ"], "Guyana interior", "jungle water bush", "Kaieteur Falls country out to Georgetown."),
    (["AYPY", "AYMD"], "Papua highlands", "jungle mountains bush", "Port Moresby north over the Owen Stanleys to Madang."),
    (["WAJJ", "WAJW"], "Baliem valley", "jungle mountains bush", "Jayapura to Wamena - one of the world's great bush runs."),
    (["FLKK", "FLMF"], "Luangwa valley", "bush water", "Lusaka east to Mfuwe over the game parks."),
    (["HAAB", "HASO"], "Ethiopian highlands", "mountains bush", "Addis north to the Simien escarpment."),
    (["KTKA", "PATK"], "Alaska bush strips", "bush mountains", "Talkeetna out to the gravel bars under Denali."),
    (["U76", "KSUN"], "Idaho backcountry", "bush mountains", "Mountain Home down the Middle Fork strips to Sun Valley."),
    (["CYPY", "CYYQ"], "Hudson Bay", "ice coast bush", "Fort Chipewyan across the barrens to Churchill."),
]


KEYWORDS = [
    (re.compile(r"\b(GLACIER|ICEFIELD|ICE CAP)\b"), "ice", "glacier country"),
    (re.compile(r"\b(ISLAND|ISLANDS|ISLE|KEY|CAY|ILHA|ILE|ISLA|ISOLA|INSEL|ATOLL)\b"), "islands", "an island strip"),
    (re.compile(r"\b(LAKE|LAGO|LAC|SEE|LOCH|RIVER|FJORD|FIORD|SOUND|FALLS)\b"), "water", "by the water"),
    (re.compile(r"\b(CANYON|GORGE|MESA|DESERT|DUNE|DUNES|OASIS)\b"), "desert", "canyon or desert country"),
    (re.compile(r"\b(BAY|BEACH|HARBOR|HARBOUR|COAST|CAPE|POINT|PLAYA|PRAIA|PORT)\b"), "coast", "on the coast"),
    (re.compile(r"\b(VOLCANO|VOLCAN|CRATER|CALDERA)\b"), "volcano", "volcano country"),
    (re.compile(r"\b(JUNGLE|RAINFOREST|FOREST|SWAMP|MARSH|DELTA|SELVA|FLORESTA)\b"), "jungle", "jungle or wetland country"),
    (re.compile(r"\b(RANCH|STATION|CAMP|LODGE|MINE|OUTPOST|AIRSTRIP|BUSH|SAFARI)\b"), "bush", "proper backcountry"),
    (re.compile(r"\b(MOUNT|MOUNTAIN|MTN|PEAK|PASS|RIDGE|ALPINE|ALPE|SIERRA|MONTE|VALLEY|CANADIAN ROCKIES)\b"), "mountains",
     "mountain country"),
]


def _d(a, b):
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(x)))


def continent_of(a):
    for k in CONTINENTS:
        if k != "Whole world" and in_area(a, k):
            return k
    return "Elsewhere"


def best_months(lat):
    if lat > 60:
        return [5, 6, 7]
    if lat > 23:
        return [4, 5, 6, 7, 8]
    if lat < -40:
        return [11, 0, 1, 2]
    if lat < -23:
        return [10, 11, 0, 1, 2, 3]
    return list(range(12))


class ScenicFinder:
    def __init__(self, core, airports, aircraft, rng, include_private=True):
        self.core, self.all, self.ac, self.rng = core, airports, aircraft, rng
        from types import SimpleNamespace
        self.gen = core.Generator(airports, aircraft, rng,
                                  SimpleNamespace(country="ANY", include_private=include_private))
        self.by_id = self.gen.by_id
        self._gems = None

    # ---- helpers --------------------------------------------------------
    def usable(self, a):
        return bool(a) and bool(self.gen.usable(a))

    def substitute(self, a, r=25):
        """a itself if usable, else the nearest usable airport within r nm (or None)."""
        if self.usable(a):
            return a
        near = self.gen.within(a, 0.5, r)
        return min(near, key=lambda x: _d(a, x)) if near else None

    # ---- famous places ------------------------------------------------------
    def famous(self, tags=None, area="Whole world"):
        out = []
        for ids, title, tg, text in FAMOUS:
            tset = set(tg.split())
            if tags and not (tset & set(tags)):
                continue
            aps = [self.by_id.get(i) for i in ids]
            if not all(aps):
                continue                     # not in this user's scenery
            if area and area != "Whole world" and not in_area(aps[0], area):
                continue
            stops, overfly = [], []
            for a in aps:
                s = self.substitute(a)
                if not s:
                    break
                if s is not a:
                    overfly.append((a, s))
                if not stops or stops[-1] is not s:
                    stops.append(s)
            else:
                out.append({"src": "famous", "title": title, "tags": tset, "text": text, "sights": aps,
                            "stops": stops, "overfly": overfly})
        return out

    # ---- hidden gems ----------------------------------------------------------
    def _compute_gems(self):
        cell = 0.5
        mx = {}
        for a in self.all:
            k = (int(a["lat"] // cell), int(a["lon"] // cell))
            mx[k] = max(mx.get(k, -9999), a["elev"])
        famous_ids = {i for ids, *_ in FAMOUS for i in ids}
        gems = []
        for a in self.gen.pool:
            if a["id"] in famous_ids:
                continue
            ci, cj = int(a["lat"] // cell), int(a["lon"] // cell)
            hi = max(mx.get((ci + i, cj + j), -9999) for i in (-1, 0, 1) for j in (-1, 0, 1))
            relief = hi - a["elev"]
            name = a["name"].upper()
            tags, why, score = set(), [], 0.0
            if relief >= 2500:
                tags.add("mountains")
                score += relief / 1500
                why.append(f"terrain rising about {round(relief, -2):,.0f} ft above the field nearby")
            if a["elev"] >= 6500:
                tags.add("mountains")
                score += a["elev"] / 3000
                why.append(f"a high strip at {a['elev']:,} ft")
            for rx, tag, text in KEYWORDS:
                if rx.search(name):
                    tags.add(tag)
                    score += 1.5
                    why.append(text)
            if any(r["s"] == "water" for r in a["rwys"]):
                tags.add("water")
                score += 1.0
                why.append("a water runway")
            if abs(a["lat"]) > 62:
                tags.add("ice")
                score += 1.5
                why.append("high-latitude scenery")
            if any(r["s"] in ("grass", "dirt", "gravel") for r in a["rwys"]) and relief >= 2000:
                score += 1.0
                why.append("an unpaved backcountry runway")
            if self.core.is_private(a):
                score *= 0.5
            if score >= 2.5 and tags:
                gems.append({"src": "gem", "title": a["name"].title(), "tags": tags, "score": score,
                             "text": "Found in your scenery: " + ", ".join(dict.fromkeys(why)) + ".",
                             "sights": [a], "stops": [a], "overfly": []})
        gems.sort(key=lambda g: -g["score"])
        self._gems = gems

    def gems(self, tags=None, area="Whole world"):
        if self._gems is None:
            self._compute_gems()
        out = self._gems
        if tags:
            out = [g for g in out if g["tags"] & set(tags)]
        if area and area != "Whole world":
            out = [g for g in out if in_area(g["stops"][0], area)]
        return out

    # ---- making flights -------------------------------------------------------
    def candidates(self, tags=None, area="Whole world", famous=True, gems=True):
        c = []
        if famous:
            c += self.famous(tags, area)
        if gems:
            c += self.gems(tags, area)[:600]
        return c

    def to_idea(self, cand):
        core, g, rng = self.core, self.gen, self.rng
        stops = list(cand["stops"])
        if len(stops) == 1:
            dest = stops[0]
            R = min(self.ac["range"] * 0.4, 140)
            deps = g.within(dest, 25, R) or g.within(dest, 8, R * 1.5)
            if not deps:
                return None
            dep = g.pick(deps, lambda a: (3 if a["tower"] else 1) * (1 if 35 <= _d(a, dest) <= 100 else 0.4))
            stops = [dep, dest]
        if len(stops) < 2:
            return None
        m = rng.choice(best_months(stops[-1]["lat"]))
        tod = rng.choice(["morning", "golden", "golden"])
        if "ice" in cand["tags"] and abs(stops[-1]["lat"]) > 62 and rng.random() < 0.4:
            m, tod = rng.choice([0, 1, 2, 10, 11]) if stops[-1]["lat"] > 0 else rng.choice([4, 5, 6, 7]), "night"
        if cand["title"] == "Dubai":
            tod = "night"
        wx = g.mkwx(stops[-1], m, sky=rng.choice(["clear", "few", "few", "cu"]), wspd=rng.choice([0, 3, 5, 8]))
        where = ", ".join(x for x in (stops[-1].get("city"), stops[-1].get("state"),
                                      stops[-1].get("country") or stops[-1].get("iso")) if x)
        notes = [f"Where: {where or continent_of(stops[-1])}  ({continent_of(stops[-1])})",
                 "Scenery: " + ", ".join(TAGS[t] for t in sorted(cand["tags"]) if t in TAGS),
                 "Turn the visibility up, slow down, and fly low enough to enjoy it (legally!)."]
        for sight, sub in cand["overfly"]:
            notes.append(f"Your plane can't use {sight['id']} ({sight['name']}) - overfly it and land at "
                         f"{sub['id']} {sub['name']}, {_d(sight, sub):.0f} nm away.")
        title = ("World scenic: " if cand["src"] == "famous" else "Hidden gem: ") + cand["title"]
        idea = core.Idea("scenic", title, stops, cand["text"], month=m, tod=tod, wx=wx, notes=notes,
                         wx_at=stops[-1])
        idea.scenic = cand
        return idea

    def surprise(self, n=1, tags=None, area="Whole world", famous=True, gems=True):
        fam = self.famous(tags, area) if famous else []
        gem = self.gems(tags, area)[:600] if gems else []
        self.rng.shuffle(fam)
        self.rng.shuffle(gem)
        ideas, seen = [], set()
        while len(ideas) < n and (fam or gem):
            src = fam if fam and (not gem or self.rng.random() < 0.55) else gem
            c = src.pop()
            key = c["stops"][-1]["id"]
            if key in seen:
                continue
            i = self.to_idea(c)
            if i:
                ideas.append(i)
                seen.add(key)
        return ideas
