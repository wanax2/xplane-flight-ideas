"""
xp_wonders.py - the scenic places themselves, not the airports.

FAMOUS (in xp_scenic.py) is a list of airports worth flying between. This file is
the other half: the *things you go to look at*. Waterfalls, volcanoes, glaciers,
gorges, reefs, ruins, sea cliffs - about four hundred of them, everywhere in the
world, each with a position, a height where it matters, and a line about what you
are looking at.

Very few of them have an airport. That's the point. The app finds the nearest
runway your aeroplane can actually use, then routes you over the place itself as
a waypoint. So Angel Falls, Everest, the Matterhorn, Uluru and the Grand Prismatic
Spring all become flights, even though you can't land at any of them.

Each entry is:

    (name, latitude, longitude, tags, what you are looking at, height in feet)

Height is the summit or rim elevation where that matters for terrain clearance,
and 0 where it doesn't (a lagoon, a beach, a city). Positions are good to a mile
or two - close enough to put the thing under your wing, not a survey reference.

Tags are the same ten used everywhere else in the app: mountains, islands, coast,
ice, desert, volcano, water, landmark, jungle, bush.
"""
from __future__ import annotations

import math
import re

# ======================================================================
# The list
# ======================================================================
WONDERS = [
    # ------------------------------------------------ United States: the West
    ("Grand Canyon", 36.06, -112.14, "desert landmark", "A mile deep and ten miles across; use the published SFRA corridors.", 7400),
    ("Horseshoe Bend", 36.879, -111.510, "desert water", "The Colorado doubling back on itself below Glen Canyon Dam.", 4200),
    ("Monument Valley", 36.98, -110.10, "desert landmark", "Sandstone buttes standing alone on the Navajo plateau.", 6000),
    ("Zion Canyon", 37.27, -112.95, "desert", "Sheer red walls with the Virgin River in the bottom.", 7800),
    ("Bryce Canyon", 37.62, -112.17, "desert", "An amphitheatre of orange hoodoos at 8,000 ft.", 9100),
    ("Delicate Arch", 38.744, -109.499, "desert landmark", "The arch everyone knows, with the La Sals behind it.", 4800),
    ("Canyonlands", 38.39, -109.86, "desert water", "Two rivers carving a maze into the Island in the Sky.", 6100),
    ("Capitol Reef", 38.29, -111.26, "desert", "A hundred-mile wrinkle in the earth's crust.", 7000),
    ("Mesa Verde", 37.18, -108.49, "desert landmark", "Cliff dwellings tucked under the canyon rims.", 8500),
    ("Shiprock", 36.687, -108.836, "desert landmark", "A volcanic neck rising 1,500 ft straight off the desert floor.", 7200),
    ("Meteor Crater", 35.027, -111.022, "desert landmark", "A mile-wide impact crater in the Arizona plain.", 5700),
    ("Cathedral Rock, Sedona", 34.82, -111.79, "desert", "Red rock spires around Oak Creek.", 5000),
    ("Havasu Falls", 36.255, -112.698, "desert water", "Blue-green travertine falls in a side canyon of the Grand Canyon.", 3200),
    ("Rainbow Bridge", 37.077, -110.964, "desert water landmark", "The world's largest natural bridge, above Lake Powell.", 4000),
    ("Hoover Dam", 36.016, -114.737, "desert landmark water", "The dam and the bypass bridge in Black Canyon.", 1300),
    ("Valley of Fire", 36.48, -114.52, "desert", "Red Aztec sandstone an hour from the Strip.", 2200),
    ("Badwater Basin", 36.230, -116.767, "desert", "The lowest point in North America, 282 ft below sea level.", 0),
    ("Racetrack Playa", 36.681, -117.562, "desert", "The dry lake where the rocks leave trails.", 3700),
    ("Mono Lake", 38.01, -119.01, "water desert", "Tufa towers in an inland sea under the Sierra crest.", 6400),
    ("Half Dome, Yosemite", 37.746, -119.533, "mountains landmark", "The valley, the falls and the granite face.", 8840),
    ("Mount Whitney", 36.578, -118.292, "mountains", "The highest peak in the lower 48, straight up from Owens Valley.", 14505),
    ("Lake Tahoe", 39.09, -120.04, "water mountains", "Cobalt blue, ringed by the Sierra.", 6230),
    ("Crater Lake", 42.941, -122.109, "volcano water", "A caldera filled with the deepest, bluest water in the country.", 8160),
    ("Mount Shasta", 41.409, -122.195, "volcano mountains", "A lone 14,000 ft stratovolcano in northern California.", 14179),
    ("Mount Rainier", 46.853, -121.760, "volcano ice mountains", "Twenty-five glaciers on one mountain, an hour from Seattle.", 14411),
    ("Mount St Helens", 46.191, -122.195, "volcano", "The blast zone and the crater, still steaming.", 8363),
    ("Mount Hood", 45.374, -121.696, "volcano ice", "Oregon's cone above the Columbia.", 11249),
    ("Columbia River Gorge", 45.576, -122.116, "water landmark", "Waterfalls down both walls of a gorge cut through the Cascades.", 4000),
    ("Cape Flattery", 48.384, -124.714, "coast", "The northwest corner of the continental United States.", 0),
    ("Haystack Rock", 45.885, -123.968, "coast", "A sea stack on the Oregon beach at Cannon Beach.", 0),
    ("Golden Gate Bridge", 37.820, -122.478, "landmark coast", "Best with the fog pouring through the gap.", 0),
    ("Bixby Bridge, Big Sur", 36.372, -121.902, "coast", "The bridge and the cliffs of the Big Sur coast.", 0),
    ("Point Reyes", 38.00, -123.02, "coast", "A headland sliding north on the San Andreas fault.", 0),
    ("Channel Islands", 34.01, -119.75, "islands coast", "Five islands off Ventura, the American Galapagos.", 0),
    ("Grand Prismatic Spring", 44.525, -110.838, "volcano landmark", "Yellowstone's rainbow hot spring, best from the air.", 7300),
    ("Grand Teton", 43.741, -110.802, "mountains", "The range rises 7,000 ft off the valley floor with no foothills.", 13775),
    ("Devils Tower", 44.590, -104.715, "landmark desert", "A column of fluted rock out of the Wyoming grass.", 5112),
    ("Mount Rushmore", 43.879, -103.459, "landmark mountains", "Four faces in the granite of the Black Hills.", 5700),
    ("Badlands", 43.85, -102.34, "desert", "Eroded spires and prairie in South Dakota.", 3300),
    ("Going-to-the-Sun, Glacier NP", 48.70, -113.72, "mountains ice", "Hanging valleys, turquoise lakes and the last glaciers.", 10500),
    ("Craters of the Moon", 43.42, -113.52, "volcano desert", "Black lava flows across the Snake River plain.", 6000),
    ("Hells Canyon", 45.25, -116.72, "water mountains", "The deepest river gorge in North America.", 8000),
    ("Sawtooth Range", 44.15, -114.93, "mountains bush", "Granite peaks and backcountry strips in central Idaho.", 10751),
    ("Great Sand Dunes", 37.73, -105.51, "desert mountains", "750 ft dunes piled against the Sangre de Cristos.", 8700),
    ("Maroon Bells", 39.071, -106.989, "mountains", "The most photographed peaks in Colorado.", 14163),
    ("Pikes Peak", 38.841, -105.043, "mountains", "The fourteener that looks over Colorado Springs.", 14115),
    ("Black Canyon of the Gunnison", 38.57, -107.72, "desert water", "A gorge so narrow and deep the bottom barely sees the sun.", 8300),
    ("Guadalupe Peak", 31.891, -104.860, "mountains desert", "A fossil reef standing over the Chihuahuan desert.", 8751),
    ("Santa Elena Canyon", 29.17, -103.61, "desert water", "The Rio Grande between 1,500 ft limestone walls.", 3700),
    ("White Sands", 32.78, -106.33, "desert", "Gypsum dunes, blinding white, in the Tularosa basin.", 4000),
    ("Bonneville Salt Flats", 40.76, -113.88, "desert", "Flat, white and perfectly level for thirty miles.", 4200),
    ("Great Salt Lake", 41.17, -112.55, "water desert", "Pink and blue brine either side of the causeway.", 4200),
    ("Canyon de Chelly", 36.13, -109.47, "desert landmark", "Spider Rock and the cliff dwellings on Navajo land.", 6500),
    ("Yosemite High Sierra", 37.85, -119.30, "mountains water", "Tuolumne Meadows, granite domes and alpine lakes.", 12000),
    ("Glacier Peak", 48.112, -121.113, "volcano ice", "The most remote volcano in the Cascades.", 10541),
    ("Olympic rainforest", 47.80, -123.90, "jungle mountains", "Moss, rain and the Hoh valley under Mount Olympus.", 7980),
    # ------------------------------------------------ United States: East and Gulf
    ("Niagara Falls", 43.081, -79.075, "water landmark", "Horseshoe Falls and the gorge below; check the airspace first.", 600),
    ("Statue of Liberty", 40.689, -74.045, "landmark coast", "The classic Hudson corridor turning point.", 0),
    ("Manhattan", 40.758, -73.985, "landmark", "Midtown from 1,000 ft in the VFR corridor.", 0),
    ("Cape Hatteras", 35.25, -75.53, "coast islands", "The lighthouse and Diamond Shoals on the Outer Banks.", 0),
    ("Ten Thousand Islands", 25.85, -81.35, "jungle coast water", "Mangrove islands where the Everglades meets the Gulf.", 0),
    ("Dry Tortugas", 24.628, -82.873, "islands coast landmark", "Fort Jefferson on a sandbar 70 miles past Key West.", 0),
    ("Clingmans Dome", 35.563, -83.498, "mountains jungle", "The Smokies in their morning haze.", 6643),
    ("Mount Washington", 44.271, -71.303, "mountains", "Home of the worst weather in the world - treat it seriously.", 6288),
    ("Cadillac Mountain, Acadia", 44.353, -68.224, "coast mountains", "First sunrise in the United States, over the Maine islands.", 1530),
    ("Hopewell Rocks", 45.82, -64.58, "coast", "Flowerpot rocks in the world's biggest tides.", 0),
    ("Cape Breton Highlands", 46.80, -60.66, "coast mountains", "The Cabot Trail where the highlands drop into the Atlantic.", 1700),
    ("Gros Morne", 49.60, -57.75, "mountains water", "Fjord lakes and exposed mantle rock in Newfoundland.", 2644),
    ("Peggy's Cove", 44.492, -63.917, "coast landmark", "Granite, surf and the most painted lighthouse in Canada.", 0),
    ("Chesapeake Bay Bridge-Tunnel", 37.03, -76.08, "landmark coast", "Seventeen miles of bridge that dives underwater twice.", 0),
    ("Okefenokee Swamp", 30.74, -82.30, "jungle water", "Black water, cypress and gators on the Georgia line.", 0),
    ("Mississippi Delta", 29.15, -89.25, "water coast", "The bird's foot where the river finally gives up.", 0),
    ("Pictured Rocks", 46.55, -86.46, "coast water", "Painted sandstone cliffs on Lake Superior.", 600),
    ("Isle Royale", 48.00, -88.82, "islands water", "A wilderness island in the middle of Lake Superior.", 1394),
    ("Apostle Islands", 46.93, -90.65, "islands water", "Sea caves and lighthouses in Wisconsin's corner of Superior.", 600),
    # ------------------------------------------------ Canada
    ("Moraine Lake", 51.322, -116.186, "mountains water", "Ten peaks above impossible turquoise water.", 6180),
    ("Lake Louise", 51.417, -116.216, "mountains water ice", "The lake, the chateau and the Victoria Glacier.", 5680),
    ("Columbia Icefield", 52.19, -117.25, "ice mountains", "The hydrological apex of North America.", 11450),
    ("Mount Robson", 53.107, -119.156, "mountains ice", "The highest peak in the Canadian Rockies, and it looks it.", 12972),
    ("Bugaboos", 50.75, -116.75, "mountains ice", "Granite spires out of a glacier in the Purcells.", 10512),
    ("Virginia Falls, Nahanni", 61.603, -125.777, "water bush", "Twice the height of Niagara, in the middle of nowhere.", 2100),
    ("Mount Logan", 60.567, -140.405, "ice mountains", "Canada's highest, in the largest icefield outside the poles.", 19551),
    ("Kluane icefields", 60.75, -139.50, "ice mountains", "An ocean of ice and unnamed peaks in the Yukon.", 15000),
    ("Torngat Mountains", 59.00, -63.90, "mountains ice coast", "Fjords and bare rock at the top of Labrador.", 5420),
    ("Dinosaur Provincial Park", 50.77, -111.51, "desert", "Alberta badlands cut into the prairie.", 2400),
    ("Athabasca sand dunes", 59.10, -108.40, "desert water", "The most northerly major dune field in the world.", 700),
    ("Bay of Fundy tidal bore", 45.36, -64.30, "coast water", "Fifty-foot tides running up the rivers.", 0),
    ("Thousand Islands", 44.34, -75.93, "islands water", "Castles and cottages on rocks in the St Lawrence.", 300),
    ("Churchill and the barrens", 58.77, -94.17, "ice bush coast", "Tundra, Hudson Bay and polar bears.", 100),
    ("Auyuittuq / Mount Thor", 66.53, -65.33, "ice mountains", "The greatest vertical drop on earth, on Baffin Island.", 5495),
    # ------------------------------------------------ Alaska
    ("Denali", 63.069, -151.007, "mountains ice", "20,310 ft, and it rises further from its base than Everest.", 20310),
    ("Ruth Glacier", 62.87, -150.85, "ice mountains", "The Great Gorge - a mile of granite either side of the ice.", 5000),
    ("Knik Glacier", 61.20, -148.60, "ice mountains", "A wall of ice calving into a lake an hour from Anchorage.", 1000),
    ("Columbia Glacier", 61.10, -147.05, "ice water", "Tidewater ice retreating into Prince William Sound.", 0),
    ("Hubbard Glacier", 60.02, -139.47, "ice water", "Six miles of calving face at the head of Yakutat Bay.", 0),
    ("Mendenhall Glacier", 58.43, -134.55, "ice water", "The glacier at the edge of Juneau.", 0),
    ("Tracy Arm", 57.85, -133.40, "ice water coast", "A narrow fjord full of icebergs and waterfalls.", 0),
    ("Misty Fjords", 55.60, -130.75, "water coast jungle", "Granite walls out of saltwater in the Alaskan rainforest.", 3000),
    ("Valley of Ten Thousand Smokes", 58.27, -155.16, "volcano desert", "Ash flats from the biggest eruption of the 20th century.", 2500),
    ("Lake Clark Pass", 60.75, -153.00, "mountains ice", "The classic bush route through the Chigmit Mountains.", 1000),
    ("Arrigetch Peaks", 67.42, -154.25, "mountains bush", "Granite fingers in the Brooks Range, north of the Arctic Circle.", 7200),
    ("Mount Redoubt", 60.485, -152.743, "volcano ice", "An active volcano across Cook Inlet from Anchorage.", 10197),
    ("Wrangell-St Elias", 61.40, -142.00, "ice mountains", "Nine of the sixteen highest peaks in the United States.", 18008),
    ("Bering Glacier", 60.15, -143.30, "ice water", "The largest glacier in North America.", 500),
    ("Aniakchak caldera", 56.88, -158.17, "volcano", "A six-mile caldera on the Alaska Peninsula that almost nobody visits.", 4400),
    # ------------------------------------------------ Hawaii and the Pacific
    ("Kilauea", 19.421, -155.287, "volcano islands", "The most active volcano on earth; check the TFRs.", 4090),
    ("Mauna Kea", 19.821, -155.468, "volcano mountains", "Observatories at 13,800 ft above the Pacific.", 13803),
    ("Na Pali coast", 22.17, -159.67, "coast islands", "Fluted green cliffs with no road behind them.", 4000),
    ("Waimea Canyon", 22.07, -159.66, "desert islands", "The Grand Canyon of the Pacific, in red and green.", 3600),
    ("Haleakala", 20.709, -156.253, "volcano islands", "A crater you can see the curve of the earth from.", 10023),
    ("Kalaupapa cliffs", 21.19, -156.98, "coast islands", "The highest sea cliffs in the world, on Molokai.", 3600),
    ("Molokini", 20.632, -156.496, "islands coast volcano", "A crescent of crater rim in clear water off Maui.", 0),
    ("Bora Bora", -16.50, -151.74, "islands coast", "The lagoon that every other lagoon is compared to.", 2385),
    ("Moorea", -17.53, -149.83, "islands volcano", "Two bays and a wall of green spires.", 3960),
    ("Rangiroa", -15.15, -147.70, "islands coast", "An atoll so big the far side is over the horizon.", 0),
    ("Aitutaki", -18.86, -159.79, "islands coast", "A triangle of blue in the Cook Islands.", 0),
    ("Mount Yasur", -19.532, 169.442, "volcano islands", "Vanuatu's permanently erupting cone - spectacular at dusk.", 1184),
    ("Yasawa Islands", -17.00, 177.20, "islands coast", "The Fijian chain, blue all the way down.", 0),
    ("Vava'u", -18.65, -173.98, "islands coast", "Tongan limestone islands and whale water.", 0),
    ("Rock Islands, Palau", 7.15, 134.37, "islands coast", "Mushroom-shaped islands over a turquoise floor.", 0),
    ("Chuuk lagoon", 7.42, 151.78, "islands coast", "A ring of reef around a sunken Japanese fleet.", 0),
    ("New Caledonia lagoon", -22.30, 166.40, "islands coast", "The largest lagoon in the world, with the Heart of Voh in it.", 0),
    # ------------------------------------------------ Mexico, Central America, Caribbean
    ("Popocatepetl", 19.023, -98.628, "volcano mountains", "A smoking 17,800 ft cone beside Mexico City.", 17802),
    ("Pico de Orizaba", 19.030, -97.269, "volcano ice", "The highest mountain in Mexico, glaciated and lonely.", 18491),
    ("Copper Canyon", 27.40, -107.70, "desert mountains", "Deeper and bigger than the Grand Canyon, and far less flown.", 8000),
    ("El Arco, Cabo", 22.871, -109.892, "coast desert landmark", "Land's End where the Pacific meets the Sea of Cortez.", 0),
    ("Chichen Itza", 20.683, -88.569, "landmark jungle", "El Castillo above the Yucatan scrub.", 100),
    ("Great Blue Hole", 17.316, -87.535, "coast water islands", "A perfect dark circle in the Belize barrier reef.", 0),
    ("Arenal", 10.463, -84.703, "volcano jungle", "A textbook cone above the Costa Rican rainforest.", 5479),
    ("Panama Canal locks", 9.27, -79.92, "landmark water", "Ships climbing a staircase between two oceans.", 0),
    ("Lake Atitlan", 14.69, -91.20, "volcano water", "Three volcanoes around a caldera lake in Guatemala.", 11604),
    ("Vinales valley", 22.62, -83.71, "jungle landmark", "Limestone mogotes over Cuban tobacco fields.", 1300),
    ("Exuma Cays", 24.30, -76.55, "islands coast", "Sandbars and shallows in every shade of blue there is.", 0),
    ("Tongue of the Ocean", 24.40, -77.70, "coast water", "A 6,000 ft trench right beside the Bahamian shallows.", 0),
    ("The Pitons", 13.81, -61.06, "islands volcano", "Two volcanic plugs straight out of the sea in St Lucia.", 2618),
    ("Soufriere Hills", 16.712, -62.181, "volcano islands", "The volcano that buried Montserrat's capital.", 3002),
    ("Saba", 17.63, -63.23, "islands volcano", "A cone with the shortest commercial runway in the world on its shoulder.", 2910),
    ("Los Roques", 11.85, -66.75, "islands coast", "A Venezuelan atoll of white sand and reef.", 0),
    ("El Yunque", 18.31, -65.79, "jungle mountains", "Rainforest and cloud on the eastern end of Puerto Rico.", 3494),
    # ------------------------------------------------ South America
    ("Angel Falls", 5.969, -62.536, "water jungle landmark", "The highest waterfall on earth, off a tepui wall.", 8200),
    ("Mount Roraima", 5.143, -60.762, "jungle landmark", "A flat-topped island in the sky where three countries meet.", 9219),
    ("Kaieteur Falls", 5.175, -59.483, "water jungle", "A single 740 ft drop in the Guyanese rainforest.", 1400),
    ("Meeting of the Waters", -3.13, -59.90, "water jungle", "Black and brown rivers running side by side for miles.", 0),
    ("Iguazu Falls", -25.687, -54.445, "water jungle landmark", "275 falls in a horseshoe, with the Devil's Throat in the middle.", 700),
    ("Pantanal", -17.70, -57.00, "water jungle bush", "The biggest wetland on earth, and the wildlife to match.", 300),
    ("Sugarloaf, Rio", -22.949, -43.157, "landmark coast", "The harbour, the beaches and the granite.", 1299),
    ("Christ the Redeemer", -22.952, -43.211, "landmark mountains", "Corcovado above Rio.", 2329),
    ("Lencois Maranhenses", -2.49, -43.13, "desert water coast", "White dunes with blue rain lagoons between them.", 0),
    ("Fernando de Noronha", -3.854, -32.428, "islands coast volcano", "A volcanic island 200 miles off Brazil.", 1089),
    ("Salar de Uyuni", -20.13, -67.49, "desert", "The world's largest salt flat, a mirror when it's wet.", 11995),
    ("Laguna Colorada", -22.19, -67.79, "desert water", "A red lake full of flamingos at 14,000 ft.", 14000),
    ("Lake Titicaca", -15.85, -69.33, "water mountains", "The highest navigable lake in the world.", 12507),
    ("Machu Picchu", -13.163, -72.545, "landmark mountains", "The citadel on the ridge above the Urubamba.", 7970),
    ("Colca Canyon", -15.61, -71.92, "desert mountains", "Twice the depth of the Grand Canyon, with condors in it.", 10700),
    ("Nazca Lines", -14.739, -75.130, "desert landmark", "Figures scratched into the pampa, only readable from the air.", 1700),
    ("Rainbow Mountain", -13.87, -71.30, "mountains desert", "Striped sediment at 17,000 ft in the Peruvian Andes.", 17060),
    ("Cordillera Blanca", -9.121, -77.604, "ice mountains", "The highest tropical mountain range on earth.", 22205),
    ("Cotopaxi", -0.684, -78.437, "volcano ice", "A glaciated cone on the equator.", 19347),
    ("Chimborazo", -1.469, -78.817, "volcano ice", "The point on earth furthest from its centre.", 20549),
    ("Quilotoa", -0.858, -78.900, "volcano water", "A green crater lake in the Ecuadorian Andes.", 12841),
    ("Isabela, Galapagos", -0.60, -91.10, "islands volcano", "Six volcanoes fused into a seahorse-shaped island.", 5600),
    ("Torres del Paine", -50.94, -73.41, "mountains ice", "Granite towers over Patagonian steppe.", 9350),
    ("Perito Moreno Glacier", -50.48, -73.04, "ice water", "A three-mile ice face that calves while you watch.", 1000),
    ("Fitz Roy", -49.271, -73.043, "mountains ice", "The hardest-looking mountain in the world.", 11171),
    ("Aconcagua", -32.653, -70.011, "mountains ice", "The highest peak outside Asia, on the classic Andes crossing.", 22838),
    ("Osorno", -41.100, -72.493, "volcano water", "A perfect cone above the Chilean lakes.", 8701),
    ("Villarrica", -39.420, -71.939, "volcano ice", "Snow on top, lava in the crater.", 9341),
    ("Valle de la Luna", -22.92, -68.28, "desert", "Atacama salt and sand, the driest place on earth.", 8000),
    ("Cape Horn", -55.98, -67.27, "coast islands", "The last rock before Antarctica.", 1391),
    ("Beagle Channel", -54.87, -68.30, "water mountains coast", "Glaciers down both sides of Darwin's channel.", 0),
    ("Marble Caves", -46.63, -72.06, "water landmark", "Blue-veined marble hollowed out by Lake General Carrera.", 700),
    ("Easter Island", -27.11, -109.35, "islands landmark", "Moai facing inland on the loneliest island there is.", 1670),
    ("Cano Cristales", 2.27, -73.79, "water jungle", "The river that turns red for a few weeks a year.", 1500),
    ("Cocora valley", 4.64, -75.49, "mountains jungle", "200 ft wax palms on Colombian hillsides.", 8000),
    ("Sierra Nevada de Santa Marta", 10.84, -73.69, "mountains coast", "Snow peaks 25 miles from a Caribbean beach.", 18700),
    ("Tepuis of the Gran Sabana", 5.60, -61.50, "jungle landmark", "Table mountains standing out of the savannah.", 8500),
    # ------------------------------------------------ Europe: the Alps
    ("Matterhorn", 45.977, 7.658, "mountains ice", "The most recognisable mountain on earth.", 14692),
    ("Mont Blanc", 45.833, 6.865, "mountains ice", "The roof of western Europe, with the Bossons glacier below.", 15774),
    ("Eiger and Jungfrau", 46.577, 7.962, "mountains ice", "The north face, the Jungfraujoch and the Aletsch behind.", 13642),
    ("Aletsch Glacier", 46.45, 8.07, "ice mountains", "The longest glacier in the Alps, fourteen miles of it.", 11000),
    ("Lauterbrunnen valley", 46.594, 7.909, "mountains water", "Seventy-two waterfalls off vertical walls.", 2600),
    ("Lake Como", 46.00, 9.26, "water mountains", "An upside-down Y of deep water under the Alps.", 650),
    ("Tre Cime di Lavaredo", 46.618, 12.305, "mountains", "Three limestone towers, the signature of the Dolomites.", 9840),
    ("Lake Garda", 45.70, 10.72, "water mountains", "Cliffs at the north end, vineyards at the south.", 215),
    ("Grossglockner", 47.075, 12.694, "mountains ice", "Austria's highest, with the Pasterze glacier under it.", 12461),
    ("Zugspitze and the Eibsee", 47.421, 10.985, "mountains water", "Germany's highest peak above a green lake.", 9718),
    ("Neuschwanstein", 47.558, 10.750, "landmark mountains", "The castle in the Bavarian foothills.", 3200),
    ("Hallstatt", 47.562, 13.649, "water mountains landmark", "A village squeezed between a lake and a cliff.", 1700),
    ("Triglav", 46.379, 13.837, "mountains", "The pyramid at the heart of the Julian Alps.", 9396),
    ("Lake Bled", 46.363, 14.094, "water landmark", "An island church in a lake under a castle.", 1600),
    ("Verdon Gorge", 43.75, 6.36, "water desert", "Europe's Grand Canyon, in Provence limestone.", 3000),
    ("Mer de Glace", 45.895, 6.930, "ice mountains", "Chamonix's great glacier, seen from above.", 8000),
    # ------------------------------------------------ Europe: Mediterranean
    ("Cinque Terre", 44.12, 9.72, "coast landmark", "Five villages stacked on the Ligurian cliffs.", 0),
    ("Amalfi coast", 40.63, 14.60, "coast", "Switchbacks, lemon terraces and blue water.", 0),
    ("Mount Vesuvius", 40.821, 14.426, "volcano landmark", "The crater above Naples, with Pompeii below.", 4203),
    ("Mount Etna", 37.751, 14.993, "volcano ice", "Europe's biggest active volcano, often with snow and smoke at once.", 11014),
    ("Stromboli", 38.789, 15.213, "volcano islands", "A cone that throws lava every twenty minutes.", 3031),
    ("Capri", 40.551, 14.242, "islands coast", "Faraglioni rocks in the Bay of Naples.", 1932),
    ("Venice lagoon", 45.434, 12.339, "landmark water", "The city, the Grand Canal and the sandbars.", 0),
    ("Plitvice Lakes", 44.881, 15.616, "water jungle", "Sixteen terraced lakes joined by waterfalls.", 2000),
    ("Bay of Kotor", 42.47, 18.69, "coast mountains water", "Europe's southernmost fjord-shaped bay.", 5700),
    ("Meteora", 39.715, 21.630, "landmark mountains", "Monasteries on top of sandstone pillars.", 1800),
    ("Santorini caldera", 36.404, 25.396, "volcano islands coast", "White villages on the rim of a drowned volcano.", 1850),
    ("Navagio Bay", 37.859, 20.625, "coast islands", "A shipwreck on a beach with no land access.", 0),
    ("Mount Olympus", 40.085, 22.359, "mountains", "Home of the gods, straight up from the Aegean.", 9573),
    ("Cappadocia", 38.643, 34.830, "desert landmark", "Fairy chimneys, rock churches and a sky full of balloons at dawn.", 4000),
    ("Pamukkale", 37.924, 29.121, "landmark desert", "White travertine terraces above the Turkish plain.", 1200),
    ("Mount Ararat", 39.702, 44.298, "volcano ice mountains", "A glaciated cone 14,000 ft above the surrounding plateau.", 16854),
    ("Alhambra", 37.176, -3.588, "landmark mountains", "The palace with the Sierra Nevada behind it.", 2600),
    ("Ronda gorge", 36.741, -5.166, "landmark desert", "A town split by a 400 ft cleft with a bridge across it.", 2400),
    ("Rock of Gibraltar", 36.144, -5.343, "landmark coast", "1,400 ft of limestone with a runway across its neck.", 1398),
    ("Ponta da Piedade", 37.079, -8.669, "coast", "Sea arches and stacks on the Algarve.", 0),
    ("Douro valley", 41.16, -7.55, "water landmark", "Terraced vineyards down to the river.", 1500),
    ("Picos de Europa", 43.19, -4.85, "mountains", "Limestone peaks fifteen miles from the Bay of Biscay.", 8688),
    ("Cirque de Gavarnie", 42.694, -0.009, "mountains water", "A 4,000 ft amphitheatre with Europe's tallest waterfall.", 9500),
    ("Sierra Nevada, Spain", 37.05, -3.31, "mountains ice", "Snow above the Mediterranean.", 11424),
    ("Calanques", 43.21, 5.44, "coast", "White limestone inlets between Marseille and Cassis.", 1200),
    ("Etretat cliffs", 49.707, 0.201, "coast landmark", "Chalk arches and a needle in the Channel.", 300),
    ("Mont Saint-Michel", 48.636, -1.511, "landmark coast", "An abbey on a rock in the tidal flats.", 300),
    # ------------------------------------------------ Europe: Atlantic islands
    ("Sete Cidades, Azores", 37.860, -25.788, "volcano islands water", "Twin crater lakes, one green and one blue.", 2900),
    ("Pico", 38.468, -28.399, "volcano islands", "Portugal's highest peak, straight out of the Atlantic.", 7713),
    ("Ponta de Sao Lourenco", 32.743, -16.693, "coast islands", "Madeira's bare eastern tail in the swell.", 500),
    ("Teide", 28.272, -16.642, "volcano islands", "Spain's highest mountain, in a caldera above the clouds.", 12198),
    ("Timanfaya", 29.010, -13.756, "volcano islands", "Lanzarote's fire mountains, still hot underfoot.", 1700),
    ("Cumbre Vieja, La Palma", 28.57, -17.84, "volcano islands", "The ridge that erupted in 2021, above the Atlantic.", 6400),
    ("Sorvagsvatn", 62.071, -7.320, "islands water coast", "The Faroese lake that looks like it floats above the ocean.", 300),
    # ------------------------------------------------ Europe: Britain and Ireland
    ("Giant's Causeway", 55.241, -6.512, "coast landmark", "Forty thousand basalt columns at the water's edge.", 300),
    ("Cliffs of Moher", 52.972, -9.426, "coast", "700 ft of Atlantic cliff in County Clare.", 700),
    ("Skellig Michael", 51.771, -10.540, "islands coast landmark", "A monastery on a pinnacle eight miles offshore.", 714),
    ("Old Man of Storr", 57.507, -6.181, "mountains islands", "The Trotternish ridge on Skye.", 2359),
    ("Ben Nevis", 56.797, -5.003, "mountains", "Britain's highest, with a 2,000 ft north face.", 4413),
    ("Glencoe", 56.67, -5.00, "mountains water", "The most dramatic glen in Scotland.", 3766),
    ("Loch Ness", 57.32, -4.42, "water landmark", "Twenty-three miles of the Great Glen fault.", 50),
    ("St Kilda", 57.815, -8.578, "islands coast", "Britain's tallest sea cliffs, 40 miles out in the Atlantic.", 1410),
    ("Durdle Door", 50.621, -2.276, "coast landmark", "A limestone arch on the Jurassic Coast.", 0),
    ("White Cliffs of Dover", 51.135, 1.363, "coast landmark", "Chalk, with France on the horizon.", 350),
    ("Stonehenge", 51.179, -1.826, "landmark", "The stones on Salisbury Plain.", 340),
    ("Land's End", 50.066, -5.715, "coast", "The last of England, and the Longships light.", 200),
    ("Snowdon", 53.068, -4.076, "mountains", "Wales' highest, with the Llanberis pass beside it.", 3560),
    ("Scafell Pike", 54.454, -3.212, "mountains water", "The Lake District from the top.", 3209),
    # ------------------------------------------------ Europe: Nordic
    ("Preikestolen", 58.986, 6.190, "water mountains", "A flat rock 1,900 ft above the Lysefjord.", 1982),
    ("Trolltunga", 60.124, 6.740, "water mountains", "A stone tongue over Ringedalsvatnet.", 3600),
    ("Geirangerfjord", 62.10, 7.10, "water mountains", "The Seven Sisters falling straight into the fjord.", 5000),
    ("Trollstigen", 62.456, 7.671, "mountains landmark", "Eleven hairpins up a wall of rock.", 2790),
    ("Atlantic Road", 63.015, 7.353, "coast landmark", "A road that hops between skerries on eight bridges.", 0),
    ("Reine, Lofoten", 67.933, 13.088, "islands mountains coast", "Red cabins under granite spires above the Arctic Circle.", 1500),
    ("Nordkapp", 71.171, 25.784, "coast", "The cliff at the top of Europe.", 1007),
    ("Longyearbyen glaciers", 78.22, 15.65, "ice", "Svalbard - ice, coal and polar bears at 78 north.", 3000),
    ("Jostedalsbreen", 61.66, 7.00, "ice mountains", "The largest icecap on mainland Europe.", 6000),
    ("Kjeragbolten", 59.035, 6.593, "mountains water", "A boulder wedged in a crack 3,200 ft above the fjord.", 3228),
    ("Sognefjord", 61.10, 6.60, "water mountains", "The longest and deepest fjord in Norway.", 0),
    ("Kebnekaise", 67.902, 18.516, "ice mountains", "Sweden's highest peak, losing height as its glacier melts.", 6880),
    ("Abisko", 68.35, 18.78, "ice water", "The Lapporten gap and a famously clear aurora sky.", 3000),
    ("Saimaa", 61.30, 28.30, "water", "A Finnish lake with 14,000 islands in it.", 250),
    # ------------------------------------------------ Iceland
    ("Gullfoss", 64.327, -20.120, "water", "A two-step fall into a canyon on the Golden Circle.", 350),
    ("Geysir", 64.313, -20.302, "landmark water", "The hot spring all the others are named after.", 400),
    ("Eyjafjallajokull", 63.633, -19.605, "volcano ice", "The one that stopped Europe flying in 2010.", 5417),
    ("Jokulsarlon", 64.048, -16.179, "ice water", "Icebergs drifting out to a black beach.", 0),
    ("Skogafoss", 63.532, -19.511, "water", "A 200 ft curtain off the old sea cliff.", 300),
    ("Dettifoss", 65.814, -16.384, "water", "The most powerful waterfall in Europe.", 1200),
    ("Landmannalaugar", 63.988, -19.061, "volcano desert", "Rhyolite hills in orange, green and pink.", 2000),
    ("Fagradalsfjall", 63.899, -22.272, "volcano", "The Reykjanes fires, minutes from Keflavik.", 1200),
    ("Latrabjarg", 65.503, -24.531, "coast islands", "Europe's biggest bird cliff, in the Westfjords.", 1450),
    ("Kirkjufell", 64.927, -23.307, "mountains coast", "The most photographed mountain in Iceland.", 1519),
    ("Vatnajokull", 64.40, -16.80, "ice volcano", "Europe's largest icecap, with volcanoes underneath it.", 6920),
    ("Askja", 65.03, -16.75, "volcano desert", "A caldera in the highland desert, where Apollo crews trained.", 4750),
    # ------------------------------------------------ Europe: East
    ("High Tatras", 49.179, 20.088, "mountains", "A small, sharp alpine range on the Polish-Slovak border.", 8711),
    ("Transfagarasan", 45.60, 24.62, "mountains landmark", "A road switchbacking over the Carpathians.", 6700),
    ("Danube Delta", 45.15, 29.35, "water jungle", "Where the Danube finally spreads out into reeds and channels.", 0),
    ("Bohemian Switzerland", 50.88, 14.28, "mountains jungle", "Sandstone arches and gorges on the German-Czech border.", 2400),
    ("Mount Elbrus", 43.355, 42.439, "mountains ice", "Two glaciated cones, the highest in Europe.", 18510),
    ("Solovetsky Islands", 65.03, 35.71, "islands water", "A monastery-fortress in the White Sea.", 200),
    # ------------------------------------------------ Africa
    ("Victoria Falls", -17.925, 25.858, "water landmark", "A mile of river falling into a slot; the spray is visible for miles.", 3000),
    ("Okavango Delta", -19.28, 22.90, "water bush jungle", "A river that dies in the desert and fills it with wildlife.", 3000),
    ("Kilimanjaro", -3.067, 37.355, "volcano ice mountains", "Snow on the equator, 16,000 ft above the plain.", 19341),
    ("Mount Kenya", -0.152, 37.308, "mountains ice", "Glaciated spires on the equator.", 17057),
    ("Ngorongoro Crater", -3.17, 35.58, "volcano bush", "A caldera with its own ecosystem inside.", 7500),
    ("Serengeti", -2.33, 34.83, "bush", "Grass to the horizon, and the migration crossing it.", 5000),
    ("Lake Natron", -2.41, 36.00, "water desert", "Blood-red soda water and flamingos.", 2000),
    ("Ol Doinyo Lengai", -2.764, 35.914, "volcano", "The only volcano that erupts black carbonatite lava.", 9711),
    ("Mount Nyiragongo", -1.522, 29.249, "volcano", "A permanent lava lake in the Virungas.", 11385),
    ("Table Mountain", -33.957, 18.403, "landmark mountains coast", "The tablecloth pouring over the edge above Cape Town.", 3563),
    ("Cape of Good Hope", -34.357, 18.472, "coast", "Where the peninsula finally runs out.", 800),
    ("Drakensberg Amphitheatre", -28.70, 28.90, "mountains water", "A three-mile wall of rock with Tugela Falls down it.", 10800),
    ("Blyde River Canyon", -24.58, 30.80, "desert water jungle", "The world's largest green canyon.", 6000),
    ("Sossusvlei", -24.727, 15.344, "desert", "Orange dunes 1,000 ft high with white pans between them.", 2000),
    ("Skeleton Coast", -20.50, 13.20, "desert coast", "Fog, shipwrecks and dunes running into the Atlantic.", 0),
    ("Fish River Canyon", -27.60, 17.62, "desert water", "The second largest canyon in the world.", 3500),
    ("Kolmanskop", -26.70, 15.23, "desert landmark", "A diamond town being swallowed by the Namib.", 300),
    ("Tassili n'Ajjer", 25.50, 9.00, "desert landmark", "Sandstone forests and 10,000-year-old rock art in the Sahara.", 7500),
    ("Erg Chebbi", 31.10, -4.00, "desert", "Classic Saharan dunes on the Moroccan-Algerian border.", 2000),
    ("Todra Gorge", 31.58, -5.60, "desert mountains", "A 500 ft slot in the High Atlas.", 5000),
    ("Toubkal", 31.061, -7.915, "mountains", "North Africa's highest peak, an hour from Marrakech.", 13671),
    ("Valley of the Kings", 25.740, 32.601, "desert landmark water", "The Nile, the green strip, and the tombs in the hills.", 300),
    ("Abu Simbel", 22.337, 31.626, "desert landmark water", "Ramses' temples, moved stone by stone above Lake Nasser.", 600),
    ("Pyramids of Giza", 29.979, 31.134, "desert landmark", "The last of the seven wonders, on the edge of the city.", 400),
    ("Mount Catherine, Sinai", 28.510, 33.955, "desert mountains", "Bare granite at 8,600 ft above the Red Sea.", 8625),
    ("Erta Ale", 13.601, 40.666, "volcano desert", "A lava lake in the Danakil, one of the hottest places on earth.", 2011),
    ("Dallol", 14.242, 40.300, "desert volcano", "Yellow and green salt springs 400 ft below sea level.", 0),
    ("Simien Mountains", 13.19, 38.07, "mountains", "An escarpment of eroded pinnacles in Ethiopia.", 14930),
    ("Lalibela", 12.032, 39.047, "landmark mountains", "Churches carved down into the rock.", 8200),
    ("Blue Nile Falls", 11.49, 37.59, "water", "Tis Issat - the water that smokes.", 6000),
    ("Socotra", 12.51, 53.92, "islands desert", "Dragon's blood trees on an island that evolved alone.", 4900),
    ("Tsingy de Bemaraha", -18.70, 44.75, "landmark jungle", "A forest of limestone needles in Madagascar.", 2600),
    ("Avenue of the Baobabs", -20.251, 44.419, "jungle landmark", "Ancient trees along a dirt road.", 300),
    ("Mount Mulanje", -15.95, 35.60, "mountains", "A granite massif standing alone over Malawi's tea estates.", 9849),
    ("Lake Malawi", -12.00, 34.60, "water", "A rift lake with more fish species than any other.", 1560),
    ("Livingstone Falls", -4.55, 15.05, "water jungle", "The Congo dropping through rapids below Kinshasa.", 900),
    ("Mount Cameroon", 4.203, 9.170, "volcano coast", "An active volcano that rises from the sea to 13,000 ft.", 13255),
    ("Piton de la Fournaise", -21.244, 55.708, "volcano islands", "One of the most active volcanoes on earth, on Reunion.", 8635),
    ("Cirque de Mafate", -21.05, 55.42, "mountains islands", "A collapsed caldera with villages you can only walk to.", 9800),
    ("La Digue", -4.36, 55.83, "islands coast", "Granite boulders on a Seychelles beach.", 1000),
    ("Bazaruto", -21.60, 35.45, "islands coast", "Dune islands and sandbars off Mozambique.", 0),
    ("Richat Structure", 21.124, -11.401, "desert landmark", "The Eye of the Sahara - a 30-mile bullseye in the sand.", 1300),
    ("Bandiagara Escarpment", 14.35, -3.42, "desert landmark", "Dogon villages built into a 100-mile cliff in Mali.", 2400),
    # ------------------------------------------------ Middle East and Central Asia
    ("Wadi Rum", 29.58, 35.42, "desert", "Red sand and granite islands; every Mars film is shot here.", 3300),
    ("Petra", 30.329, 35.444, "desert landmark", "Tombs cut into the rose rock of a desert canyon.", 3300),
    ("Dead Sea", 31.50, 35.47, "water desert", "The lowest land on earth, 1,400 ft below sea level.", 0),
    ("Jerusalem old city", 31.777, 35.234, "landmark", "The walls, the domes and the hills around them.", 2500),
    ("Empty Quarter", 20.00, 50.00, "desert", "The largest sand desert in the world, and nothing in it.", 1000),
    ("Jebel Shams", 23.237, 57.263, "mountains desert", "Oman's Grand Canyon, 3,000 ft deep.", 9875),
    ("Musandam fjords", 26.19, 56.24, "coast mountains water", "Bare rock dropping into the Strait of Hormuz.", 6000),
    ("Burj Khalifa and the Palm", 25.197, 55.274, "landmark coast desert", "The tallest building on earth; best at night.", 2717),
    ("Mount Damavand", 35.955, 52.109, "volcano ice", "A snow cone above Tehran.", 18406),
    ("Persepolis", 29.935, 52.891, "desert landmark", "The Persian ceremonial capital on its terrace.", 5700),
    ("Registan, Samarkand", 39.655, 66.976, "landmark desert", "Blue tiled madrasas on the Silk Road.", 2300),
    ("Issyk-Kul", 42.45, 77.20, "water mountains", "A warm lake at 5,000 ft ringed by snow peaks.", 5272),
    ("Khan Tengri", 42.21, 80.17, "ice mountains", "A marble pyramid that glows red at sunset.", 22999),
    ("Pamir Highway", 38.30, 73.50, "mountains desert", "The roof of the world, at 15,000 ft for days at a time.", 15300),
    ("Aral Sea remains", 45.00, 59.00, "desert water", "Ships in the sand where a sea used to be.", 200),
    ("Darvaza gas crater", 40.253, 58.439, "desert landmark", "The Door to Hell, burning since 1971.", 700),
    # ------------------------------------------------ South and East Asia
    ("Mount Everest", 27.988, 86.925, "mountains ice", "29,032 ft. Look, don't try to climb over it.", 29032),
    ("Annapurna", 28.596, 83.820, "mountains ice", "A 20-mile wall above the Pokhara valley.", 26545),
    ("K2", 35.881, 76.513, "mountains ice", "The savage mountain, in the heart of the Karakoram.", 28251),
    ("Nanga Parbat", 35.238, 74.589, "mountains ice", "The Rupal face - 15,000 ft of it, the biggest on earth.", 26660),
    ("Hunza valley", 36.32, 74.65, "mountains", "Terraced villages under 24,000 ft peaks.", 25551),
    ("Pangong Tso", 33.73, 78.90, "water mountains", "A 90-mile blue lake at 14,000 ft in Ladakh.", 14270),
    ("Mount Kailash", 31.067, 81.312, "mountains landmark", "A sacred pyramid nobody is allowed to climb.", 21778),
    ("Yarlung Tsangpo gorge", 29.60, 95.00, "water mountains", "Deeper than anything in the Americas, and barely known.", 25531),
    ("Zhangjiajie", 29.315, 110.435, "mountains jungle", "Sandstone pillars in cloud - the Avatar mountains.", 4140),
    ("Guilin karst", 24.95, 110.40, "jungle water landmark", "Limestone hills along the Li River.", 1300),
    ("Huangshan", 30.132, 118.166, "mountains jungle", "Granite peaks, pines and a sea of cloud.", 6115),
    ("Great Wall at Jinshanling", 40.677, 117.244, "landmark mountains", "The wall running along the ridgelines.", 2300),
    ("Three Gorges", 30.95, 110.70, "water landmark", "The Yangtze through limestone, and the dam that tamed it.", 3000),
    ("Jiuzhaigou", 33.26, 103.92, "water mountains", "Blue and green terraced lakes in a Sichuan valley.", 14000),
    ("Zhangye Danxia", 38.92, 100.13, "desert landmark", "Striped rainbow hills in Gansu.", 6000),
    ("Taklamakan", 39.00, 83.00, "desert", "'Go in and you won't come out' - a thousand miles of dune.", 3500),
    ("Mount Fuji", 35.361, 138.727, "volcano mountains landmark", "The cone, and the five lakes around it.", 12389),
    ("Kamikochi", 36.25, 137.63, "mountains water", "The Japanese Alps and the Azusa river.", 10466),
    ("Sakurajima", 31.585, 130.657, "volcano islands", "A volcano that erupts most days, beside a city.", 3665),
    ("Aso caldera", 32.884, 131.104, "volcano", "One of the largest calderas in the world, with towns inside it.", 5223),
    ("Shiretoko", 44.10, 145.10, "coast ice bush", "Drift ice, bears and waterfalls into the sea in Hokkaido.", 5285),
    ("Daisetsuzan", 43.66, 142.85, "mountains volcano", "Hokkaido's roof - the first snow in Japan every year.", 7513),
    ("Seto Inland Sea", 34.30, 133.50, "islands water coast", "Three thousand islands between Honshu and Shikoku.", 0),
    ("Hallasan, Jeju", 33.362, 126.529, "volcano islands", "A shield volcano with a crater lake, off Korea.", 6398),
    ("Halong Bay", 20.90, 107.18, "islands water landmark", "Two thousand limestone towers in the sea.", 600),
    ("Fansipan", 22.303, 103.775, "mountains jungle", "The roof of Indochina above the Sapa terraces.", 10312),
    ("Mekong Delta", 10.10, 105.80, "water jungle", "Nine mouths, endless channels, floating markets.", 0),
    ("Angkor Wat", 13.412, 103.867, "landmark jungle", "The largest religious monument on earth, in the forest.", 200),
    ("Phang Nga Bay", 8.27, 98.50, "islands coast", "Karst stacks out of flat green water.", 1000),
    ("Railay", 8.01, 98.84, "coast islands", "Limestone walls straight down to the beach.", 800),
    ("Bagan", 21.170, 94.860, "landmark desert", "Two thousand temples on a plain by the Irrawaddy.", 300),
    ("Inle Lake", 20.55, 96.91, "water", "Stilt villages and leg-rowing fishermen in the Shan hills.", 2900),
    ("Mount Agung", -8.343, 115.508, "volcano islands", "Bali's sacred cone above the rice terraces.", 9944),
    ("Mount Bromo", -7.942, 112.953, "volcano", "A smoking cone inside a sand sea inside a caldera.", 7641),
    ("Krakatoa", -6.102, 105.423, "volcano islands", "Anak Krakatau, the child of the 1883 eruption.", 500),
    ("Rinjani", -8.411, 116.457, "volcano islands water", "A crater lake with a new cone growing in it.", 12224),
    ("Lake Toba", -2.61, 98.83, "volcano water islands", "The largest volcanic lake in the world, with an island in it.", 3000),
    ("Komodo", -8.55, 119.48, "islands coast", "Pink beaches, dragons and fierce tidal water.", 2400),
    ("Raja Ampat", -0.50, 130.50, "islands coast jungle", "Mushroom islands over the richest reef on earth.", 800),
    ("Borobudur", -7.608, 110.204, "landmark jungle", "A stone mandala with volcanoes behind it.", 900),
    ("Mount Kinabalu", 6.075, 116.558, "mountains islands", "Borneo's granite dome, 13,400 ft above the South China Sea.", 13435),
    ("Mulu pinnacles", 4.05, 114.85, "jungle landmark", "Razor limestone blades sticking out of the rainforest.", 4900),
    ("Chocolate Hills", 9.80, 124.17, "landmark islands", "Over a thousand identical conical hills on Bohol.", 400),
    ("Banaue rice terraces", 16.93, 121.13, "mountains landmark", "Two thousand years of terracing up the Cordillera.", 5000),
    ("Mayon", 13.257, 123.685, "volcano islands", "The most perfect cone in the world.", 8077),
    ("Taal", 14.002, 120.993, "volcano water islands", "A lake in a volcano on an island in a lake.", 1020),
    ("El Nido", 11.20, 119.40, "islands coast", "Palawan's limestone cliffs and hidden lagoons.", 1000),
    ("Klyuchevskaya Sopka", 56.056, 160.642, "volcano ice", "The highest active volcano in Eurasia, in Kamchatka.", 15584),
    ("Valley of Geysers", 54.43, 160.14, "volcano water", "A Kamchatkan river valley full of geysers.", 1300),
    ("Lake Baikal", 53.50, 108.00, "water ice mountains", "A fifth of the world's fresh water, and it freezes solid.", 1500),
    ("Belukha", 49.807, 86.590, "mountains ice", "The highest peak of the Altai, where four countries meet.", 14783),
    ("Putorana Plateau", 69.00, 94.00, "water mountains ice", "Siberian basalt cut by hundreds of waterfalls; almost nobody goes.", 5500),
    ("Kerala backwaters", 9.50, 76.40, "water jungle coast", "Lagoons, canals and palms behind the beach.", 0),
    ("Sundarbans", 21.95, 89.18, "jungle water", "The biggest mangrove forest in the world, and tigers in it.", 0),
    ("Sigiriya", 7.957, 80.760, "landmark jungle", "A palace on top of a 600 ft rock plug in Sri Lanka.", 1144),
    ("Thar Desert and Jaisalmer", 26.913, 70.912, "desert landmark", "A golden fort in the sand.", 800),
    ("Kangchenjunga", 27.702, 88.147, "mountains ice", "The third highest mountain on earth, above the Darjeeling tea gardens.", 28169),
    # ------------------------------------------------ Australia and New Zealand
    ("Uluru", -25.345, 131.036, "desert landmark", "A single rock, 1,100 ft high, in the middle of the continent.", 2831),
    ("Kata Tjuta", -25.30, 130.73, "desert landmark", "Thirty-six domes, higher than Uluru and far less visited.", 3497),
    ("Kings Canyon", -24.25, 131.57, "desert", "Sheer red walls and a lost world on top.", 3000),
    ("Heart Reef", -19.75, 149.00, "coast islands water", "A coral heart in the Whitsundays.", 0),
    ("Whitehaven Beach", -20.28, 149.04, "coast islands", "Silica sand swirling into turquoise at Hill Inlet.", 0),
    ("Twelve Apostles", -38.665, 143.105, "coast landmark", "Limestone stacks in the Southern Ocean.", 300),
    ("Three Sisters, Blue Mountains", -33.732, 150.312, "mountains jungle", "Sandstone cliffs and blue eucalyptus haze.", 3300),
    ("Sydney Harbour", -33.855, 151.215, "landmark coast", "The bridge, the opera house, and the harbour scenic route.", 0),
    ("Kakadu", -12.85, 132.55, "jungle water bush", "Escarpment, floodplain and waterfalls in the Top End.", 1300),
    ("Bungle Bungles", -17.45, 128.38, "desert landmark", "Orange and black striped beehives in the Kimberley.", 1900),
    ("Horizontal Falls", -16.38, 123.98, "coast water", "Tides forcing seawater sideways through two gaps.", 0),
    ("Ningaloo Reef", -22.70, 113.65, "coast water", "A reef you can swim to from the beach, and whale sharks on it.", 0),
    ("Shark Bay", -25.50, 113.50, "coast water desert", "Stromatolites, seagrass and a beach made of shells.", 0),
    ("Pinnacles Desert", -30.60, 115.16, "desert coast", "Limestone spikes out of yellow sand near the sea.", 500),
    ("Wave Rock", -32.443, 118.897, "desert landmark", "A 50 ft granite breaker frozen mid-curl.", 1200),
    ("Lake Eyre", -28.37, 137.35, "desert water", "A salt pan that becomes an inland sea once a decade.", 0),
    ("Wilpena Pound", -31.55, 138.60, "desert mountains", "A natural amphitheatre of rock in the Flinders Ranges.", 3800),
    ("Cradle Mountain", -41.68, 145.95, "mountains water", "Dolerite crags over Dove Lake in Tasmania.", 5069),
    ("Bay of Fires", -41.05, 148.28, "coast", "Orange lichen granite on white sand.", 0),
    ("Lord Howe Island", -31.55, 159.08, "islands coast mountains", "Two peaks, a lagoon, and a runway between them.", 2871),
    ("Milford Sound", -44.67, 167.93, "water mountains", "Mitre Peak out of black water, and it rains most days.", 5551),
    ("Doubtful Sound", -45.35, 167.05, "water mountains", "Bigger, quieter and emptier than Milford.", 4000),
    ("Aoraki / Mount Cook", -43.595, 170.142, "mountains ice", "New Zealand's highest, with the Tasman Glacier below.", 12218),
    ("Franz Josef Glacier", -43.47, 170.18, "ice mountains", "Ice coming down into temperate rainforest.", 8000),
    ("Fox Glacier", -43.53, 170.02, "ice mountains", "Franz Josef's twin, ten miles south.", 8000),
    ("Mount Taranaki", -39.296, 174.064, "volcano", "An almost perfect cone with a circular forest around it.", 8261),
    ("Tongariro", -39.157, 175.632, "volcano", "Three volcanoes in a row, one of them Mount Doom.", 9177),
    ("White Island", -37.521, 177.182, "volcano islands", "An active crater in the sea off the Bay of Plenty.", 1053),
    ("Rotorua geothermal", -38.36, 176.25, "volcano water", "Steam, mud and coloured pools; you can smell it from the air.", 1000),
    ("Bay of Islands", -35.22, 174.12, "islands coast", "144 islands and the Hole in the Rock.", 0),
    ("Abel Tasman", -40.90, 173.05, "coast islands", "Golden beaches between granite headlands.", 3000),
    ("Southern Alps divide", -43.30, 170.80, "ice mountains", "The spine of the South Island, glaciated end to end.", 10000),
    ("Moeraki Boulders", -45.345, 170.826, "coast landmark", "Stone spheres on an Otago beach.", 0),
    # ------------------------------------------------ Papua and the far south
    ("Owen Stanley Range", -9.10, 147.70, "jungle mountains bush", "Cloud forest and the Kokoda Track behind Port Moresby.", 13363),
    ("Baliem valley", -4.10, 138.95, "jungle mountains bush", "A hidden highland valley only found in 1938.", 5300),
    ("Puncak Jaya", -4.079, 137.184, "mountains ice", "Glaciers 4 degrees from the equator, and going fast.", 16024),
    ("Mount Erebus", -77.529, 167.153, "volcano ice", "An active volcano with a lava lake, on Ross Island.", 12448),
    ("Dry Valleys", -77.50, 162.00, "ice desert", "The driest place on earth - no ice, no snow, no rain for millennia.", 3000),
    ("Ilulissat Icefjord", 69.18, -49.90, "ice water", "Where the Greenland ice sheet calves its biggest bergs.", 0),
    ("Scoresby Sund", 70.50, -24.00, "ice water mountains", "The largest fjord system in the world, in east Greenland.", 6000),
    ("Greenland ice sheet", 72.00, -40.00, "ice", "Two miles thick and nothing else for a thousand miles.", 10500),
]

# ======================================================================
# Helpers
# ======================================================================
_SLUG = re.compile(r"[^A-Z0-9]+")


def slug(name, n=8):
    s = _SLUG.sub("", name.upper().replace("'", ""))
    return (s[:n] or "WONDER")


def _ident(name, used):
    base = slug(name)
    ident = base
    i = 1
    while ident in used:
        i += 1
        ident = f"{base[:7]}{i}"
    used.add(ident)
    return ident


def _pairs():
    """The list as dicts, with unique idents, built once."""
    used, out = set(), []
    for name, lat, lon, tags, text, msl in WONDERS:
        out.append({"name": name, "lat": lat, "lon": lon, "tags": set(tags.split()),
                    "text": text, "msl": int(msl), "ident": _ident(name, used)})
    return out


ALL = _pairs()


def waypoint(w):
    """A wonder in the same shape as an airport, so it can be a stop you overfly."""
    return {"id": "*" + w["ident"], "name": w["name"], "kind": "wonder", "elev": w["msl"],
            "lat": w["lat"], "lon": w["lon"],
            "rwys": [{"e": ["00", "18"], "len": 0, "w": 0, "s": "none", "lit": False, "h": 0,
                      "lat": w["lat"], "lon": w["lon"]}],
            "ramps": [], "tower": False, "atis": False, "ils": [], "pack": None,
            "spot": True, "wonder": True,
            "city": "", "state": "", "country": "", "iso": "", "notes": w["text"]}


def nm(a_lat, a_lon, b_lat, b_lon):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    x = (math.sin((p2 - p1) / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(math.radians(b_lon - a_lon) / 2) ** 2)
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(x)))


def near(lat, lon, radius=120, tags=None):
    """Wonders within `radius` nm of a point, nearest first."""
    out = []
    for w in ALL:
        if tags and not (w["tags"] & set(tags)):
            continue
        d = nm(lat, lon, w["lat"], w["lon"])
        if d <= radius:
            out.append((d, w))
    out.sort(key=lambda x: x[0])
    return out


def count_by_tag():
    c = {}
    for w in ALL:
        for t in w["tags"]:
            c[t] = c.get(t, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))
