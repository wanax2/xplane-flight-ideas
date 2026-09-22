"""
xp_scenic.py - "anywhere in the world" scenic flight generator.

Four sources:
  * FAMOUS  - a hand-picked list of well-known scenic airports and routes on every continent
  * WONDERS - the scenic places themselves (xp_wonders.py): 400-odd waterfalls,
              volcanoes, glaciers, gorges, reefs and ruins that mostly have no
              airport at all. The finder puts you over the thing itself and lands
              you at the nearest runway your plane can use.
  * GEMS    - "hidden gems" found automatically in YOUR X-Plane scenery: airports
              surrounded by much higher terrain (judged from nearby airport
              elevations), high-altitude strips, islands, glaciers, lakes, fjords,
              canyons... (from the airport data and names)
  * RANDOM  - a dart thrown at the planet. Any airport, anywhere in your scenery,
              with a light bias towards interesting ground. This is the one that
              takes you places no list would ever have suggested.

Every pick is checked against your scenery and aircraft. If your plane can't use
the famous strip itself, the flight overflies it and lands at the nearest
airport it can use.
"""
from __future__ import annotations

import math
import re

import xp_wonders as wonders_db
from xp_wx import CONTINENTS, in_area

# How far from a natural wonder we will accept a runway. Bigger than it sounds:
# Angel Falls, the Putorana plateau and the Empty Quarter have nothing close.
WONDER_R = 130.0

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
    # ---------------- more again, added in v6.1 ----------------
    # North America
    (["KFLG", "KSEZ"], "Flagstaff to Sedona", "desert mountains", "Off the 7,000 ft plateau and down into the red rocks."),
    (["KPRC", "KGCN"], "Prescott to the canyon", "desert", "Granite Dells, the Verde valley and the South Rim."),
    (["KSGU", "KCDC"], "Zion's back door", "desert", "St George up past Zion's east side to Cedar City."),
    (["KTUS", "KOLS"], "Sonoran desert", "desert", "Saguaro forest and sky islands down to the border."),
    (["KROW", "KCNM"], "Guadalupe escarpment", "desert mountains", "Roswell south past the reef to Carlsbad."),
    (["KMAF", "KMRF"], "Big Bend country", "desert", "Out of the oil patch into the Davis Mountains."),
    (["KELP", "KTCS"], "Rio Grande north", "desert water", "El Paso up the river to Truth or Consequences."),
    (["KSAF", "KTAD"], "Sangre de Cristo", "mountains", "Santa Fe north along the last of the Rockies."),
    (["KASE", "KGUC"], "Elk Mountains", "mountains", "Aspen over the ridge to Gunnison."),
    (["KMTJ", "KTEX"], "San Juans", "mountains", "Montrose into the deepest corner of Colorado."),
    (["KGJT", "KMTJ"], "Grand Mesa", "mountains desert", "The largest flat-topped mountain in the world."),
    (["KRIL", "KEGE"], "Glenwood Canyon", "mountains water", "Follow the Colorado up the canyon to Eagle."),
    (["KLAR", "KRKS"], "Red Desert", "desert", "Laramie west across the Great Divide Basin."),
    (["KCPR", "KRIW"], "Wind River Range", "mountains ice", "Casper west to Riverton under Gannett Peak."),
    (["KBIL", "KSHR"], "Bighorns", "mountains", "Billings south-east over the range to Sheridan."),
    (["KBZN", "KWYS"], "Gallatin valley", "mountains", "Bozeman up the canyon to West Yellowstone."),
    (["KMSO", "KSMN"], "Bitterroots", "mountains bush", "Missoula down the valley and over the divide to Salmon."),
    (["KSUN", "KBOI"], "Sawtooth valley", "mountains water", "Sun Valley down the Salmon River to Boise."),
    (["KLWS", "KPUW"], "Hells Canyon rim", "water mountains", "Lewiston over the deepest gorge in America."),
    (["KPDT", "KDLS"], "Columbia Gorge east", "water desert", "Pendleton down the river to The Dalles."),
    (["KYKM", "KELN"], "Cascades east", "mountains volcano", "Yakima north with Rainier and Adams on the wing."),
    (["KPAE", "KORS"], "Puget Sound", "islands water", "Everett across the water to Orcas Island."),
    (["KHQM", "KAST"], "Washington coast", "coast", "Grays Harbor south to the mouth of the Columbia."),
    (["KOTH", "KCEC"], "Redwood coast", "coast jungle", "Coos Bay down to the tallest trees on earth."),
    (["KACV", "KUKI"], "Lost Coast", "coast mountains", "Eureka over King Range to the Ukiah valley."),
    (["KIPL", "KBLH"], "Lower Colorado", "desert water", "Below sea level, then up the river to Blythe."),
    (["KAUS", "KDRT"], "Texas hill country", "water desert", "Austin west over the limestone hills to the border."),
    (["KHOU", "KGLS"], "Galveston Bay", "coast water", "Ship channel, the bay and the island."),
    (["KNEW", "KHUM"], "Bayou country", "water jungle", "New Orleans out over the marsh to Houma."),
    (["KTLH", "KPFN"], "Forgotten Coast", "coast", "Tallahassee to the Panhandle beaches."),
    (["KSRQ", "KAPF"], "Florida Gulf coast", "coast water", "Sarasota south past the barrier islands to Naples."),
    (["KILM", "KMYR"], "Carolina coast", "coast", "Wilmington up the beaches to Myrtle Beach."),
    (["KRDU", "KAVL"], "Blue Ridge", "mountains jungle", "Raleigh west into the Appalachians."),
    (["KTRI", "KGKT"], "Great Smoky Mountains", "mountains jungle", "Tri-Cities south over the ridges to Gatlinburg."),
    (["KROA", "KLWB"], "Allegheny ridges", "mountains", "Roanoke north-west across parallel ridge after ridge."),
    (["KELM", "KITH"], "Finger Lakes", "water", "Elmira north over the long narrow lakes."),
    (["KSLK", "KPBG"], "Adirondacks", "mountains water", "Saranac Lake east to Lake Champlain."),
    (["KBTV", "KMPV"], "Green Mountains", "mountains", "Burlington across the spine of Vermont."),
    (["KLEB", "KHIE"], "The Notches", "mountains", "Lebanon north through Franconia to the Presidentials."),
    (["KPWM", "KBGR"], "Maine woods", "coast bush", "Portland up the coast and inland to Bangor."),
    (["KTVC", "KMCD"], "Lake Michigan shore", "water islands", "Traverse City north to the Straits."),
    (["KDLH", "KINL"], "Boundary Waters", "water bush", "Duluth north over a thousand lakes to the border."),
    (["KRAP", "KGCC"], "Devils Tower", "landmark desert", "Rapid City west past the Black Hills to the Tower."),
    (["KBIS", "KDIK"], "North Dakota badlands", "desert", "Bismarck west to the Little Missouri breaks."),
    (["CYXS", "CYZT"], "British Columbia coast", "coast mountains", "Prince George out to the north end of Vancouver Island."),
    (["CYVR", "CYYJ"], "Georgia Strait", "islands water", "Vancouver across the Gulf Islands."),
    (["CYCG", "CYXC"], "Kootenays", "mountains water", "Castlegar up the lakes to Cranbrook."),
    (["CYYC", "CYBA"], "Front ranges", "mountains", "Calgary west into the wall of the Rockies."),
    (["CYEG", "CYJA"], "Jasper", "mountains ice", "Edmonton south-west to the icefields."),
    (["CYMM", "CYZF"], "Northern lakes", "water bush", "Fort McMurray north over the boreal to Yellowknife."),
    (["CYQB", "CYBG"], "Saguenay fjord", "water mountains", "Quebec north-east up the fjord."),
    (["CYHZ", "CYQY"], "Nova Scotia coast", "coast", "Halifax up the eastern shore to Cape Breton."),
    (["CYYT", "CYDF"], "Newfoundland", "coast bush", "St John's west across the rock."),
    (["CYFB", "CYRB"], "High Arctic", "ice", "Iqaluit north-west to Resolute - a long way over ice."),
    (["PAFA", "PABT"], "Yukon River", "water bush", "Fairbanks north-west to Bettles and the Brooks Range."),
    (["PAEN", "PAHO"], "Kenai Peninsula", "mountains ice coast", "Kenai down past the Harding Icefield."),
    (["PACV", "PAYA"], "Gulf of Alaska", "ice coast", "Cordova east past the Bering Glacier to Yakutat."),
    (["PADQ", "PAKN"], "Kodiak and Katmai", "islands volcano", "Across Shelikof Strait to the volcano coast."),
    (["MMMD", "MMUN"], "Yucatan", "jungle coast", "Merida east over the cenote country to the reef."),
    (["MMTO", "MMMX"], "Valley of Mexico", "volcano mountains", "Toluca past Popocatepetl into the basin."),
    (["MMLP", "MMSD"], "Baja south", "coast desert", "La Paz down the cape to Land's End."),
    (["MMHO", "MMGM"], "Sea of Cortez", "coast desert", "Hermosillo out to the Guaymas islands."),
    (["MGGT", "MGSJ"], "Guatemalan volcanoes", "volcano", "Over Fuego and Agua to the Pacific coast."),
    (["MROC", "MRLB"], "Costa Rica volcanoes", "volcano jungle", "San Jose north-west past Arenal to Guanacaste."),
    (["MPMG", "MPDA"], "Chiriqui", "jungle mountains", "Panama City west to the highlands under Volcan Baru."),
    (["TIST", "TISX"], "US Virgin Islands", "islands coast", "St Thomas over the reefs to St Croix."),
    (["TKPK", "TFFR"], "Leeward arc", "islands volcano", "St Kitts down past Montserrat's ash to Guadeloupe."),
    (["TFFF", "TFFG"], "French Antilles", "islands coast", "Martinique north past Dominica to St Martin."),
    (["TTPP", "TTCP"], "Trinidad and Tobago", "islands coast", "Across the channel to Tobago's reefs."),
    # South America
    (["SOCA", "SMJP"], "Guiana coast", "jungle coast", "Cayenne west along the rainforest shore."),
    (["SVCB", "SVCN"], "Angel Falls country", "jungle landmark water", "Ciudad Bolivar south to Canaima and the tepuis."),
    (["SBBE", "SBMN"], "Amazon crossing", "jungle water", "Belem 900 miles up the river to Manaus."),
    (["SBSV", "SBIL"], "Bahia coast", "coast", "Salvador south along the Atlantic beaches."),
    (["SBPA", "SBFL"], "Southern Brazil", "coast islands", "Porto Alegre north to Florianopolis."),
    (["SGAS", "SBFI"], "Parana river", "water jungle", "Asuncion east to Iguazu."),
    (["SUMU", "SULS"], "Uruguay coast", "coast", "Montevideo east to Punta del Este."),
    (["SAEZ", "SAZM"], "Pampas to the sea", "coast", "Buenos Aires south to the Atlantic."),
    (["SAZN", "SAZS"], "Patagonian lakes", "mountains water", "Neuquen west into the Andean lake district."),
    (["SAVC", "SAWE"], "Patagonian coast", "coast desert", "Comodoro south down the empty shore."),
    (["SCFA", "SCDA"], "Atacama", "desert", "Antofagasta north over the driest desert on earth."),
    (["SCIE", "SCTE"], "Araucania volcanoes", "volcano water", "Concepcion south past Villarrica."),
    (["SPHI", "SPJC"], "Peruvian coast", "coast desert", "Chiclayo south down the desert shoreline."),
    (["SPST", "SPQT"], "Upper Amazon", "jungle water", "Tarapoto down to Iquitos - no roads in or out."),
    (["SLCB", "SLLP"], "Bolivian Andes", "mountains", "Cochabamba over the altiplano to La Paz."),
    (["SEGU", "SEQM"], "Coast to the Andes", "mountains volcano", "Guayaquil up 9,000 ft into the Avenue of the Volcanoes."),
    # Europe
    (["LFMD", "LFKF"], "Cote d'Azur", "coast islands", "Cannes out across the Med to southern Corsica."),
    (["LFLS", "LFLB"], "Chartreuse and Vercors", "mountains", "Grenoble's limestone walls and the Savoie lakes."),
    (["LFBO", "LFBZ"], "Pyrenees foothills", "mountains coast", "Toulouse west to the Basque coast."),
    (["LFRB", "LFRQ"], "Brittany", "coast islands", "Brest around the Pointe du Raz."),
    (["LFRG", "LFRK"], "Normandy", "coast landmark", "Deauville west over the invasion beaches."),
    (["EHAM", "EHGG"], "Dutch waterland", "water landmark", "Amsterdam north over the polders and the Afsluitdijk."),
    (["EDXW", "EDHL"], "Frisian islands", "islands coast", "Sylt down the Wadden Sea to Lubeck."),
    (["EKCH", "EKRN"], "Baltic Denmark", "islands coast", "Copenhagen east over the sea to Bornholm."),
    (["ESGG", "ESSA"], "Swedish archipelago", "islands water", "Gothenburg across the lakes to the Stockholm skerries."),
    (["EFTU", "EFMA"], "Aland islands", "islands water", "Turku west into six thousand islands."),
    (["EETN", "EEKA"], "Estonian islands", "islands coast", "Tallinn west to Hiiumaa."),
    (["EPGD", "EPSC"], "Polish Baltic", "coast", "Gdansk west along the dunes to Szczecin."),
    (["LOWW", "LOWK"], "Austrian Alps", "mountains water", "Vienna south-west over the Alps to Carinthia's lakes."),
    (["LHBP", "LHSM"], "Lake Balaton", "water", "Budapest south-west to the Hungarian sea."),
    (["LROP", "LRSB"], "Carpathians", "mountains", "Bucharest north over the Fagaras wall to Transylvania."),
    (["LBSF", "LBWN"], "Bulgaria to the Black Sea", "mountains coast", "Sofia east over the Balkan range."),
    (["LGAV", "LGSA"], "Aegean to Crete", "islands coast", "Athens south through the Cyclades."),
    (["LTAI", "LTAU"], "Taurus mountains", "mountains", "Antalya north over the range to Cappadocia's edge."),
    (["LTCG", "LTCE"], "Pontic Alps", "mountains coast", "Trabzon inland over the tea hills to Erzurum."),
    (["UGTB", "UGKO"], "Caucasus", "mountains ice", "Tbilisi west under the highest mountains in Europe."),
    (["LEVC", "LEIB"], "Valencia to Ibiza", "islands coast", "Out across the Med to the Balearics."),
    (["LEST", "LEVX"], "Rias Baixas", "coast water", "Santiago down Galicia's drowned valleys."),
    (["LEXJ", "LEAS"], "Picos de Europa", "mountains coast", "Santander west with limestone peaks inland."),
    (["LPPR", "LPBR"], "Douro valley", "water mountains", "Porto up the terraced river gorge."),
    (["LPPD", "LPHR"], "Azores hop", "islands volcano", "Sao Miguel west across the Atlantic to Faial."),
    (["GCTS", "GCLP"], "Teide", "volcano islands", "Tenerife around Spain's highest mountain to Gran Canaria."),
    (["GVAC", "GVBA"], "Cape Verde", "islands volcano desert", "Sal to Boa Vista over the dunes and the sea."),
    (["EIDW", "EIKN"], "Connemara", "coast water", "Dublin west to the Atlantic bogs and lakes."),
    (["EGAA", "EGNS"], "Irish Sea", "islands coast", "Belfast east to the Isle of Man."),
    (["EGPE", "EGPD"], "Moray Firth", "coast mountains", "Inverness along the firth with the Cairngorms inland."),
    (["EGPF", "EGEO"], "Loch Lomond and the isles", "water islands", "Glasgow north-west past the loch to Oban."),
    (["EGHR", "EGKA"], "The Solent", "coast", "Goodwood west over the Downs and the Isle of Wight."),
    (["EGTE", "EGHE"], "Cornwall and Scilly", "coast islands", "Exeter down the peninsula and out to sea."),
    (["ENVA", "ENBO"], "Helgeland coast", "coast islands", "Trondheim north over the Arctic Circle."),
    (["ENKB", "ENAL"], "Atlantic Road", "coast landmark", "Kristiansund south over the bridges and skerries."),
    (["ENZV", "ENHD"], "Lysefjord", "water mountains", "Stavanger east up the fjord under Preikestolen."),
    (["BIRK", "BIHU"], "Iceland highlands", "volcano desert ice", "Reykjavik north across the interior to Husavik."),
    # Africa and the Middle East
    (["DTTA", "DTTJ"], "Tunisian Sahara", "desert coast", "Tunis south to the salt lakes and Djerba."),
    (["DAAG", "DAAT"], "Deep Sahara", "desert mountains", "Algiers 1,000 miles south to the Hoggar."),
    (["HECA", "HELX"], "Down the Nile", "desert water landmark", "Cairo south along the green strip to Luxor."),
    (["LLBG", "LLER"], "Negev and the Dead Sea", "desert water", "Tel Aviv south past the lowest place on earth."),
    (["OEJN", "OETF"], "Hejaz escarpment", "mountains desert", "Jeddah up 6,000 ft into the mountains."),
    (["OOMS", "OOSA"], "Oman coast", "coast desert", "Muscat south-west along the edge of the Empty Quarter."),
    (["OMSJ", "OMFJ"], "Hajar mountains", "mountains coast", "Sharjah east over the range to the Gulf of Oman."),
    (["HAAB", "HADR"], "Rift escarpment", "volcano desert", "Addis east down to the Danakil's edge."),
    (["HKJK", "HKKI"], "Rift valley lakes", "water bush", "Nairobi west over the escarpment to Lake Victoria."),
    (["HTKJ", "HTMW"], "Serengeti crossing", "bush water", "Kilimanjaro west over the plains to Lake Victoria."),
    (["FQMA", "FQBR"], "Mozambique coast", "coast islands", "Maputo north up the Indian Ocean shore."),
    (["FVFA", "FVHA"], "Zambezi", "water bush", "Victoria Falls east to Harare."),
    (["FLKK", "FLLI"], "Down to the falls", "water landmark", "Lusaka south-west to Livingstone."),
    (["FYWH", "FYWB"], "Namib crossing", "desert coast", "Windhoek west down the escarpment to the sea."),
    (["FYWH", "FYKT"], "Fish River", "desert water", "Windhoek south to the great canyon."),
    (["FALE", "FAPM"], "Drakensberg", "mountains coast", "Durban inland to the Berg."),
    (["FAUP", "FAKM"], "Kalahari", "desert bush", "Upington east over the red dunes to Kimberley."),
    (["FMCZ", "FMEE"], "Indian Ocean hop", "islands volcano", "Mayotte south-east to Reunion's volcano."),
    (["FMMI", "FMSD"], "Madagascar south", "desert jungle", "Antananarivo down to the spiny forest and the cape."),
    (["GOOY", "GOGG"], "Casamance", "coast jungle water", "Dakar south over the Gambia to the Casamance delta."),
    (["GABS", "GAGO"], "Niger bend", "desert water", "Bamako down the river to the edge of the Sahara."),
    (["FKYS", "FKKD"], "Mount Cameroon", "volcano coast", "Yaounde west to the volcano on the sea."),
    (["FOOL", "FOOG"], "Gabon coast", "jungle coast", "Libreville south over the rainforest to the delta."),
    # Asia and the Pacific
    (["OPIS", "OPSD"], "Karakoram", "mountains ice", "Islamabad north to Skardu, under K2 and Nanga Parbat."),
    (["VIJP", "VIJO"], "Thar desert", "desert landmark", "Jaipur west to the blue city on the sand."),
    (["VISR", "VILH"], "Kashmir to Ladakh", "mountains ice", "Srinagar east over the Zoji La to the Indus."),
    (["VOML", "VOCL"], "Western Ghats", "mountains jungle coast", "Mangalore south with the escarpment inland."),
    (["VGHS", "VGCB"], "Sundarbans", "jungle water coast", "Dhaka south over the mangroves to the bay."),
    (["VYMD", "VYBG"], "Irrawaddy", "water landmark", "Mandalay down the river to Bagan's temples."),
    (["VTBS", "VTBU"], "Gulf of Thailand", "coast islands", "Bangkok south-east to the islands."),
    (["VTCC", "VTCN"], "Golden Triangle hills", "mountains jungle", "Chiang Mai east into the hill country."),
    (["VLVT", "VLLB"], "Laos mountains", "mountains jungle", "Vientiane north up the Mekong to Luang Prabang."),
    (["VVNB", "VVCI"], "Halong Bay", "islands water", "Hanoi east to two thousand limestone towers."),
    (["VVDN", "VVCR"], "Vietnam coast", "coast", "Da Nang south past the Hai Van pass and the dunes."),
    (["ZPPP", "ZPLJ"], "Tiger Leaping Gorge", "mountains water", "Kunming north-west to Lijiang and the Jade Dragon."),
    (["ZUUU", "ZUJZ"], "Jiuzhaigou", "water mountains", "Chengdu north into the terraced lakes."),
    (["ZGKL", "ZGGG"], "Li River karst", "jungle landmark", "Guilin's hills south-east to the delta."),
    (["ZSHC", "ZSTX"], "Huangshan", "mountains", "Hangzhou west to the Yellow Mountains' sea of cloud."),
    (["RJAA", "RJSS"], "Northern Honshu", "mountains coast", "Tokyo north up the spine of Japan."),
    (["RJCH", "RJCM"], "Hokkaido east", "coast ice bush", "Hakodate north-east to the drift ice coast."),
    (["ROAH", "ROIG"], "Yaeyama islands", "islands coast", "Okinawa south-west almost to Taiwan."),
    (["RPLC", "RPUB"], "Luzon cordillera", "mountains landmark", "Clark north into the rice terraces."),
    (["RPMD", "RPVP"], "Sulu Sea", "islands coast", "Davao west across the water to Palawan."),
    (["WIII", "WARR"], "Java volcanoes", "volcano", "Jakarta east along a line of cones to Surabaya."),
    (["WADD", "WATO"], "Komodo", "islands coast", "Bali east past Rinjani to the dragons."),
    (["WIPP", "WIBB"], "Sumatra", "jungle volcano", "Palembang north-west over the forest."),
    (["WAAA", "WAPP"], "Spice islands", "islands coast", "Makassar east to Ambon."),
    (["WASS", "WAJJ"], "Raja Ampat and Papua", "islands jungle", "Sorong east along the north coast of New Guinea."),
    (["AYPY", "AYNZ"], "Owen Stanleys", "jungle mountains bush", "Port Moresby over the Kokoda track to the Markham."),
    (["YBAS", "YCBP"], "Central Australia", "desert bush", "Alice Springs south to the opal fields."),
    (["YPDN", "YPGV"], "Arnhem Land", "bush jungle coast", "Darwin east over Kakadu to the Gulf."),
    (["YBBN", "YBSU"], "Sunshine Coast", "coast", "Brisbane north up the beaches to the Glasshouse Mountains."),
    (["YSSY", "YSNW"], "Sydney south", "coast landmark", "Out of the harbour down the sea cliffs to Jervis Bay."),
    (["YMML", "YMHB"], "Bass Strait", "islands coast", "Melbourne south over the water to Tasmania."),
    (["YPAD", "YPWR"], "Flinders Ranges", "desert mountains", "Adelaide north to Wilpena Pound and the outback."),
    (["YPPH", "YGEL"], "Coral Coast", "coast desert", "Perth north up the Indian Ocean shore."),
    (["NZAA", "NZRO"], "Bay of Plenty volcanoes", "volcano coast", "Auckland south-east to the geothermal country."),
    (["NZCH", "NZTU"], "Canterbury to the Alps", "mountains ice", "Christchurch south-west with the divide on the wing."),
    (["NZWN", "NZNS"], "Cook Strait", "water coast", "Wellington across to the Marlborough Sounds."),
    (["NFTF", "NFTV"], "Tonga", "islands coast", "Tongatapu north to the Vava'u group."),
    (["NVVV", "NVVW"], "Tanna", "volcano islands", "Port Vila south to Yasur's fireworks."),
    (["NWWW", "NWWL"], "New Caledonia lagoon", "islands coast", "Noumea north-east over the world's biggest lagoon."),
    (["PTKK", "PTPN"], "Micronesia", "islands coast", "Chuuk lagoon east to Pohnpei - a long way over water."),
    (["PGUM", "PGSN"], "Marianas", "islands volcano", "Guam north to Saipan."),
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


TITLES = {"famous": "World scenic: ", "gem": "Hidden gem: ",
          "wonder": "Wonder of the world: ", "random": "Anywhere on earth: "}


def fmt_ll(lat, lon):
    """A position you can read out loud, and type into the GPS."""
    return (f"{abs(lat):.3f}{'N' if lat >= 0 else 'S'} {abs(lon):.3f}{'E' if lon >= 0 else 'W'}")


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
        self._wonders = None
        self._relief = None
        self._idx = None
        self._pools = {}
        self._rand_seen = set()

    # ---- a coarse spatial index, so we don't scan 30,000 airports per lookup --
    def _index(self):
        if self._idx is None:
            idx = {}
            for a in self.gen.pool:
                idx.setdefault((int(a["lat"] // 1), int(a["lon"] // 1)), []).append(a)
            self._idx = idx
        return self._idx

    def near_pool(self, lat, lon, r, rmin=0.0):
        """Every usable airport within r nm of a position. Bucketed, so it's quick."""
        idx = self._index()
        c = {"lat": lat, "lon": lon}
        dlat = int(r / 60.0) + 1
        span = 60.0 * max(0.02, math.cos(math.radians(max(-89.0, min(89.0, lat)))))
        dlon = min(180, int(r / span) + 1)
        out = []
        for i in range(int(lat // 1) - dlat, int(lat // 1) + dlat + 1):
            for j in range(int(lon // 1) - dlon, int(lon // 1) + dlon + 1):
                for a in idx.get((i, ((j + 180) % 360) - 180), ()):
                    dd = _d(c, a)
                    if rmin <= dd <= r:
                        out.append(a)
        return out

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

    # ---- natural wonders -----------------------------------------------------
    def _compute_wonders(self):
        """Match every wonder in the world to the nearest runway you can use."""
        out = []
        for w in wonders_db.ALL:
            wp = wonders_db.waypoint(w)
            near = self.near_pool(w["lat"], w["lon"], WONDER_R)
            if not near:
                continue                       # nothing within reach in this scenery
            dest = min(near, key=lambda a: _d(wp, a))
            out.append({"src": "wonder", "title": w["name"], "tags": set(w["tags"]),
                        "text": w["text"], "sights": [wp], "stops": [dest], "overfly": [],
                        "wp": wp, "msl": w["msl"], "away": _d(wp, dest)})
        out.sort(key=lambda c: c["away"])
        self._wonders = out

    def wonders(self, tags=None, area="Whole world"):
        if self._wonders is None:
            self._compute_wonders()
        out = self._wonders
        if tags:
            out = [w for w in out if w["tags"] & set(tags)]
        if area and area != "Whole world":
            out = [w for w in out if in_area(w["wp"], area)]
        return out

    # ---- random: a dart thrown at the planet ---------------------------------
    def _relief_grid(self):
        """Roughest terrain in each half-degree cell, from the airport elevations."""
        if self._relief is None:
            cell, mx = 0.5, {}
            for a in self.all:
                k = (int(a["lat"] // cell), int(a["lon"] // cell))
                mx[k] = max(mx.get(k, -9999), a["elev"])
            self._relief = (cell, mx)
        return self._relief

    def interest(self, a):
        """How promising does this airport look, sight unseen? Returns (score, reasons)."""
        cell, mx = self._relief_grid()
        ci, cj = int(a["lat"] // cell), int(a["lon"] // cell)
        hi = max(mx.get((ci + i, cj + j), -9999) for i in (-1, 0, 1) for j in (-1, 0, 1))
        relief = hi - a["elev"]
        score, why, tags = 1.0, [], set()
        if relief >= 1500:
            score += min(4.0, relief / 1500.0)
            tags.add("mountains")
            why.append(f"ground about {round(relief, -2):,.0f} ft higher close by")
        if a["elev"] >= 5000:
            score += min(2.0, a["elev"] / 5000.0)
            tags.add("mountains")
            why.append(f"the field itself is at {a['elev']:,} ft")
        name = a["name"].upper()
        hits = 0
        for rx, tag, text in KEYWORDS:
            if rx.search(name) and hits < 2:
                tags.add(tag)
                score += 1.0
                hits += 1
                why.append(text)
        if any(r["s"] == "water" for r in a["rwys"]):
            score += 1.0
            tags.add("water")
            why.append("a water runway")
        if abs(a["lat"]) > 60:
            score += 1.0
            tags.add("ice")
            why.append("a high latitude, so long light and long shadows")
        if any(r["s"] in ("grass", "dirt", "gravel", "sand") for r in a["rwys"]):
            score += 0.5
            tags.add("bush")
            why.append("an unpaved runway")
        w = wonders_db.near(a["lat"], a["lon"], 70)
        if w:
            score += 2.5
            tags |= w[0][1]["tags"]
            why.append(f"{w[0][1]['name']} about {w[0][0]:.0f} nm away")
        return score, why, tags, (w[0][1] if w else None)

    def _pool_for(self, area):
        key = area or "Whole world"
        if key not in self._pools:
            p = list(self.gen.pool)
            if key != "Whole world":
                p = [a for a in p if in_area(a, key)]
            self._pools[key] = p
        return self._pools[key]

    def random_world(self, n=1, area="Whole world", tags=None, bias=True, fresh=True):
        """Somewhere random on earth. Not a list - a dart in the map.

        bias  - lean towards interesting ground rather than a flat field in Ohio
        fresh - don't hand back the same place twice in one session
        """
        rng = self.gen.rng
        pool = self._pool_for(area)
        if not pool:
            return []
        ideas, tries = [], 0
        while len(ideas) < n and tries < n * 40:
            tries += 1
            if bias:
                sample = [pool[rng.randrange(len(pool))] for _ in range(min(len(pool), 40))]
                scored = [(self.interest(a), a) for a in sample]
                scored.sort(key=lambda x: -x[0][0])
                (score, why, tg, wonder), dest = scored[0]
            else:
                dest = pool[rng.randrange(len(pool))]
                score, why, tg, wonder = self.interest(dest)
            if tags and not (tg & set(tags)):
                continue
            if fresh and dest["id"] in self._rand_seen:
                continue
            where = ", ".join(x for x in (dest.get("city"), dest.get("state"),
                                          dest.get("country") or dest.get("iso")) if x)
            text = (f"The dice picked {dest['id']} - {dest['name'].title()}"
                    + (f", {where}" if where else "") + ". "
                    + ("What's interesting about it: " + ", ".join(dict.fromkeys(why)) + "."
                       if why else "Nothing famous here at all, which is rather the point. "
                                   "Go and look at somewhere nobody flies."))
            cand = {"src": "random", "title": dest["name"].title(), "tags": tg or {"bush"},
                    "text": text, "sights": [dest], "stops": [dest], "overfly": [], "score": score}
            if wonder and rng.random() < 0.7:
                cand["wp"] = wonders_db.waypoint(wonder)
                cand["msl"] = wonder["msl"]
            idea = self.to_idea(cand)
            if idea:
                self._rand_seen.add(dest["id"])
                ideas.append(idea)
        return ideas

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
    def candidates(self, tags=None, area="Whole world", famous=True, gems=True, wonders=True):
        c = []
        if famous:
            c += self.famous(tags, area)
        if wonders:
            c += self.wonders(tags, area)
        if gems:
            c += self.gems(tags, area)[:600]
        return c

    def to_idea(self, cand):
        core, g, rng = self.core, self.gen, self.rng
        stops = list(cand["stops"])
        wp = cand.get("wp")
        if len(stops) == 1:
            dest = stops[0]
            R = min(self.ac["range"] * 0.4, 140)
            # With a wonder in the middle, measure from the wonder, so the route is
            # departure -> sight -> runway rather than a long detour on one side.
            anchor = wp or dest
            deps = ([a for a in self.near_pool(anchor["lat"], anchor["lon"], R, 25) if a["id"] != dest["id"]] or
                    [a for a in self.near_pool(anchor["lat"], anchor["lon"], R * 1.5, 8) if a["id"] != dest["id"]])
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
        # A natural wonder goes in as a waypoint between the last two stops: you fly
        # over the thing itself, then land at the nearest runway you can use.
        over = []
        if wp is not None and len(stops) >= 2:
            away = _d(wp, stops[-1])
            stops = stops[:-1] + [wp, stops[-1]]
            legs = sum(_d(stops[k], stops[k + 1]) for k in range(len(stops) - 1))
            if legs > self.ac["range"] * 0.85:
                return None                      # too far for this aeroplane to make sense of
            over.append(wp["id"])
            notes.insert(1, f"The sight itself is at {fmt_ll(wp['lat'], wp['lon'])} - there is no runway there. "
                            f"Fly over it, then land at {stops[-1]['id']} {stops[-1]['name'].title()}, "
                            f"{away:.0f} nm away. About {legs:.0f} nm in total.")
            msl = int(cand.get("msl") or 0)
            if msl:
                cross = int(round((msl + 1500) / 500.0) * 500)
                ceil = int(self.ac.get("ceiling") or 0)
                if ceil and msl + 500 > ceil:
                    notes.insert(2, f"This one tops out at about {msl:,} ft and your aircraft runs out of air "
                                    f"around {ceil:,} ft, so you are not going over it. Fly alongside instead, "
                                    f"a few miles off and well below the summit - which is the better view anyway.")
                else:
                    notes.insert(2, f"High ground here goes to about {msl:,} ft. Plan to cross no lower than "
                                    f"{cross:,} ft, and remember that big terrain makes its own weather and "
                                    f"its own downdraughts.")
        title = TITLES.get(cand["src"], "Scenic: ") + cand["title"]
        idea = core.Idea("scenic", title, stops, cand["text"], month=m, tod=tod, wx=wx, notes=notes,
                         wx_at=stops[-1], overfly=over)
        idea.scenic = cand
        return idea

    def surprise(self, n=1, tags=None, area="Whole world", famous=True, gems=True,
                 wonders=True, random_places=False):
        """A mixed handful from whichever sources are switched on."""
        piles = []
        if famous:
            piles.append((0.30, list(self.famous(tags, area))))
        if wonders:
            piles.append((0.34, list(self.wonders(tags, area))))
        if gems:
            piles.append((0.24, list(self.gems(tags, area))[:600]))
        piles = [(w, p) for w, p in piles if p]
        for _, p in piles:
            self.rng.shuffle(p)
        ideas, seen = [], set()
        rnd_share = 0.28 if random_places else 0.0
        guard = 0
        while len(ideas) < n and guard < n * 80 and (piles or random_places):
            guard += 1
            if random_places and (not piles or self.rng.random() < rnd_share):
                want = (n - len(ideas)) if not piles else 1
                got = self.random_world(max(1, want), area, tags)
                for gi in got:
                    k = gi.stops[-1]["id"] + "/" + gi.title
                    if k not in seen:
                        seen.add(k)
                        ideas.append(gi)
                if not piles and not got:
                    break                      # nowhere left to go
                continue
            total = sum(w for w, _ in piles)
            r, pick = self.rng.random() * total, piles[-1]
            for w, p in piles:
                r -= w
                if r <= 0:
                    pick = (w, p)
                    break
            c = pick[1].pop()
            if not pick[1]:
                piles = [x for x in piles if x[1]]
            key = c["stops"][-1]["id"] + "/" + c["title"]
            if key in seen:
                continue
            i = self.to_idea(c)
            if i:
                ideas.append(i)
                seen.add(key)
        return ideas
