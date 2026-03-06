import { useState, useEffect, useRef } from "react";
import axios from "axios";
import MapView from "./MapView";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
const DEFAULT_DATE = tomorrow.toISOString().split("T")[0];

// ── Safety colors ──────────────────────────────────────────────────────────────

// ── Helpers ───────────────────────────────────────────────────────────────────
function SafeBadge({ status }) {
  const cfg = { safe: "badge-safe", caution: "badge-caution", avoid: "badge-avoid" };
  return <span className={`safety-badge ${cfg[status] || "badge-unknown"}`}>{(status || "unknown").toUpperCase()}</span>;
}
const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--";
const fmtDur  = (d)   => d ? d.replace("PT","").replace("H","h ").replace("M","m").toLowerCase() : "";

function bookingUrl(origin, dest, date, type) {
  if (type === "google") return `https://www.google.com/flights?hl=en#flt=${origin}.${dest}.${date};c:USD;e:1;sd:1;t:f`;
  if (type === "skyscanner") return `https://www.skyscanner.net/transport/flights/${origin.toLowerCase()}/${dest.toLowerCase()}/${date.replace(/-/g, "").slice(2)}/`;
  return "#";
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]           = useState("search");
  const [airports, setAirports] = useState({});
  const [closures, setClosures] = useState([]);
  const [news, setNews]         = useState([]);
  const [newsOpen, setNewsOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(true);
  const sheetRef = useRef(null);
  const dragStart = useRef(null);

  // search
  const [originIata, setOriginIata] = useState("");
  const [destIata,   setDestIata]   = useState("");
  const [originQ,    setOriginQ]    = useState("");
  const [destQ,      setDestQ]      = useState("");
  const [originSugg, setOriginSugg] = useState([]);
  const [destSugg,   setDestSugg]   = useState([]);
  const [date,       setDate]       = useState(DEFAULT_DATE);
  const [flights,    setFlights]    = useState([]);
  const [flightLoad, setFlightLoad] = useState(false);
  const [flightErr,  setFlightErr]  = useState("");
  const [selectedId, setSelectedId] = useState(null);

  // check
  const [flightNum,   setFlightNum]   = useState("");
  const [checkResult, setCheckResult] = useState(null);
  const [checkLoad,   setCheckLoad]   = useState(false);
  const [checkErr,    setCheckErr]    = useState("");

  // map
  const [mainPath,   setMainPath]   = useState([]);
  const [safePath,   setSafePath]   = useState([]);
  const [mapSafety,  setMapSafety]  = useState("safe");
  const [depMarker,  setDepMarker]  = useState(null);
  const [arrMarker,  setArrMarker]  = useState(null);

  useEffect(() => {
    axios.get(`${API}/airports`).then(r => setAirports(r.data)).catch(() => {});
    axios.get(`${API}/closures`).then(r => setClosures(r.data.closures)).catch(() => {});
    axios.get(`${API}/news`).then(r => setNews(r.data.articles || [])).catch(() => {});
  }, []);

  // airport suggestions
  const suggest = (q, setSugg) => {
    if (!q || q.length < 2) { setSugg([]); return; }
    const ql = q.toLowerCase();
    setSugg(Object.entries(airports)
      .filter(([, v]) => v.name.toLowerCase().includes(ql) || v.iata.toLowerCase().includes(ql))
      .slice(0, 6));
  };

  const getCoords = (iata) => {
    const e = Object.values(airports).find(a => a.iata === iata);
    return e ? [e.lat, e.lon] : null;
  };

  // ── Flight search ──────────────────────────────────────────────────────────
  const handleSearch = async () => {
    if (!originIata || !destIata) { setFlightErr("Select both airports."); return; }
    if (originIata === destIata)  { setFlightErr("Origin and destination must differ."); return; }
    setFlightErr(""); setFlights([]); setSelectedId(null);
    setMainPath([]); setSafePath([]); setDepMarker(null); setArrMarker(null);
    setFlightLoad(true);
    try {
      const r = await axios.get(`${API}/flights`, { params: { origin: originIata, destination: destIata, date } });
      setFlights(r.data.flights || []);
      if (!r.data.flights?.length) setFlightErr("No flights found for this route and date.");
    } catch (e) {
      setFlightErr(e.response?.data?.detail || "Search failed. Is the backend running?");
    } finally { setFlightLoad(false); }
  };

  const selectFlight = async (flight) => {
    setSelectedId(flight.id);
    const segs = flight.segments || [];
    if (!segs.length) return;

    // Build main route path
    const coords = [];
    segs.forEach(seg => {
      const d = getCoords(seg.departure?.iataCode);
      const a = getCoords(seg.arrival?.iataCode);
      if (d) coords.push(d);
      if (a) coords.push(a);
    });
    const unique = coords.filter((c, i) => !i || JSON.stringify(c) !== JSON.stringify(coords[i-1]));
    setMainPath(unique);
    setMapSafety(flight.safety);
    setDepMarker(unique[0]);
    setArrMarker(unique[unique.length - 1]);
    setSafePath([]);

    // If caution or avoid, fetch safe alternative
    if (flight.safety !== "safe") {
      const dep = segs[0]?.departure?.iataCode;
      const arr = segs[segs.length-1]?.arrival?.iataCode;
      try {
        const r = await axios.get(`${API}/safe-route`, { params: { origin: dep, destination: arr } });
        const sp = (r.data.path || []).map(p => [p.lat, p.lon]);
        setSafePath(sp);
      } catch { /* silent */ }
    }
  };

  // ── Flight checker ─────────────────────────────────────────────────────────
  const handleCheck = async () => {
    if (!flightNum.trim()) { setCheckErr("Enter a flight number."); return; }
    setCheckErr(""); setCheckResult(null); setMainPath([]); setSafePath([]);
    setDepMarker(null); setArrMarker(null);
    setCheckLoad(true);
    try {
      const r = await axios.get(`${API}/check-flight`, { params: { flight_number: flightNum.trim() } });
      setCheckResult(r.data);
      if (r.data.map_path?.length > 1) {
        const path = r.data.map_path;
        setMainPath(path);
        setMapSafety(r.data.safety);
        setDepMarker(path[0]);
        setArrMarker(path[path.length - 1]);
      }
      // Fetch safe alternative if needed
      if (r.data.safety !== "safe") {
        const dep = r.data.departure?.iata;
        const arr = r.data.arrival?.iata;
        if (dep && arr) {
          try {
            const sr = await axios.get(`${API}/safe-route`, { params: { origin: dep, destination: arr } });
            setSafePath((sr.data.path || []).map(p => [p.lat, p.lon]));
          } catch { /* silent */ }
        }
      }
    } catch (e) {
      setCheckErr(e.response?.data?.detail || "Flight not found.");
    } finally { setCheckLoad(false); }
  };

  const depIata = tab === "search"
    ? flights.find(f => f.id === selectedId)?.segments?.[0]?.departure?.iataCode
    : checkResult?.departure?.iata;
  const arrIata = tab === "search"
    ? flights.find(f => f.id === selectedId)?.segments?.at(-1)?.arrival?.iataCode
    : checkResult?.arrival?.iata;

  // Touch drag to open/close sheet on mobile
  const onDragStart = (e) => {
    dragStart.current = e.touches?.[0]?.clientY ?? e.clientY;
  };
  const onDragEnd = (e) => {
    const end = e.changedTouches?.[0]?.clientY ?? e.clientY;
    if (dragStart.current === null) return;
    const diff = end - dragStart.current;
    if (diff > 50)  setSheetOpen(false);
    if (diff < -50) setSheetOpen(true);
    dragStart.current = null;
  };

  return (
    <div className="app">
      {/* ══════════════ SIDEBAR / BOTTOM SHEET ══════════════ */}
      <aside className={`sidebar ${sheetOpen ? "sheet-open" : "sheet-closed"}`} ref={sheetRef}>

        {/* Drag handle — mobile only */}
        <div
          className="drag-handle"
          onTouchStart={onDragStart}
          onTouchEnd={onDragEnd}
          onMouseDown={onDragStart}
          onMouseUp={onDragEnd}
          onClick={() => setSheetOpen(o => !o)}
        >
          <div className="drag-bar" />
        </div>

        <div className="brand">
          <span className="brand-icon">✈</span>
          <span className="brand-name">AirspaceRouter</span>
        </div>
        <p className="tagline">Find safe flights around Middle East airspace closures</p>

        <div className="tabs">
          <button className={tab === "search" ? "tab active" : "tab"} onClick={() => setTab("search")}>Search Flights</button>
          <button className={tab === "check"  ? "tab active" : "tab"} onClick={() => setTab("check")}>Check My Flight</button>
        </div>

        {/* ── Search Flights ── */}
        {tab === "search" && (
          <div className="tab-content">
            <div className="field">
              <label>From</label>
              <input placeholder="City or airport code…" value={originQ}
                onChange={e => { setOriginQ(e.target.value); suggest(e.target.value, setOriginSugg); }} />
              {originSugg.length > 0 && (
                <ul className="suggestions">
                  {originSugg.map(([icao, v]) => (
                    <li key={icao} onClick={() => { setOriginIata(v.iata); setOriginQ(`${v.name} (${v.iata})`); setOriginSugg([]); }}>
                      <strong>{v.iata}</strong> — {v.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="field">
              <label>To</label>
              <input placeholder="City or airport code…" value={destQ}
                onChange={e => { setDestQ(e.target.value); suggest(e.target.value, setDestSugg); }} />
              {destSugg.length > 0 && (
                <ul className="suggestions">
                  {destSugg.map(([icao, v]) => (
                    <li key={icao} onClick={() => { setDestIata(v.iata); setDestQ(`${v.name} (${v.iata})`); setDestSugg([]); }}>
                      <strong>{v.iata}</strong> — {v.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="field">
              <label>Date</label>
              <input type="date" value={date} min={DEFAULT_DATE} onChange={e => setDate(e.target.value)} />
            </div>

            <button className="btn-primary" onClick={handleSearch} disabled={flightLoad}>
              {flightLoad ? "Searching…" : "Search Flights"}
            </button>
            {flightErr && <p className="error">{flightErr}</p>}

            {flights.length > 0 && (
              <div className="flight-list">
                <p className="results-count">{flights.length} flights — click to view on map</p>
                {flights.map(f => {
                  const depIataF = f.segments?.[0]?.departure?.iataCode;
                  const arrIataF = f.segments?.at(-1)?.arrival?.iataCode;
                  return (
                    <div key={f.id} className={`flight-card ${selectedId === f.id ? "selected" : ""} border-${f.safety}`} onClick={() => selectFlight(f)}>
                      <div className="flight-top">
                        <div className="flight-airline">{f.airline_names?.[0] || f.airline_codes?.[0] || "—"}</div>
                        <SafeBadge status={f.safety} />
                      </div>
                      <div className="flight-route">
                        <span>{depIataF} <span className="time">{fmtTime(f.segments?.[0]?.departure?.at)}</span></span>
                        <span className="arrow">──✈──</span>
                        <span>{arrIataF} <span className="time">{fmtTime(f.segments?.at(-1)?.arrival?.at)}</span></span>
                      </div>
                      <div className="flight-meta">
                        <span>{fmtDur(f.duration)}</span>
                        <span>{f.stops === 0 ? "Direct" : `${f.stops} stop${f.stops > 1 ? "s" : ""}`}</span>
                        <span className="price">${parseFloat(f.price?.total || 0).toLocaleString()}</span>
                      </div>
                      {f.affected_zones?.length > 0 && (
                        <div className="affected-zones">⚠ Crosses: {f.affected_zones.join(", ")}</div>
                      )}
                      {/* Booking links */}
                      <div className="booking-links" onClick={e => e.stopPropagation()}>
                        <a href={bookingUrl(depIataF, arrIataF, date, "google")} target="_blank" rel="noreferrer" className="book-btn google">
                          Google Flights
                        </a>
                        <a href={bookingUrl(depIataF, arrIataF, date, "skyscanner")} target="_blank" rel="noreferrer" className="book-btn skyscanner">
                          Skyscanner
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Check My Flight ── */}
        {tab === "check" && (
          <div className="tab-content">
            <p className="check-desc">Enter your flight number to check if it passes through any closed airspace.</p>
            <div className="field">
              <label>Flight Number</label>
              <input placeholder="e.g. EK009, TK4" value={flightNum}
                onChange={e => setFlightNum(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCheck()} />
            </div>
            <button className="btn-primary" onClick={handleCheck} disabled={checkLoad}>
              {checkLoad ? "Checking…" : "Check Flight"}
            </button>
            {checkErr && <p className="error">{checkErr}</p>}

            {checkResult && (
              <div className="check-result">
                <div className="check-header">
                  <div>
                    <div className="check-flightnum">{checkResult.flight_number}</div>
                    <div className="check-airline">{checkResult.airline}</div>
                  </div>
                  <SafeBadge status={checkResult.safety} />
                </div>
                <div className="check-route">
                  <div className="check-airport">
                    <div className="check-iata">{checkResult.departure?.iata}</div>
                    <div className="check-apname">{checkResult.departure?.airport}</div>
                    <div className="check-time">{fmtTime(checkResult.departure?.scheduled)}</div>
                  </div>
                  <div className="check-arrow">✈</div>
                  <div className="check-airport">
                    <div className="check-iata">{checkResult.arrival?.iata}</div>
                    <div className="check-apname">{checkResult.arrival?.airport}</div>
                    <div className="check-time">{fmtTime(checkResult.arrival?.scheduled)}</div>
                  </div>
                </div>
                <div className={`verdict ${checkResult.safety}`}>
                  {checkResult.safety === "safe"    && "This flight does not cross any active airspace closures."}
                  {checkResult.safety === "caution" && `Passes near restricted zones: ${checkResult.affected_zones?.join(", ")}.`}
                  {checkResult.safety === "avoid"   && `Crosses high-risk airspace: ${checkResult.affected_zones?.join(", ")}. Contact your airline.`}
                </div>
                {checkResult.safety !== "safe" && safePath.length > 0 && (
                  <div className="alt-route-notice">Safe alternative route shown in green on map</div>
                )}
                <div className={`track-source ${checkResult.track_source}`}>
                  {checkResult.track_source === "live" ? "Live flight track — high accuracy" : "Estimated straight-line route"}
                </div>
                <div className="booking-links">
                  <a href={bookingUrl(checkResult.departure?.iata, checkResult.arrival?.iata, DEFAULT_DATE, "google")} target="_blank" rel="noreferrer" className="book-btn google">
                    Google Flights
                  </a>
                  <a href={bookingUrl(checkResult.departure?.iata, checkResult.arrival?.iata, DEFAULT_DATE, "skyscanner")} target="_blank" rel="noreferrer" className="book-btn skyscanner">
                    Skyscanner
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── News Feed ── */}
        <div className="news-panel">
          <button className="news-toggle" onClick={() => setNewsOpen(o => !o)}>
            <span>Aviation News</span>
            {news.length > 0 && <span className="news-count">{news.length}</span>}
            <span className="news-chevron">{newsOpen ? "▲" : "▼"}</span>
          </button>
          {newsOpen && (
            <div className="news-list">
              {news.length === 0 && <p className="no-news">No relevant news at the moment.</p>}
              {news.map((n, i) => (
                <a key={i} href={n.link} target="_blank" rel="noreferrer" className="news-item">
                  <div className="news-title">{n.title}</div>
                  <div className="news-meta">{n.source} · {n.date ? new Date(n.date).toLocaleDateString() : ""}</div>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* ── Legend ── */}
        <div className="legend">
          <div className="legend-item"><span className="dot red"></span> High-risk closure</div>
          <div className="legend-item"><span className="dot orange"></span> Medium-risk closure</div>
          <div className="legend-item"><span className="line green"></span> Safe / alternative route</div>
          <div className="legend-item"><span className="line orange"></span> Caution route</div>
          <div className="legend-item"><span className="line red"></span> Avoid route</div>
        </div>
      </aside>

      {/* ══════════════ MAP ══════════════ */}
      <main className="map-wrap">
        <MapView
          closures={closures}
          mainPath={mainPath}
          safePath={safePath}
          mapSafety={mapSafety}
          depMarker={depMarker}
          arrMarker={arrMarker}
          depIata={depIata}
          arrIata={arrIata}
        />
      </main>
    </div>
  );
}
