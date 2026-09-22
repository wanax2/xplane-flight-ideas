X-PLANE FLIGHT IDEAS  v6.3
========================

Files
  Flight Ideas.bat          double-click to start the app (Windows)
  xp_flight_ideas_gui.py    the app
  xp_flight_ideas.py        idea engine + command-line version
  xp_link.py                talks to X-Plane's Web API
  xp_images.py              maps, airport diagrams, sky pictures, photos
  xp_wx.py                  live weather (current METARs from aviationweather.gov)
  xp_scenic.py              worldwide scenic-flight generator
  xp_wonders.py             429 natural wonders and landmarks worldwide
  xp_acf.py                 reads performance out of your aircraft's .acf files
  xp_score.py               flight scoring and the logbook
  xp_export.py              nav logs, briefing sheets, GPX/KML/LNM, trips, share codes
  xp_career.py              ratings, badges, challenge of the day
  xp_kneeboard.py           checklists, speech, the kneeboard window
  xp_terrain.py             terrain height along the route
  xp_online.py              OurAirports database + shared routes from
                            flightplandatabase.com
  xp_theme.py               the look of the app (light and dark)
  xp_scenery.py             which add-on scenery you have installed
  xp_perf.py                density altitude, runway lengths, fuel, weight
  xp_approach.py            approach geometry, runway choice, minimums
  xp_radio.py               ATIS, radio calls, and your own landing spots
  xp_web.py                 the briefing for your phone, and backups
  xp_qr.py                  the QR code shown for the phone briefing
  PI_FlightIdeas.py         small XPPython3 plugin that loads the route into the GPS/FMS

Keep all the files in one folder. You need Python 3.8 or newer (python.org -
tick "Add Python to PATH" during install). Nothing else to install.


   THE LOOK  (v5.0)
   - Light by default, with a "Dark mode" button in the top right corner. It
     remembers which one you used.
   - The left-hand panel scrolls, so the app is usable on a small laptop
     screen, and the "Where" box only shows the boxes that apply to the area
     you picked.
   - Mission types are no longer 41 tick-boxes: press "Choose missions..." for
     a window that groups them (everyday flying, backcountry, weather and
     instruments, scenery, training) with quick picks - "Easy day out",
     "IFR practice", "Bush and backcountry", "Sharpen your flying".
   - It follows your Windows display scaling: table rows, column widths, the
     pictures and the window size are all worked out from your actual text
     size, so nothing overlaps or gets cut off on a 4K or 150% screen (v5.1).
   - The briefing is laid out properly now - headings, the route with its legs,
     the weather colour-coded VFR/MVFR/IFR/LIFR - instead of a wall of
     typewriter text. "Copy briefing" and the printable sheet are unchanged.


1. GENERATE IDEAS
   - The app finds X-Plane automatically (or use Browse...). The first scan of
     your scenery takes up to a minute; after that it's instant. Press
     "Rescan scenery" after installing new airports.
   - Choose the plane (every .acf in your Aircraft folder) and a livery.
     "Flies like" defaults to "Auto (read from the aircraft file)": the app reads
     the .acf and works out cruise speed, range, shortest usable runway,
     crosswind limit, ceiling, engines, floats/helicopter/glider and payload.
     You can pick a hand-written preset instead, and "Edit performance..."
     lets you change any of it - your edits are remembered per aircraft.
   - Where > Area:
       Whole world          - anywhere in your X-Plane scenery
       A continent          - North America, South America, Europe, Africa,
                              Asia & Middle East, Oceania & Pacific
       A country            - pick from the list or type a name/code (GB, NZ...)
       A state / province   - pick the country, then the state
       Near an airport      - within N nm of an airport code (crosses borders)
     "Always depart from" (optional) forces every idea to start at one airport.
     Also: max leg length, and whether to include private strips.
   - Scenic ideas now include famous spots around the world (Courchevel, Lukla,
     Saba, St Barth, Maho Beach, Gibraltar, Madeira, Barra's beach, Innsbruck,
     Queenstown, Milford Sound, Paro, Svalbard, the Faroes...).
   - Press "Choose missions..." to pick what kind of flying you want (or use a
     quick pick), then set the number of ideas and how often a twist (failure,
     diversion, deadline...) is added. Same seed = same ideas.
   - "Or fly your own route": type airport codes, e.g.  KBJC KLXV KASE


   PICTURES (right side of the Briefing tab)
   - Route map: your stops, distances, wind, nearby airports and where the
     twist happens (red X). Mystery flights only show a dashed "?" arrow.
   - "Pictures of": choose any airport on the route, then:
       Photo           - a photo from that airport's Wikipedia article (needs
                         internet; click the caption to open the article).
                         Most photos are JPEGs: press "Enable JPEG photos" once
                         to install the free Pillow library (or run
                         py -m pip install pillow). Untick "Photos" to stay offline.
       Airport diagram - runways drawn to scale from your X-Plane scenery, the
                         runway favoured by the wind in green, and a wind arrow.
       Sky & weather   - a picture of the time of day, clouds, rain/snow, fog
                         and a windsock for the chosen conditions. It updates as
                         you change weather or time on the "Fly it" tab.
       Your plane      - the aircraft's own thumbnail (and the livery's, if it has one).
   If the diagram says "Rescan scenery", press that button once (v2.1 stores
   runway positions that older scans didn't).


   WORLD WEATHER (the "Weather" tab - needs internet)
   - "Refresh weather" downloads every current METAR from NOAA's Aviation
     Weather Center (aviationweather.gov). Tick "Auto-refresh every N min" to
     keep polling (5 min minimum; 10 is plenty - reports come in hourly).
   - Look for: any bad weather, anything IFR/LIFR, low ceilings only, low
     visibility only, strong or gusty wind, thunderstorms, snow/ice/freezing
     rain, fog, rain, or dust/sand/smoke/ash -
       within N nm of an airport you type,
       in your region (Country/State on the left), or
       worldwide (whole world or one continent).
     "Minimum severity" hides the milder reports (2 is a good start; 5+ = only
     the really nasty stuff).
     "Low ceilings only" scores by the cloud base alone (3,000 ft and below,
     worst at 200 ft or less) and ignores how far you can see. "Low visibility
     only" does the opposite: under 5 SM counts, 1/4 SM is the worst, whatever
     the cloud is doing. Use them when you want one or the other, not both.
   - The list shows the airports closest to that weather, worst first, with the
     METAR decoded (click a column header to sort). "Only airports my plane can
     use" swaps a reporting station for the nearest runway your plane fits.
     The map colours every station by flight category (green VFR, blue MVFR,
     red IFR, purple LIFR); big dots are the matches, a bolt means storms.
   - "Set up a flight INTO this weather" makes a flight from your airport (or
     from a nearby airport in better weather) into it. "Take off IN this
     weather" starts you there and sends you to a nearby airport in better
     weather. With "then open the 'Fly it' tab" ticked you land straight on
     the setup tab - pick the plane/start position and press Launch.
     Double-click a row = INTO this weather.
   - Or tick "realwx" under Mission types and Generate ideas as usual.
   - Live-weather flights default to X-Plane's own real-world weather and your
     computer's clock on the "Fly it" tab, so the sim matches what's happening.
     Pick "Mission weather" instead to freeze the conditions from the METAR.
   - Command line:  python xp_flight_ideas.py --from KBJC --live-weather ifr
                    python xp_flight_ideas.py --world
                    python xp_flight_ideas.py --continent Europe
                    python xp_flight_ideas.py --country NZ
                    python xp_flight_ideas.py --country CA --state "British Columbia"


   SCENIC WORLD (Explore > Scenic, or the buttons on the left)
   A separate generator that ignores "Where" and picks a scenic flight
   anywhere in the world. Four sources, each with its own tick box:

   - Famous routes: 456 hand-picked airport-to-airport runs on every continent
     (Alps, fjords, Himalaya, Caribbean, Patagonia, Hawaii, Alaska, Greenland,
     Uluru, Milford Sound, Victoria Falls, the Nile, the Amazon, Kamchatka...).

   - Natural wonders (new in v6.1): 429 places worth looking at that mostly
     have no airport at all - Angel Falls, Everest, the Matterhorn, Iguazu,
     the Grand Prismatic Spring, Uluru, Halong Bay, the Richat Structure,
     Sossusvlei, Denali's Ruth Glacier, Machu Picchu, Bora Bora, Erta Ale.
     The app finds the nearest runway your aeroplane can actually use and
     routes you over the thing itself as a GPS waypoint, then lands you there.
     The briefing gives its position, how high the ground goes, what height to
     cross at - and tells you plainly when the summit is above your aircraft's
     ceiling and you should fly alongside instead.

   - Hidden gems found in your scenery: airports with much higher terrain
     nearby, very high strips, islands, glaciers, lakes, fjords, canyons,
     volcanoes (from airport elevations, runways and names).

   - Random places (new in v6.1): a dart thrown at the planet. Any airport
     anywhere in your scenery, leaning towards interesting ground - big relief
     close by, high fields, unpaved strips, water runways, high latitudes, and
     anything within 70 nm of one of the wonders. The briefing tells you what
     the dice picked and why it might be worth the trip. The "Anywhere on
     earth" button does this on its own, ignoring the other three sources.

   - Ten kinds of scenery: mountains, islands, coast & beaches, glaciers &
     Arctic, canyons & desert, volcanoes, lakes/rivers/fjords, landmarks &
     cities, jungle & wetlands, bush & backcountry.
   - Filter by scenery type and continent. "Surprise me!" opens one flight
     straight away; "Show me" lists several with a map preview.
   - If your plane can't use a famous strip (e.g. Courchevel), you overfly it
     and land at the nearest airport it can use. Seasons follow the hemisphere.
   - Command line:  python xp_flight_ideas.py --scenic-world -n 5
                    python xp_flight_ideas.py --scenic-world mountains,ice --continent Europe
                    python xp_flight_ideas.py --scenic-world --scenic-source wonders
                    python xp_flight_ideas.py --anywhere -n 5
                    python xp_flight_ideas.py --wonders-near KBJC

   WONDERS NEAR ME ("Wonders near me" button on the left)
   All 429 places in one list, sorted by how far they are from you, with what
   you'd be looking at. Type a different airport code at the top to measure
   from somewhere else. "Only ones I can reach" hides anything with no usable
   runway near it in your scenery - so the list shrinks to what you can
   actually go and see today. Pick one and press "Open briefing" or
   "Set up in X-Plane".

   DANGEROUS WEATHER NOW (button on the left)
   One click: downloads current weather if needed and lists the worst weather
   in the world right now (minimum severity 6). Pick a row, then pick an airport
   from "Airports near the weather" and choose "Fly from here INTO it" or
   "Take off IN it, land here".


   IDEA TABS: "North America" and "World"  (v4.0)
   Two tabs with their own area controls, their own Generate button and their
   own list of ideas with a map preview. They use the aircraft, mission types
   and twist setting from the left panel.
     North America - All of North America, United States, Canada, Mexico,
                     Alaska, Hawaii, Caribbean, Central America, US Rockies,
                     US East Coast, US West Coast, plus state/province,
                     "near an airport within N nm", and "always depart from".
     World         - continent, country, state/province, near an airport.
   The old "Where" box on the left still works for the main Generate button.

   BROWSE AIRPORTS  (v4.0)
   "Browse airports..." searches every airport in your scenery by code, name or
   city, filtered by country, runway length, surface, tower, ILS, elevation, and
   distance from an airport. It shows a diagram of the selected one, and the
   buttons send it straight into a flight: depart from here, search around here,
   add to the route box, or fly here from your departure airport.

   YOUR OWN SCENERY  (v6.0)
   The app reads your Custom Scenery folder (and scenery_packs.ini, so disabled
   packs are ignored exactly as X-Plane ignores them) and works out:
     - which airports come from an add-on pack rather than the default set,
     - which one-degree tiles have photo (ortho) or custom mesh scenery.
   "Use my add-ons" on the left: ignore / favour / only.
     favour  - ideas drift towards airports where your sim looks good
     only    - every stop is somewhere you have add-on scenery
   The briefing shows a star line for each stop that has add-on scenery, naming
   the pack. "My scenery..." lists every pack, and has a "Never flown there" tab
   that finds the add-on airports your logbook has never visited - the ones you
   installed and forgot about.

   APPROACH PRACTICE  ("Approach practice..." on Fly it > Set it up)   (v6.3)
   Puts you on final anywhere, as many times as you like. No route, no idea, no
   flight plan - type an airport code and press the button.
   - It picks the runway for you: the instrument runway first, then the one with
     the best headwind, and it says in one line why. Untick "prefer the
     instrument runway" if you'd rather just have the wind.
   - The runway list shows length, the ILS frequency where your scenery has one,
     and the head and crosswind components on each end.
   - Distance: anything from 1 to 20 nm, with four shortcuts - Short final (2),
     4 nm, Glideslope (6) and Intercept (10).
   - Weather: leave X-Plane's alone, a clear day, 800 ft and 3 miles, right at
     minimums (200 ft and half a mile), or real weather.
   - Before you press anything it tells you what you're being dropped into: the
     height you'll appear at and what the altimeter will read, the rate of
     descent and speed to hold, time to the threshold, the wind on the runway,
     the localizer frequency and course, the usual minimums for that kind of
     approach, whether the runway is long enough for your aeroplane, and whether
     you will actually see the runway in that weather.
   - Leave the window open. "Put me on final" works over and over, so you can
     fly the same approach ten times in a row.
   - "Back to final" on Fly it > In flight repeats the last approach exactly -
     handy after a go-around or a landing you'd rather forget.
   Heights assume a 3-degree path and 50 ft over the threshold. The minimums are
   the usual ones for the kind of approach, NOT the numbers off the real chart -
   if you're flying a published procedure, use the plate.


   THE NUMBERS  (Briefing tab > "Numbers")   (v6.0)
   For the departure and the destination:
     - density altitude from the field elevation, temperature and altimeter,
     - the best runway for the wind, with head and crosswind components (and a
       warning when the crosswind is over your aircraft's limit),
     - estimated takeoff and landing distances - ground roll and over a 50 ft
       obstacle - against the runway you actually have, with a verdict:
       comfortable, fine, tight, or too short,
     - fuel: trip + taxi + alternate + reserve in gallons and pounds, against
       what your tanks hold, with the endurance,
     - weight: empty + fuel + load against the maximum, and the CG if the
       aircraft file gives limits.
   Type the fuel and the load at the top to see the numbers change. "Wet runway"
   adds the usual penalty.
   These are rule-of-thumb estimates calibrated against a Cessna 172's published
   figures - within a few percent of the 172 tables from sea level to 8,000 ft -
   but they are NOT your aircraft's flight manual. Treat them as a sanity check.
   On the "Fly it" tab, "Load the planned fuel into the aircraft" sets the tanks
   in X-Plane to the planned figure plus a little, instead of whatever the last
   flight left in them.

   ATIS AND RADIO CALLS  (Briefing tab > "Radio")   (v6.0)
   An ATIS written out the way one really reads - wind, visibility, sky,
   temperature and dew point, altimeter, runway in use, spoken digit by digit -
   and every radio call for the flight in order: taxi, departure, en route,
   overhead each stop, the arrival and the circuit. Towered and non-towered
   airports get different calls, IFR flights get a clearance. Set your callsign
   at the top. "Read the ATIS aloud" speaks it.

   YOUR OWN LANDING SPOTS  (v6.0)
   "My spots..." next to the route box: save any latitude and longitude as a
   place to fly to - a gravel bar, a meadow, a ridge, an oil rig - with its
   elevation, surface and usable length. Spots behave like tiny airports: they
   can be a destination, they go into the route box (their code starts with *),
   and they're written into the .fms as a plain lat/lon waypoint. "Use my
   position in X-Plane" grabs wherever your aircraft is sitting right now.

   EMERGENCIES  (Fly it tab)   (v6.0)
   "Surprise failure between N and M minutes" now picks from eighteen kinds -
   engine, rough running, vacuum, radios, electrics, alternator, pitot, static,
   ASI, attitude, altimeter, DG, gear, brakes, fuel pump, flaps, GPS, autopilot -
   and "Which ones..." lets you choose (with quick picks for engine only or
   instruments only). When the flight is scored, you get a debrief: what broke,
   where, how close the nearest usable airport was, where you actually finished,
   and what the drill looks like.

   CHARTS, LITTLE NAVMAP AND LOCAL TIME  (v6.0)
   - Export / print > "Approach plates and charts for this route" opens a menu
     per airport: FAA digital terminal procedures and AirNav for US fields,
     SkyVector and OpenAIP everywhere, and the Wikipedia article when there is one.
   - "Send straight to Little Navmap's folder" writes the .lnmpln where Little
     Navmap keeps its plans, so it's in the list next time you open it.
   - "The real time where I'm flying" on the Fly it tab sets the sim to today's
     date and the clock time it is right now at the departure airport's
     longitude - so if you're flying in New Zealand at breakfast time here, it's
     evening there, as it really is.

   THE BRIEFING ON YOUR PHONE, AND BACKUPS  (v6.0)
   - Export / print > "Send the briefing to my phone or tablet" starts a small
     web server on your own network and shows a QR code. Scan it with the phone's
     camera and the briefing sheet opens there, ready to read on a tablet on the
     yoke. The page is served only while that window is open - and while it is,
     anyone on your network can open it, so close it when you're done.
   - Export / print > "Back up settings, logbook and trips..." saves everything
     the app remembers into one zip: settings, logbook, trips, spots, career.
     "Restore from a backup..." puts it back (keeping the old files as .bak).

   REAL FLIGHTS HAPPENING NOW  (Explore > Shared routes)   (v6.0)
   "Copy a real flight" asks the OpenSky Network which aircraft are airborne
   near an airport you name, keeps the ones flying like light aircraft, and
   builds a flight from one of them: take off from the nearest field you can
   use, join their track, fly it at their height. Their callsign and position
   are in the notes. Free and anonymous, rate-limited by OpenSky; positions are
   a minute or two old.

   ONLINE FLIGHTS (Explore > Shared routes - needs internet)   (v4.5)
   Routes that other pilots have shared, from flightplandatabase.com - tens of
   thousands of them, free, no account needed.
   - Search by departure and/or arrival airport, by tag (scenic, bush, vfr,
     ifr, mountain, island, shortfield, sightseeing, challenge...), by distance,
     sorted by popularity, date or length.
   - "Make it a flight idea" turns the shared route into a normal idea, with
     weather, a time of day, the map, the nav log and everything else. Airports
     that aren't in your scenery are dropped automatically, and a very long
     route is thinned to a sensible number of stops.
   - "Save .fms to X-Plane" downloads the plan in X-Plane's own format straight
     into X-Plane/Output/FMS plans. "Open on the website" shows the original.
   - An API key is optional: a free account at flightplandatabase.com only
     raises the per-hour request limit.

   AIRPORT DATA FROM OURAIRPORTS  (v4.5)
   Bottom of Explore > Shared routes: "Download / refresh" fetches the open OurAirports
   database (about 10 MB, once). It fills in city, region, country, IATA code,
   airport type and Wikipedia links for the airports in your scenery, which
   means better photos on the Briefing tab, a country list that's actually
   complete, and a new "Type:" filter in "Browse airports..." (large/medium/
   small airport, heliport, seaplane base, balloonport, or "has airline
   service"). Everything works without it; it just gets better with it.

   BUILD A TOUR  (v4.5)
   "Build a tour..." on Progress > Trips: pick an area (world or a continent), how
   many legs, and a style - Scenic highlights, Hidden gems, or Anything nearby -
   and it strings together a multi-leg tour that your aircraft can actually fly,
   saved as a trip you tick off leg by leg over several sessions.

   MORE MISSION TYPES (v3.0, v4.0, v4.5)
   cargo      - haul a load into a short strip; the payload is set in X-Plane
   sightsee   - overfly a string of sights, land at the last one
   aerobatic  - airwork and practice overhead one airport
   soaring    - a glider triangle (only offered for gliders)
   alphabet   - land at airports A, B, C... in turn
   mail       - several stops against the clock
   checkride  - the whole practical test in one flight, graded against limits
   poker      - five airports, five cards, best hand
   photo      - be overhead at the right height, heading and light
   organ      - urgent medical transport against a hard deadline
   sar        - search and rescue: fly an expanding square, then land
   patrol     - pipeline or powerline patrol at low level
   timetrial  - fastest time between two airports (the logbook keeps your time)
   hold       - an IFR holding pattern at a real beacon, then the approach
   circuits   - a set of circuits at one airport, each one a different exercise
                (flapless, glide, short field, soft field, go-around...)
   diversion  - plan the flight, then divert in the air when the destination
                shuts; work out heading, time and fuel on the move
   pass       - cross a mountain pass at the lowest safe level, with the wind
                and the lee-side downdraught to think about
   survey     - a grid of parallel survey lines at a fixed height, flown by hand
   firewatch  - hot, dry, windy fire-spotting patrol, then a short strip
   nordo      - the radio quits: work out the runway in use and join a
                non-towered pattern without saying a word
   dawn       - wheels up in the dark, sunrise on the way, smooth air
   lowceil    - marginal VFR under a low overcast: plan it below the cloud,
                know the high ground, and set a turn-back point (v4.6)
   lowvis     - an approach down to minimums in fog or heavy haze; IFR aircraft
                get the ILS to DH, VFR ones get a no-horizon haze flight (v4.6)

   SCORING AND LOGBOOK (Progress > Logbook)
   Tick "Score the flight and add it to the logbook" on the Fly tab. The app
   watches the flight and grades every landing: touchdown rate, how far past
   the threshold, distance off the centreline, plus smoothness and whether you
   arrived where you planned. When you stop on the ground it saves the flight
   (or press "End flight & save now"). The logbook keeps totals - hours, miles,
   landings, airports, average score, your smoothest touchdown - and exports to
   CSV. Landing scoring needs the runway data, so rescan scenery once if the
   airport shows as unknown.

   TRIPS (Progress > Trips)
   "Make a trip" on the Briefing tab turns any multi-stop idea into a trip you
   fly leg by leg over several sessions. Pick a leg, press "Fly this leg" and it
   becomes the current flight; when the score is saved the leg is ticked off.

   EXPORT / PRINT (the "Save" and "More" buttons on the Briefing tab)
   - Printable briefing sheet (HTML, opens in your browser - Ctrl+P to print)
   - Nav log: headings, groundspeed, time and fuel per leg for the planned wind
   - .fms for the X-Plane GPS, GPX (Little Navmap, SkyDemon), KML (Google Earth)
   - Copy the route string, or open the route in SimBrief


   IN FLIGHT (v3.5)
   - Fly it > "In flight": your aircraft drawn on the route map, groundspeed,
     height, distance and time to the next stop, miles flown and fuel used.
   - "Kneeboard" button: a small always-on-top window with the mission, the
     live numbers and a checklist for each phase, tailored to your aircraft
     (piston, turbine, helicopter, glider, floats, twin).
   - "Read aloud" speaks the briefing using Windows' built-in voice
     (macOS 'say' / Linux espeak also work). There's a tick-box to do it
     automatically at launch.
   - "Show the mission inside X-Plane" sends the mission text to the sim
     through the companion plugin, so you don't have to alt-tab.
   - "Surprise failure between N and M minutes after takeoff": something breaks
     (engine, vacuum or radios) at a random time. "Repair failures" fixes it.

   TERRAIN AND FORECAST (Briefing tab > Terrain)
   - "Check terrain" draws the ground along the route with your planned cruise
     and a suggested minimum safe altitude, and warns about mountain wave when
     the wind is strong over high ground.
   - By default it uses airport elevations only, which under-reads real peaks.
     Tick "Use online terrain data" for proper elevations (opentopodata.org,
     free, a little slower, cached on disk).
   - "Forecast" fetches the destination's TAF.

   CAREER (Progress > Career)
   Ratings from Student to Legend based on hours and landings, twenty badges
   (greaser, world tour, airport collector, hard IFR...), and "Today's
   challenge" - a flight generated from the date, the same every time, so you
   can try to beat your own score.

   FLIGHT PLAN FILE OPTIONS  (v4.6)
   Bottom of the "Fly it" tab:
   - "Save a .fms file when I launch a flight" - untick it and no file is
     written at all (the route still goes into the GPS through the plugin).
   - "Save one now" writes one whenever you want, even with the switch off.
     The "Save .fms plan" button and the Export menu always write one too.
   - "Where and what name..." sets the folder and the file name:
       Folder    blank = X-Plane's own Output/FMS plans (what the GPS menu
                 lists). Point it anywhere else - Little Navmap, a second
                 sim, a Dropbox folder - and plans go there instead.
       File name a pattern, e.g. IDEA_{from}_{to}, {from}-{to},
                 {date}_{time}_{from}_{to}, {title}, {kind}_{from}_{to}.
                 Fields: {from} {to} {date} {time} {kind} {title} {n}
                 {aircraft}. Anything illegal in a file name is replaced.
     The line under the switch always shows exactly where the next file goes.
   - Command line:  python xp_flight_ideas.py --world --fms-dir "D:\plans"

   SUNRISE AND SUNSET  (v4.5)
   Every briefing, nav log, printed sheet and kneeboard now shows sunrise and
   sunset at the departure airport for that month, and how much daylight is
   left when you take off (or how far before sunrise a night departure is).

   RADIO NAVIGATION
   New mission type "radionav": VOR and NDB beacons from your nav data, tuned
   and tracked with no GPS. The beacons go into the .fms plan as real navaids.

   SHARING
   Export / print > "Copy share code" turns the whole flight (route, weather,
   time, twist) into a short code. Anyone with the app pastes it into the route
   box and presses "Paste share code" to fly exactly the same thing.
   Little Navmap plans (.lnmpln) are in the same menu.


2. FLY IT IN X-PLANE  (the "Fly it" tab)
   Needs X-Plane 12.4.0 or newer, running, with the Web API enabled:
   X-Plane > Settings > Network > allow the Web API (port 8086).
   Press "Test connection" to check.

   Everything is pre-filled from the idea, and you can change any of it:
   - Starting position: departure airport (type any code), then on the runway
     (favoured runway for the wind is pre-selected), parked at a gate/tie-down,
     on final to the next stop (1-15 nm out), or in the air part-way along leg 1.
     Engines running, or cold and dark.
   - Date and time: month and local time, or your computer's clock.
   - Weather: the mission weather (sky, wind, gusts, temperature, visibility,
     ceiling, altimeter - all editable), real-world weather, an X-Plane preset,
     or leave X-Plane's current weather alone.
     Ceiling ft AGL: type any height (or pick 100...4000) and the overcast moves
     there; "none" takes the ceiling away. Visibility has the usual low values
     (1/4, 1/2, 3/4, 1, 1 1/2...) in its list. Under the two boxes the app shows
     what that adds up to - VFR, MVFR, IFR or LIFR - in colour, and both are
     sent to X-Plane when you launch.
     "Minimums" sets a CAT I day (200 ft and 1/2 SM, or 1 1/2 SM haze if your
     aircraft isn't IFR); "Clear day" puts it back to blue sky.
     The Sky list also has fourteen new low presets: overcast 2,500 / 1,500 /
     1,200 in rain / 1,000 / 600 / 400 in snow / 200 (CAT I) / 100, and for
     visibility alone: 3 SM haze, 1 1/2 SM haze, 1 SM smoke, 3/4 SM mist,
     1/2 SM shallow fog and 1/4 SM dense fog.
   - "Launch flight in X-Plane" loads the plane, position, time and weather.


3. ROUTE INTO THE GPS / FMS
   X-Plane's Web API can't load flight plans, so a tiny plugin does it:
   a) Install the free XPPython3 plugin for X-Plane 12:
      https://xppython3.readthedocs.io  (unzip into X-Plane 12/Resources/plugins)
   b) In the app press "Install GPS plugin..." (copies PI_FlightIdeas.py into
      Resources/plugins/PythonPlugins), then restart X-Plane.
   After that, launching a flight also loads the route into the G1000 / GNS / FMS
   a few seconds after the flight is ready. If the avionics were still booting,
   use X-Plane's menu  Plugins > Flight Ideas > Reload route into GPS,
   or the app's "Send route to GPS only" button.
   Without the plugin, every route is still saved in X-Plane/Output/FMS plans,
   so you can load it from the GPS/FMS flight-plan menu yourself.
   Mystery flights never load the route (it would spoil the surprise).


4. TWISTS AND LIVE PROGRESS
   With "Show live progress" on, the bottom of the tab shows the distance to the
   next stop, groundspeed and height. With "Arm the twist failure" on, the
   engine / vacuum / radio failure from the twist is triggered when you reach
   the spot. "Repair failures" fixes them again.


COMMAND LINE (no GUI)
   python xp_flight_ideas.py --help
   python xp_flight_ideas.py -a cub --from KMYL --save


TROUBLESHOOTING
   - "Can't reach X-Plane's Web API": X-Plane isn't running, or the Web API is
     off in Settings > Network, or a different port is set.
   - "needs X-Plane 12.4.0 or newer": older versions can't start flights from
     outside. Use the saved .fms plan and set up the flight by hand.
   - A launch error from X-Plane: the exact request sent is saved in
     %USERPROFILE%\.xp_flight_ideas\last_flight.json
   - Plugin messages are in X-Plane 12/XPPython3Log.txt
   - "Couldn't reach flightplandatabase.com": the site or your connection is
     down, or you've hit the free request limit for this hour. Everything else
     in the app carries on working offline.


WHERE THE ONLINE DATA COMES FROM
   aviationweather.gov          current METARs and TAFs (US government, free)
   opensky-network.org          which aircraft are airborne right now (free)
   flightplandatabase.com       routes shared by other pilots (free API)
   davidmegginson.github.io/ourairports-data
                                the OurAirports open airport database
   en.wikipedia.org             airport photos and articles
   opentopodata.org             terrain elevations
   All of them are optional. The app works with no internet at all - it just
   uses your own X-Plane scenery instead.


WHAT'S NEW IN 6.3
   - Approach practice: put the aeroplane on final at any airport, at any
     distance, in any weather, over and over. It picks the runway, reads the ILS
     frequency out of your scenery, and tells you the height, the descent rate
     and whether you'll see the runway before you press go. "Back to final"
     repeats the last one after a go-around.
   - The app now reads the localizer frequency and course out of earth_nav.dat,
     not just which runways have one. That means a one-time rescan of your
     scenery the first time you run this version.
   - Fixed: the scenery scan read a setting from a background thread, which
     could make it fail with "main thread is not in main loop".


WHAT'S NEW IN 6.2
   A tidy-up, no new flying.
   - Five tabs instead of twelve. Briefing and Fly it are where they always
     were; the rest moved into two groups with their own little tab strips:
       Fly it   > Set it up | In flight
       Explore  > Scenic | North America | Worldwide | Shared routes
       Progress > Career | Logbook | Trips | Messages
   - The briefing's row of nine buttons is now Copy, Save and More. Everything
     that was there is still there, one click further in.
   - New Settings window: X-Plane folder, rescan, add-on scenery preference and
     the theme, all in one place. The left panel now shows a single line saying
     what's loaded, which is all you need day to day.
   - The left panel fits on the screen without scrolling, the panel is a little
     wider so button labels stop getting cut off, and the scenery-type filter
     on the Scenic tab wraps onto two rows.


WHAT'S NEW IN 6.1
   - 429 natural wonders worldwide as a new source of flights. Most of them
     have no airport; the app finds the nearest runway you can use and puts
     the wonder itself in the route as a GPS waypoint you fly over.
   - Another 134 famous scenic routes, bringing that list to 456.
   - "Anywhere on earth": a genuinely random destination, anywhere in your
     scenery, weighted towards ground worth looking at.
   - "Wonders near me": all 429 sorted by distance from wherever you are, with
     the unreachable ones hidden if you want.
   - The scenic tab now has a tick box per source, and the scenery-type filter
     wraps onto two rows so all ten are visible.
   - New command line: --anywhere, --wonders-near ICAO, and --scenic-source
     now takes a list (famous,wonders,gems,random,all).
