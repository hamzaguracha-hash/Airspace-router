from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import heapq
import math
import time
import xml.etree.ElementTree as ET
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

AMADEUS_KEY    = os.getenv("AMADEUS_API_KEY")
AMADEUS_SECRET = os.getenv("AMADEUS_API_SECRET")
AVSTACK_KEY    = os.getenv("AVIATIONSTACK_KEY")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Airport data (ICAO → info + IATA code) ────────────────────────────────────
AIRPORTS = {
    "EGLL": {"name": "London Heathrow",         "iata": "LHR", "lat": 51.477,  "lon":  -0.461},
    "LGAT": {"name": "Athens International",    "iata": "ATH", "lat": 37.936,  "lon":  23.944},
    "LFPG": {"name": "Paris CDG",               "iata": "CDG", "lat": 49.009,  "lon":   2.548},
    "OMDB": {"name": "Dubai International",     "iata": "DXB", "lat": 25.253,  "lon":  55.365},
    "OERK": {"name": "Riyadh King Khalid",      "iata": "RUH", "lat": 24.957,  "lon":  46.698},
    "OEJN": {"name": "Jeddah King Abdulaziz",   "iata": "JED", "lat": 21.679,  "lon":  39.156},
    "OKBK": {"name": "Kuwait International",    "iata": "KWI", "lat": 29.227,  "lon":  47.969},
    "OTHH": {"name": "Doha Hamad",              "iata": "DOH", "lat": 25.273,  "lon":  51.608},
    "VABB": {"name": "Mumbai Chhatrapati",      "iata": "BOM", "lat": 19.089,  "lon":  72.868},
    "VIDP": {"name": "Delhi Indira Gandhi",     "iata": "DEL", "lat": 28.556,  "lon":  77.100},
    "WSSS": {"name": "Singapore Changi",        "iata": "SIN", "lat":  1.359,  "lon": 103.989},
    "ZBAA": {"name": "Beijing Capital",         "iata": "PEK", "lat": 40.080,  "lon": 116.584},
    "RJTT": {"name": "Tokyo Haneda",            "iata": "HND", "lat": 35.552,  "lon": 139.780},
    "YSSY": {"name": "Sydney Kingsford Smith",  "iata": "SYD", "lat":-33.946,  "lon": 151.177},
    "KJFK": {"name": "New York JFK",            "iata": "JFK", "lat": 40.640,  "lon": -73.779},
    "KLAX": {"name": "Los Angeles",             "iata": "LAX", "lat": 33.943,  "lon":-118.408},
    "KORD": {"name": "Chicago O'Hare",          "iata": "ORD", "lat": 41.978,  "lon": -87.905},
    "FAOR": {"name": "Johannesburg O.R. Tambo", "iata": "JNB", "lat":-26.139,  "lon":  28.246},
    "HECA": {"name": "Cairo International",     "iata": "CAI", "lat": 30.122,  "lon":  31.406},
    "HAAB": {"name": "Addis Ababa Bole",        "iata": "ADD", "lat":  8.978,  "lon":  38.799},
    "EDDF": {"name": "Frankfurt",               "iata": "FRA", "lat": 50.026,  "lon":   8.543},
    "LEMD": {"name": "Madrid Barajas",          "iata": "MAD", "lat": 40.472,  "lon":  -3.561},
    "LIRF": {"name": "Rome Fiumicino",          "iata": "FCO", "lat": 41.800,  "lon":  12.239},
    "LTFM": {"name": "Istanbul New Airport",    "iata": "IST", "lat": 41.275,  "lon":  28.752},
    "LLBG": {"name": "Tel Aviv Ben Gurion",     "iata": "TLV", "lat": 32.011,  "lon":  34.887},
    "OIII": {"name": "Tehran Imam Khomeini",    "iata": "IKA", "lat": 35.416,  "lon":  51.152},
    "ORBI": {"name": "Baghdad International",   "iata": "BGW", "lat": 33.263,  "lon":  44.235},
    "OLBA": {"name": "Beirut Rafic Hariri",     "iata": "BEY", "lat": 33.821,  "lon":  35.488},
    "OYSN": {"name": "Sanaa International",     "iata": "SAH", "lat": 15.478,  "lon":  44.220},
    "HSSS": {"name": "Khartoum",                "iata": "KRT", "lat": 15.590,  "lon":  32.553},
    "EHAM": {"name": "Amsterdam Schiphol",      "iata": "AMS", "lat": 52.308,  "lon":   4.764},
    "EDDM": {"name": "Munich",                  "iata": "MUC", "lat": 48.354,  "lon":  11.786},
    "LSZH": {"name": "Zurich",                  "iata": "ZRH", "lat": 47.464,  "lon":   8.549},
    "LOWW": {"name": "Vienna",                  "iata": "VIE", "lat": 48.110,  "lon":  16.569},
    "OMAA": {"name": "Abu Dhabi",               "iata": "AUH", "lat": 24.433,  "lon":  54.651},
    "OOMS": {"name": "Muscat",                  "iata": "MCT", "lat": 23.594,  "lon":  58.284},
    "OPKC": {"name": "Karachi Jinnah",          "iata": "KHI", "lat": 24.906,  "lon":  67.161},
    "OPLR": {"name": "Lahore Allama Iqbal",     "iata": "LHE", "lat": 31.521,  "lon":  74.403},
    "VHHH": {"name": "Hong Kong",               "iata": "HKG", "lat": 22.308,  "lon": 113.915},
    "RKSI": {"name": "Seoul Incheon",           "iata": "ICN", "lat": 37.469,  "lon": 126.451},
    "VTBS": {"name": "Bangkok Suvarnabhumi",    "iata": "BKK", "lat": 13.681,  "lon": 100.747},
    "WMKK": {"name": "Kuala Lumpur",            "iata": "KUL", "lat":  2.746,  "lon": 101.710},
    "WIII": {"name": "Jakarta Soekarno-Hatta",  "iata": "CGK", "lat": -6.126,  "lon": 106.656},
    "SBGR": {"name": "Sao Paulo Guarulhos",     "iata": "GRU", "lat":-23.432,  "lon": -46.469},
    "SAEZ": {"name": "Buenos Aires Ezeiza",     "iata": "EZE", "lat":-34.822,  "lon": -58.536},
    "CYYZ": {"name": "Toronto Pearson",         "iata": "YYZ", "lat": 43.677,  "lon": -79.631},
    "YSME": {"name": "Melbourne",               "iata": "MEL", "lat":-37.673,  "lon": 144.843},
    "NZAA": {"name": "Auckland",                "iata": "AKL", "lat":-37.008,  "lon": 174.792},
    "DNMM": {"name": "Lagos Murtala",           "iata": "LOS", "lat":  6.577,  "lon":   3.321},
    "GMMN": {"name": "Casablanca Mohammed V",   "iata": "CMN", "lat": 33.368,  "lon":  -7.590},
    "KEWR": {"name": "New York Newark",         "iata": "EWR", "lat": 40.690,  "lon": -74.175},
    "KATL": {"name": "Atlanta Hartsfield",      "iata": "ATL", "lat": 33.637,  "lon": -84.428},
    # UK airports
    "EGCC": {"name": "Manchester",              "iata": "MAN", "lat": 53.354,  "lon":  -2.275},
    "EGBB": {"name": "Birmingham",              "iata": "BHX", "lat": 52.454,  "lon":  -1.748},
    "EGPH": {"name": "Edinburgh",               "iata": "EDI", "lat": 55.950,  "lon":  -3.373},
    "EGPF": {"name": "Glasgow",                 "iata": "GLA", "lat": 55.872,  "lon":  -4.433},
    "EGGD": {"name": "Bristol",                 "iata": "BRS", "lat": 51.382,  "lon":  -2.719},
    "EGNX": {"name": "East Midlands",           "iata": "EMA", "lat": 52.831,  "lon":  -1.328},
    "EGKK": {"name": "London Gatwick",          "iata": "LGW", "lat": 51.148,  "lon":  -0.190},
    "EGSS": {"name": "London Stansted",         "iata": "STN", "lat": 51.885,  "lon":   0.235},
    # Middle East
    "OJAM": {"name": "Amman Queen Alia",        "iata": "AMM", "lat": 31.723,  "lon":  35.993},
    "OMAA": {"name": "Abu Dhabi",               "iata": "AUH", "lat": 24.433,  "lon":  54.651},
    "OOMS": {"name": "Muscat",                  "iata": "MCT", "lat": 23.594,  "lon":  58.284},
    # South Asia
    "OPKC": {"name": "Karachi Jinnah",          "iata": "KHI", "lat": 24.906,  "lon":  67.161},
    "OPLR": {"name": "Lahore Allama Iqbal",     "iata": "LHE", "lat": 31.521,  "lon":  74.403},
    "VECC": {"name": "Kolkata",                 "iata": "CCU", "lat": 22.655,  "lon":  88.447},
    "VOMM": {"name": "Chennai",                 "iata": "MAA", "lat": 12.990,  "lon":  80.169},
    # More Asia/Pacific
    "VHHH": {"name": "Hong Kong",               "iata": "HKG", "lat": 22.308,  "lon": 113.915},
    "RKSI": {"name": "Seoul Incheon",           "iata": "ICN", "lat": 37.469,  "lon": 126.451},
    "VTBS": {"name": "Bangkok Suvarnabhumi",    "iata": "BKK", "lat": 13.681,  "lon": 100.747},
    "WMKK": {"name": "Kuala Lumpur",            "iata": "KUL", "lat":  2.746,  "lon": 101.710},
    "WIII": {"name": "Jakarta Soekarno-Hatta",  "iata": "CGK", "lat": -6.126,  "lon": 106.656},
    "YSME": {"name": "Melbourne",               "iata": "MEL", "lat":-37.673,  "lon": 144.843},
    "NZAA": {"name": "Auckland",                "iata": "AKL", "lat":-37.008,  "lon": 174.792},
    # Americas
    "SBGR": {"name": "Sao Paulo Guarulhos",     "iata": "GRU", "lat":-23.432,  "lon": -46.469},
    "SAEZ": {"name": "Buenos Aires Ezeiza",     "iata": "EZE", "lat":-34.822,  "lon": -58.536},
    "CYYZ": {"name": "Toronto Pearson",         "iata": "YYZ", "lat": 43.677,  "lon": -79.631},
    "CYVR": {"name": "Vancouver",               "iata": "YVR", "lat": 49.194,  "lon":-123.184},
    "KIAH": {"name": "Houston George Bush",     "iata": "IAH", "lat": 29.980,  "lon": -95.340},
    "KMIA": {"name": "Miami",                   "iata": "MIA", "lat": 25.796,  "lon": -80.287},
    "KSFO": {"name": "San Francisco",           "iata": "SFO", "lat": 37.619,  "lon":-122.375},
    # More Europe
    "EHAM": {"name": "Amsterdam Schiphol",      "iata": "AMS", "lat": 52.308,  "lon":   4.764},
    "EDDM": {"name": "Munich",                  "iata": "MUC", "lat": 48.354,  "lon":  11.786},
    "LSZH": {"name": "Zurich",                  "iata": "ZRH", "lat": 47.464,  "lon":   8.549},
    "LOWW": {"name": "Vienna",                  "iata": "VIE", "lat": 48.110,  "lon":  16.569},
}

# ── Airline names ─────────────────────────────────────────────────────────────
AIRLINE_NAMES = {
    "EK": "Emirates",
    "EY": "Etihad Airways",
    "QR": "Qatar Airways",
    "GF": "Gulf Air",
    "WY": "Oman Air",
    "FZ": "flydubai",
    "G9": "Air Arabia",
    "TK": "Turkish Airlines",
    "BA": "British Airways",
    "VS": "Virgin Atlantic",
    "LH": "Lufthansa",
    "AF": "Air France",
    "KL": "KLM",
    "IB": "Iberia",
    "VY": "Vueling",
    "FR": "Ryanair",
    "U2": "easyJet",
    "W6": "Wizz Air",
    "PC": "Pegasus Airlines",
    "OS": "Austrian Airlines",
    "LX": "Swiss International",
    "AY": "Finnair",
    "SK": "Scandinavian Airlines",
    "AZ": "ITA Airways",
    "TP": "TAP Air Portugal",
    "UA": "United Airlines",
    "AA": "American Airlines",
    "DL": "Delta Air Lines",
    "AC": "Air Canada",
    "WS": "WestJet",
    "B6": "JetBlue",
    "WN": "Southwest Airlines",
    "AS": "Alaska Airlines",
    "QF": "Qantas",
    "VA": "Virgin Australia",
    "NZ": "Air New Zealand",
    "SQ": "Singapore Airlines",
    "CX": "Cathay Pacific",
    "MH": "Malaysia Airlines",
    "TG": "Thai Airways",
    "AI": "Air India",
    "6E": "IndiGo",
    "PK": "Pakistan International Airlines",
    "NH": "All Nippon Airways",
    "JL": "Japan Airlines",
    "KE": "Korean Air",
    "OZ": "Asiana Airlines",
    "CI": "China Airlines",
    "CA": "Air China",
    "MU": "China Eastern",
    "CZ": "China Southern",
    "BR": "EVA Air",
    "ET": "Ethiopian Airlines",
    "MS": "EgyptAir",
    "AT": "Royal Air Maroc",
    "RJ": "Royal Jordanian",
    "ME": "Middle East Airlines",
    "SV": "Saudia",
    "WB": "RwandAir",
    "KQ": "Kenya Airways",
    "SA": "South African Airways",
    "LA": "LATAM Airlines",
    "G3": "Gol",
    "CM": "Copa Airlines",
    "AV": "Avianca",
    "AM": "Aeromexico",
    "SU": "Aeroflot",
    "LO": "LOT Polish Airlines",
    "OK": "Czech Airlines",
    "RO": "TAROM",
    "A3": "Aegean Airlines",
    "OA": "Olympic Air",
}

# IATA → (lat, lon) lookup for safety checking
IATA_COORDS = {v["iata"]: (v["lat"], v["lon"]) for v in AIRPORTS.values()}
# IATA → ICAO reverse lookup (needed for OpenSky which uses ICAO airport codes)
IATA_TO_ICAO = {v["iata"]: k for k, v in AIRPORTS.items()}

# ── Airspace closures ─────────────────────────────────────────────────────────
STATIC_CLOSURES = [
    {"id": "IR-OIIX", "name": "Iran FIR – Partial closure",      "country": "Iran",             "risk": "high",
     "polygon": [[38.0,44.0],[38.0,63.5],[25.0,63.5],[25.0,44.0]]},
    {"id": "IQ-ORBB", "name": "Iraq FIR – Conflict zones",       "country": "Iraq",             "risk": "high",
     "polygon": [[37.5,38.8],[37.5,48.8],[29.0,48.8],[29.0,38.8]]},
    {"id": "YE-OYSC", "name": "Yemen FIR – Full closure",        "country": "Yemen",            "risk": "high",
     "polygon": [[19.0,41.5],[19.0,53.5],[11.5,53.5],[11.5,41.5]]},
    {"id": "SY-OSTT", "name": "Syria FIR – Full closure",        "country": "Syria",            "risk": "high",
     "polygon": [[37.5,35.7],[37.5,42.5],[32.3,42.5],[32.3,35.7]]},
    {"id": "IL-LLLL", "name": "Israel/Palestine – Restricted",   "country": "Israel/Palestine", "risk": "high",
     "polygon": [[33.5,34.2],[33.5,35.9],[29.4,35.9],[29.4,34.2]]},
    {"id": "LB-OLLL", "name": "Lebanon FIR – Restricted",        "country": "Lebanon",          "risk": "medium",
     "polygon": [[34.7,35.1],[34.7,36.7],[33.0,36.7],[33.0,35.1]]},
    {"id": "SD-HSSS", "name": "Sudan – Conflict zones",          "country": "Sudan",            "risk": "medium",
     "polygon": [[22.0,23.5],[22.0,38.5],[10.0,38.5],[10.0,23.5]]},
]

# ── Amadeus token cache ───────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}

async def get_amadeus_token():
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://test.api.amadeus.com/v1/security/oauth2/token",
            data={"grant_type": "client_credentials",
                  "client_id": AMADEUS_KEY,
                  "client_secret": AMADEUS_SECRET},
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data["expires_in"]
    return _token_cache["token"]

# ── Safety helpers ────────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def point_in_polygon(lat, lon, polygon):
    n, inside, j = len(polygon), False, len(polygon)-1
    for i in range(n):
        xi, yi = polygon[i][1], polygon[i][0]
        xj, yj = polygon[j][1], polygon[j][0]
        if ((yi > lat) != (yj > lat)) and (lon < (xj-xi)*(lat-yi)/(yj-yi)+xi):
            inside = not inside
        j = i
    return inside

def segment_crosses_closure(lat1, lon1, lat2, lon2, polygon, steps=30):
    for i in range(steps+1):
        t = i/steps
        if point_in_polygon(lat1+t*(lat2-lat1), lon1+t*(lon2-lon1), polygon):
            return True
    return False

def path_is_safe(lat1, lon1, lat2, lon2, closures):
    return all(not segment_crosses_closure(lat1, lon1, lat2, lon2, c["polygon"]) for c in closures if c.get("polygon"))

def build_waypoints(closures):
    waypoints = {}
    margin = 1.5
    for c in closures:
        if not c.get("polygon"):
            continue
        poly = c["polygon"]
        lats = [p[0] for p in poly]; lons = [p[1] for p in poly]
        corners = [
            (min(lats)-margin, min(lons)-margin), (min(lats)-margin, max(lons)+margin),
            (max(lats)+margin, min(lons)-margin), (max(lats)+margin, max(lons)+margin),
            ((min(lats)+max(lats))/2, min(lons)-margin), ((min(lats)+max(lats))/2, max(lons)+margin),
            (min(lats)-margin, (min(lons)+max(lons))/2), (max(lats)+margin, (min(lons)+max(lons))/2),
        ]
        for i, (wlat, wlon) in enumerate(corners):
            waypoints[f"{c['id']}_wp{i}"] = {"lat": wlat, "lon": wlon}
    return waypoints

def find_route(origin_icao, dest_icao, closures):
    if origin_icao not in AIRPORTS or dest_icao not in AIRPORTS:
        return None, None
    origin = AIRPORTS[origin_icao]; dest = AIRPORTS[dest_icao]
    waypoints = build_waypoints(closures)
    nodes = {"origin": origin, "dest": dest, **waypoints}
    open_heap = [(0, "origin", ["origin"])]; visited = set()
    while open_heap:
        cost, current, path = heapq.heappop(open_heap)
        if current in visited: continue
        visited.add(current)
        if current == "dest":
            return [{"lat": nodes[n]["lat"], "lon": nodes[n]["lon"]} for n in path], round(cost)
        cur = nodes[current]
        for nid, ndata in nodes.items():
            if nid in visited: continue
            if path_is_safe(cur["lat"], cur["lon"], ndata["lat"], ndata["lon"], closures):
                d = haversine(cur["lat"], cur["lon"], ndata["lat"], ndata["lon"])
                h = haversine(ndata["lat"], ndata["lon"], dest["lat"], dest["lon"])
                heapq.heappush(open_heap, (cost + d + h * 0.5, nid, path + [nid]))
    return [{"lat": origin["lat"], "lon": origin["lon"]}, {"lat": dest["lat"], "lon": dest["lon"]}], \
           round(haversine(origin["lat"], origin["lon"], dest["lat"], dest["lon"]))

def check_segment_safety(iata1: str, iata2: str, closures: list):
    c1, c2 = IATA_COORDS.get(iata1), IATA_COORDS.get(iata2)
    if not c1 or not c2:
        return "unknown", []
    affected = []
    for zone in closures:
        if not zone.get("polygon"):
            continue
        if segment_crosses_closure(c1[0], c1[1], c2[0], c2[1], zone["polygon"]):
            affected.append(zone)
    if not affected:
        return "safe", []
    if any(z["risk"] == "high" for z in affected):
        return "avoid", affected
    return "caution", affected

def rate_offer(offer: dict, closures: list):
    worst, zones = "safe", []
    for itin in offer.get("itineraries", []):
        for seg in itin.get("segments", []):
            dep = seg["departure"]["iataCode"]
            arr = seg["arrival"]["iataCode"]
            status, affected = check_segment_safety(dep, arr, closures)
            zones += [z for z in affected if z not in zones]
            if status == "avoid":
                worst = "avoid"
            elif status == "caution" and worst == "safe":
                worst = "caution"
    return worst, zones

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/airports")
def get_airports(q: Optional[str] = None):
    if q:
        ql = q.lower()
        return {k: v for k, v in AIRPORTS.items()
                if ql in k.lower() or ql in v["name"].lower() or ql in v["iata"].lower()}
    return AIRPORTS

@app.get("/closures")
async def get_closures():
    live = await fetch_live_notams()
    return {"closures": STATIC_CLOSURES + live}

@app.get("/flights")
async def search_flights(
    origin: str = Query(..., description="IATA code e.g. LHR"),
    destination: str = Query(..., description="IATA code e.g. DXB"),
    date: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        token = await get_amadeus_token()
    except Exception:
        raise HTTPException(502, "Could not authenticate with Amadeus")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://test.api.amadeus.com/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "originLocationCode":      origin.upper(),
                "destinationLocationCode": destination.upper(),
                "departureDate":           date,
                "adults":                  1,
                "max":                     15,
                "currencyCode":            "USD",
            },
        )

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text[:200])

    offers = r.json().get("data", [])
    closures_data = await get_closures()
    closures = closures_data["closures"]

    results = []
    for offer in offers:
        safety, affected_zones = rate_offer(offer, closures)
        itins = offer.get("itineraries", [])
        segments = itins[0].get("segments", []) if itins else []
        codes = offer.get("validatingAirlineCodes", [])
        results.append({
            "id":           offer["id"],
            "price":        offer.get("price", {}),
            "airline_codes": codes,
            "airline_names": [AIRLINE_NAMES.get(c, c) for c in codes],
            "segments":     segments,
            "duration":     itins[0].get("duration", "") if itins else "",
            "stops":        len(segments) - 1,
            "safety":       safety,
            "affected_zones": [z["name"] for z in affected_zones],
        })

    # Sort: safe first, then caution, then avoid
    order = {"safe": 0, "caution": 1, "avoid": 2}
    results.sort(key=lambda x: order.get(x["safety"], 3))
    return {"flights": results, "count": len(results)}

async def fetch_opensky_track(callsign: str, dep_icao: str) -> Optional[list]:
    """
    Fetch actual flight track from OpenSky Network using departure airport + callsign.
    Returns list of [lat, lon] waypoints, or None if unavailable.
    """
    try:
        now   = int(time.time())
        begin = now - 86400  # search last 24 hours
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(
                "https://opensky-network.org/api/flights/departure",
                params={"airport": dep_icao, "begin": begin, "end": now},
            )
            if r.status_code != 200:
                return None
            flights = r.json()
            cn = callsign.upper().replace(" ", "")
            match = next(
                (f for f in flights if f.get("callsign", "").strip().upper().startswith(cn[:6])),
                None
            )
            if not match:
                return None
            icao24    = match.get("icao24")
            first_seen = match.get("firstSeen", begin)
            tr = await client.get(
                "https://opensky-network.org/api/tracks/all",
                params={"icao24": icao24, "time": first_seen},
            )
            if tr.status_code != 200:
                return None
            path = tr.json().get("path", [])
            # path entries: [time, lat, lon, baro_alt, true_track, on_ground]
            waypoints = [[p[1], p[2]] for p in path if p[1] and p[2] and not p[5]]
            return waypoints if len(waypoints) > 4 else None
    except Exception:
        return None


def check_track_safety(waypoints: list, closures: list):
    """Check a multi-point track against all closure zones."""
    affected = []
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        for zone in closures:
            if not zone.get("polygon"):
                continue
            if zone in affected:
                continue
            if segment_crosses_closure(lat1, lon1, lat2, lon2, zone["polygon"], steps=10):
                affected.append(zone)
    if not affected:
        return "safe", []
    if any(z["risk"] == "high" for z in affected):
        return "avoid", affected
    return "caution", affected


@app.get("/check-flight")
async def check_flight(flight_number: str = Query(..., description="e.g. EK009")):
    fn = flight_number.upper().replace(" ", "")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "http://api.aviationstack.com/v1/flights",
            params={"access_key": AVSTACK_KEY, "flight_iata": fn, "limit": 1},
        )

    data = r.json().get("data", [])
    if not data:
        raise HTTPException(404, f"Flight {fn} not found. Check the flight number and try again.")

    flight   = data[0]
    dep_iata = flight.get("departure", {}).get("iata", "")
    arr_iata = flight.get("arrival",   {}).get("iata", "")
    dep_icao = IATA_TO_ICAO.get(dep_iata, "")

    closures_data = await get_closures()
    closures = closures_data["closures"]

    dep_coords = IATA_COORDS.get(dep_iata)
    arr_coords = IATA_COORDS.get(arr_iata)

    # Try to get real flight track from OpenSky for accurate checking
    track      = await fetch_opensky_track(fn, dep_icao) if dep_icao else None
    track_source = "live"

    if track and len(track) > 4:
        safety, affected = check_track_safety(track, closures)
        map_path = track  # full waypoint list for map
    else:
        # Fall back to straight-line check
        track_source = "estimated"
        safety, affected = check_segment_safety(dep_iata, arr_iata, closures)
        map_path = (
            [[dep_coords[0], dep_coords[1]], [arr_coords[0], arr_coords[1]]]
            if dep_coords and arr_coords else []
        )

    return {
        "flight_number":  fn,
        "airline":        flight.get("airline", {}).get("name", ""),
        "departure": {
            "iata":      dep_iata,
            "airport":   flight.get("departure", {}).get("airport", ""),
            "scheduled": flight.get("departure", {}).get("scheduled", ""),
            "coords":    {"lat": dep_coords[0], "lon": dep_coords[1]} if dep_coords else None,
        },
        "arrival": {
            "iata":      arr_iata,
            "airport":   flight.get("arrival", {}).get("airport", ""),
            "scheduled": flight.get("arrival", {}).get("scheduled", ""),
            "coords":    {"lat": arr_coords[0], "lon": arr_coords[1]} if arr_coords else None,
        },
        "status":         flight.get("flight_status", ""),
        "safety":         safety,
        "affected_zones": [z["name"] for z in affected],
        "track_source":   track_source,
        "map_path":       map_path,
        "closures":       closures,
    }

# ── Safe route (IATA-based) ───────────────────────────────────────────────────
@app.get("/safe-route")
async def get_safe_route(
    origin: str = Query(..., description="IATA code"),
    destination: str = Query(..., description="IATA code"),
):
    origin_icao = IATA_TO_ICAO.get(origin.upper())
    dest_icao   = IATA_TO_ICAO.get(destination.upper())
    if not origin_icao or not dest_icao:
        raise HTTPException(404, "One or both airports not found in database")
    closures_data = await get_closures()
    path, distance = find_route(origin_icao, dest_icao, closures_data["closures"])
    return {"path": path, "distance_km": distance}


# ── News feed ─────────────────────────────────────────────────────────────────
NEWS_SOURCES = [
    {"url": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "name": "BBC Middle East"},
    {"url": "https://avherald.com/h?subscribe=rss",                   "name": "Aviation Herald"},
    {"url": "https://www.flightglobal.com/rss/news",                  "name": "FlightGlobal"},
]
AIRSPACE_KEYWORDS = [
    "airspace", "notam", "closure", "flight ban", "aviation", "airline",
    "iran", "iraq", "yemen", "israel", "syria", "lebanon", "sudan",
    "restricted", "prohibited", "fir", "conflict zone",
]

@app.get("/news")
async def get_news():
    articles = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for source in NEWS_SOURCES:
            try:
                r = await client.get(source["url"])
                if r.status_code != 200:
                    continue
                root = ET.fromstring(r.content)
                for item in root.findall(".//item")[:12]:
                    title = (item.findtext("title") or "").strip()
                    link  = (item.findtext("link")  or "").strip()
                    desc  = (item.findtext("description") or "").strip()
                    date  = (item.findtext("pubDate") or "").strip()
                    combined = (title + " " + desc).lower()
                    if any(k in combined for k in AIRSPACE_KEYWORDS):
                        articles.append({
                            "title":  title,
                            "link":   link,
                            "source": source["name"],
                            "date":   date,
                        })
            except Exception:
                continue
    return {"articles": articles[:10]}


# ── Live NOTAMs ───────────────────────────────────────────────────────────────
async def fetch_live_notams():
    results = []
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            for fir in ["OIIX", "ORBB", "OYSC", "OSTT", "LLLL", "OLLL", "HSSS"]:
                r = await client.get(
                    f"https://aviationweather.gov/api/data/notam?icaos={fir}&format=json"
                )
                if r.status_code == 200:
                    for n in (r.json() if isinstance(r.json(), list) else []):
                        results.append({
                            "id":      n.get("notamID", ""),
                            "name":    n.get("text", "")[:80],
                            "country": fir,
                            "risk":    "medium",
                            "source":  "NOTAM",
                            "polygon": [],
                        })
    except Exception:
        pass
    return results
