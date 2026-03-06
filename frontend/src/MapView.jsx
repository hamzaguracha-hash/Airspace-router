import { useState, useEffect, useRef } from 'react';
import Map, { Source, Layer, Marker, Popup, NavigationControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import './MapView.css';

const SAFETY_COLOR = { safe: '#22c55e', caution: '#f97316', avoid: '#ef4444' };
const RISK_COLOR   = { high: '#ef4444', medium: '#f97316' };

// ── Great circle arc between two [lat,lon] points ────────────────────────────
function slerp(lon1, lat1, lon2, lat2, t) {
  const R = Math.PI / 180;
  const [la1, lo1, la2, lo2] = [lat1*R, lon1*R, lat2*R, lon2*R];
  const x1 = Math.cos(la1)*Math.cos(lo1), y1 = Math.cos(la1)*Math.sin(lo1), z1 = Math.sin(la1);
  const x2 = Math.cos(la2)*Math.cos(lo2), y2 = Math.cos(la2)*Math.sin(lo2), z2 = Math.sin(la2);
  const dot = Math.max(-1, Math.min(1, x1*x2 + y1*y2 + z1*z2));
  const omega = Math.acos(dot);
  if (Math.abs(omega) < 0.0001) return [lon1, lat1];
  const s = Math.sin(omega);
  const A = Math.sin((1-t)*omega)/s, B = Math.sin(t*omega)/s;
  const x=A*x1+B*x2, y=A*y1+B*y2, z=A*z1+B*z2;
  return [Math.atan2(y,x)/R, Math.atan2(z, Math.sqrt(x*x+y*y))/R];
}

function buildArc(path, steps = 100) {
  if (!path || path.length < 2) return [];
  const coords = [];
  for (let i = 0; i < path.length - 1; i++) {
    const [lat1, lon1] = Array.isArray(path[i]) ? path[i] : [path[i].lat, path[i].lon];
    const [lat2, lon2] = Array.isArray(path[i+1]) ? path[i+1] : [path[i+1].lat, path[i+1].lon];
    for (let s = 0; s <= steps; s++) coords.push(slerp(lon1, lat1, lon2, lat2, s/steps));
  }
  return coords;
}

function arcToGeoJSON(coords) {
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: coords }, properties: {} };
}

function closuresToGeoJSON(closures) {
  return {
    type: 'FeatureCollection',
    features: (closures || []).filter(c => c.polygon?.length > 2).map(c => ({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[...c.polygon.map(p => [p[1], p[0]]), [c.polygon[0][1], c.polygon[0][0]]]],
      },
      properties: { name: c.name, country: c.country, risk: c.risk },
    })),
  };
}

// ── Bearing between two lon/lat points ───────────────────────────────────────
function bearing(lon1, lat1, lon2, lat2) {
  const R = Math.PI / 180;
  const dLon = (lon2 - lon1) * R;
  const y = Math.sin(dLon) * Math.cos(lat2 * R);
  const x = Math.cos(lat1*R)*Math.sin(lat2*R) - Math.sin(lat1*R)*Math.cos(lat2*R)*Math.cos(dLon);
  return Math.atan2(y, x) * 180 / Math.PI;
}

export default function MapView({ closures, mainPath, safePath, mapSafety, depMarker, arrMarker, depIata, arrIata }) {
  const mapRef      = useRef(null);
  const animRef     = useRef(null);
  const startRef    = useRef(null);
  const [mapLoaded, setMapLoaded]       = useState(false);
  const [planePos,  setPlanePos]        = useState(null);
  const [planeBearing, setPlaneBearing] = useState(0);
  const [popup,     setPopup]           = useState(null);

  const mainArc    = buildArc(mainPath);
  const safeArc    = buildArc(safePath);
  const closureGJ  = closuresToGeoJSON(closures);
  const routeColor = SAFETY_COLOR[mapSafety] || '#22c55e';

  // ── Animate plane along main arc ──────────────────────────────────────────
  useEffect(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    startRef.current = null;
    if (!mainArc.length) { setPlanePos(null); return; }

    const DURATION = 10000;
    const animate = (ts) => {
      if (!startRef.current) startRef.current = ts;
      const progress = ((ts - startRef.current) % DURATION) / DURATION;
      const idx      = Math.floor(progress * (mainArc.length - 1));
      const nextIdx  = Math.min(idx + 1, mainArc.length - 1);
      const [lon, lat]   = mainArc[idx];
      const [nlon, nlat] = mainArc[nextIdx];
      setPlanePos([lon, lat]);
      setPlaneBearing(bearing(lon, lat, nlon, nlat));
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animRef.current);
  }, [mainPath]);

  // ── Fly to route when path changes ────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !mainArc.length) return;
    const lons = mainArc.map(p => p[0]);
    const lats = mainArc.map(p => p[1]);
    mapRef.current.fitBounds(
      [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: 80, duration: 1800 }
    );
  }, [mainPath]);

  const depLon = depMarker ? depMarker[1] : null;
  const depLat = depMarker ? depMarker[0] : null;
  const arrLon = arrMarker ? arrMarker[1] : null;
  const arrLat = arrMarker ? arrMarker[0] : null;

  return (
    <div className="mapview">
      <Map
        ref={mapRef}
        initialViewState={{ longitude: 45, latitude: 28, zoom: 4 }}
        style={{ width: '100%', height: '100%' }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        onLoad={() => setMapLoaded(true)}
        interactiveLayerIds={mapLoaded ? ['closure-fill'] : []}
        onClick={e => {
          const f = e.features?.[0];
          f ? setPopup({ lon: e.lngLat.lng, lat: e.lngLat.lat, ...f.properties }) : setPopup(null);
        }}
        cursor="auto"
      >
        <NavigationControl position="top-right" />

        {mapLoaded && (
          <>
            {/* ── Closure zones ── */}
            <Source id="closures" type="geojson" data={closureGJ}>
              <Layer id="closure-fill" type="fill"
                paint={{ 'fill-color': ['case',['==',['get','risk'],'high'],'#ef4444','#f97316'], 'fill-opacity': 0.18 }} />
              <Layer id="closure-glow" type="line"
                paint={{ 'line-color': ['case',['==',['get','risk'],'high'],'#ef4444','#f97316'], 'line-width': 6, 'line-opacity': 0.12, 'line-blur': 6 }} />
              <Layer id="closure-outline" type="line"
                paint={{ 'line-color': ['case',['==',['get','risk'],'high'],'#ef4444','#f97316'], 'line-width': 1.5, 'line-opacity': 0.85 }} />
              <Layer id="closure-label" type="symbol"
                layout={{ 'text-field': ['get','country'], 'text-size': 11, 'text-font': ['Open Sans Bold','Arial Unicode MS Bold'], 'text-anchor': 'center' }}
                paint={{ 'text-color': '#fca5a5', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 }} />
            </Source>

            {/* ── Safe alternative route ── */}
            {safeArc.length > 1 && (
              <Source id="safe-arc" type="geojson" data={arcToGeoJSON(safeArc)}>
                <Layer id="safe-arc-glow" type="line"
                  paint={{ 'line-color': '#22c55e', 'line-width': 8, 'line-opacity': 0.12, 'line-blur': 5 }} />
                <Layer id="safe-arc-line" type="line"
                  paint={{ 'line-color': '#22c55e', 'line-width': 2, 'line-opacity': 0.75, 'line-dasharray': [4, 3] }} />
              </Source>
            )}

            {/* ── Main flight route ── */}
            {mainArc.length > 1 && (
              <Source id="main-arc" type="geojson" data={arcToGeoJSON(mainArc)}>
                <Layer id="main-arc-glow" type="line"
                  paint={{ 'line-color': routeColor, 'line-width': 14, 'line-opacity': 0.1, 'line-blur': 8 }} />
                <Layer id="main-arc-outer" type="line"
                  paint={{ 'line-color': routeColor, 'line-width': 4, 'line-opacity': 0.25 }} />
                <Layer id="main-arc-line" type="line"
                  paint={{ 'line-color': routeColor, 'line-width': 2.5, 'line-opacity': 1 }} />
              </Source>
            )}
          </>
        )}

        {/* ── Animated plane ── */}
        {planePos && (
          <Marker longitude={planePos[0]} latitude={planePos[1]} anchor="center">
            <div className="plane-icon" style={{ transform: `rotate(${planeBearing}deg)` }}>✈</div>
          </Marker>
        )}

        {/* ── Airport markers ── */}
        {depLon !== null && (
          <Marker longitude={depLon} latitude={depLat} anchor="bottom">
            <div className="airport-marker dep">
              <div className="marker-dot dep-dot" />
              <span>{depIata}</span>
            </div>
          </Marker>
        )}
        {arrLon !== null && (
          <Marker longitude={arrLon} latitude={arrLat} anchor="bottom">
            <div className="airport-marker arr">
              <div className="marker-dot arr-dot" />
              <span>{arrIata}</span>
            </div>
          </Marker>
        )}

        {/* ── Closure zone popup ── */}
        {popup && (
          <Popup longitude={popup.lon} latitude={popup.lat} onClose={() => setPopup(null)} anchor="top" closeButton>
            <div className="map-popup">
              <div className="popup-name">{popup.name}</div>
              <span className={`popup-risk ${popup.risk}`}>{popup.risk?.toUpperCase()} RISK</span>
              <div className="popup-hint">This zone is currently closed or restricted to commercial flights.</div>
            </div>
          </Popup>
        )}
      </Map>

      {/* ── Map legend ── */}
      <div className="map-legend">
        <div className="legend-title">Airspace Status</div>
        <div className="legend-row"><span className="l-zone high"></span> High-risk closure</div>
        <div className="legend-row"><span className="l-zone med"></span>  Medium-risk closure</div>
        <div className="legend-divider" />
        {mainArc.length > 0 && <>
          <div className="legend-row"><span className="l-line" style={{background: routeColor}}></span>
            {mapSafety === 'safe' ? 'Safe route' : mapSafety === 'caution' ? 'Caution route' : 'Avoid route'}
          </div>
          {safeArc.length > 0 &&
            <div className="legend-row"><span className="l-line green dashed"></span> Safe alternative</div>
          }
        </>}
      </div>
    </div>
  );
}
