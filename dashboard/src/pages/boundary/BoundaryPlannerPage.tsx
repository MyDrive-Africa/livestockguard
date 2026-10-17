/**
 * @file BoundaryPlannerPage.tsx
 * @description Standalone, read-only boundary planning tool for Sibanyoni Farm.
 *
 * ISOLATION GUARANTEE — this page does not touch the operational system:
 *   - It writes nothing to the `geofences` table (no POST/PUT/DELETE).
 *   - It generates no alerts and runs no breach detection.
 *   - It does not modify MapPage, simulators, beams, or robot presets.
 *
 * It draws candidate farm-boundary options over the 14 verified exclusion
 * structures so a human can compare them and decide. All planning geometry is
 * static (see planningData.ts). Live geofences may optionally be shown for
 * reference only, fetched read-only via GET /api/geofences.
 *
 * When an option is eventually chosen, promoting it into a real geofence is a
 * separate deliberate step that is intentionally NOT built here.
 */
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { apiClient } from '@/api/client';
import {
  SIBANYONI_CENTRE,
  STRUCTURES,
  BOUNDARY_OPTIONS,
  structureBuffers,
  clusterBuffers,
  type BoundaryOption,
} from './planningData';

const SIBANYONI_FARM_ID = 'dddddddd-1111-2222-3333-555555555555';

type BufferMode = 'structure' | 'cluster';

interface OptionVisibility {
  P1: boolean;
  P2: boolean;
  P3: boolean;
}

const TILES = {
  satellite: { tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'], attribution: '&copy; Google' },
  street: { tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], attribution: '&copy; OpenStreetMap contributors' },
};

const TYPE_EMOJI: Record<string, string> = { house: '🏠', compound: '🏘️', field: '🌾' };

export default function BoundaryPlannerPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const structureMarkersRef = useRef<maplibregl.Marker[]>([]);
  const liveFenceLayerIdsRef = useRef<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [tile, setTile] = useState<keyof typeof TILES>('satellite');

  // Toggle state
  const [showOptions, setShowOptions] = useState<OptionVisibility>({ P1: true, P2: true, P3: false });
  const [showStructures, setShowStructures] = useState(true);
  const [bufferMode, setBufferMode] = useState<BufferMode>('cluster');
  const [showBuffers, setShowBuffers] = useState(true);
  const [showLiveFences, setShowLiveFences] = useState(false);
  const [selectedOption, setSelectedOption] = useState<BoundaryOption['id'] | null>(null);

  // ─── Init map ─────────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const src = TILES[tile];
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        name: 'BoundaryPlanner',
        sources: { 'base-tiles': { type: 'raster', tiles: src.tiles, tileSize: 256, attribution: src.attribution } },
        layers: [{ id: 'base-layer', type: 'raster', source: 'base-tiles', minzoom: 0, maxzoom: 19 }],
      },
      center: [SIBANYONI_CENTRE.lon, SIBANYONI_CENTRE.lat],
      zoom: 14.5,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');
    map.on('load', () => {
      setLoading(false);
      // Ensure the canvas matches the (possibly late-sized) container.
      map.resize();
      try {
        drawAll(map);
      } catch (err) {
        // A drawing failure must not blank the whole page — the base map stays usable.
        console.error('[BoundaryPlanner] draw failed:', err);
      }
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Tile switching ───────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    const src = TILES[tile];
    if (map.getLayer('base-layer')) map.removeLayer('base-layer');
    if (map.getSource('base-tiles')) map.removeSource('base-tiles');
    map.addSource('base-tiles', { type: 'raster', tiles: src.tiles, tileSize: 256, attribution: src.attribution });
    const firstLayerId = map.getStyle().layers[0]?.id;
    map.addLayer({ id: 'base-layer', type: 'raster', source: 'base-tiles', minzoom: 0, maxzoom: 19 }, firstLayerId);
  }, [tile, loading]);

  // ─── Draw candidate boundary options ───────────────
  function drawOptions(map: maplibregl.Map) {
    BOUNDARY_OPTIONS.forEach((opt) => {
      const srcId = `opt-${opt.id}`;
      if (map.getSource(srcId)) return; // already added
      map.addSource(srcId, { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: opt.geometry } });
      map.addLayer({
        id: `opt-fill-${opt.id}`, type: 'fill', source: srcId,
        paint: { 'fill-color': opt.color, 'fill-opacity': 0.12 },
      });
      map.addLayer({
        id: `opt-line-${opt.id}`, type: 'line', source: srcId,
        // Draft options rendered dashed to distinguish from surveyed/baseline.
        paint: { 'line-color': opt.color, 'line-width': 3, 'line-dasharray': opt.draft ? [3, 2] : [1] },
      });

      // Exclusion pockets (P3) drawn as separate hatched red polygons.
      if (opt.pockets && opt.pockets.length > 0) {
        const pocketSrc = `opt-${opt.id}-pockets`;
        map.addSource(pocketSrc, { type: 'geojson', data: { type: 'FeatureCollection', features: opt.pockets } });
        map.addLayer({ id: `opt-pocket-fill-${opt.id}`, type: 'fill', source: pocketSrc, paint: { 'fill-color': '#ef4444', 'fill-opacity': 0.25 } });
        map.addLayer({ id: `opt-pocket-line-${opt.id}`, type: 'line', source: pocketSrc, paint: { 'line-color': '#ef4444', 'line-width': 1.5, 'line-dasharray': [2, 2] } });
      }
    });
  }

  function applyOptionVisibility(map: maplibregl.Map) {
    BOUNDARY_OPTIONS.forEach((opt) => {
      const vis = showOptions[opt.id] ? 'visible' : 'none';
      [`opt-fill-${opt.id}`, `opt-line-${opt.id}`, `opt-pocket-fill-${opt.id}`, `opt-pocket-line-${opt.id}`].forEach((id) => {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
      });
    });
  }

  // ─── Draw structure buffers ────────────────────────
  function drawBuffers(map: maplibregl.Map) {
    const structureFC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: structureBuffers() };
    const clusterFC: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: clusterBuffers() };

    if (!map.getSource('buf-structure')) {
      map.addSource('buf-structure', { type: 'geojson', data: structureFC });
      map.addLayer({ id: 'buf-structure-fill', type: 'fill', source: 'buf-structure', paint: { 'fill-color': '#f97316', 'fill-opacity': 0.18 } });
      map.addLayer({ id: 'buf-structure-line', type: 'line', source: 'buf-structure', paint: { 'line-color': '#f97316', 'line-width': 1.5 } });
    }
    if (!map.getSource('buf-cluster')) {
      map.addSource('buf-cluster', { type: 'geojson', data: clusterFC });
      map.addLayer({ id: 'buf-cluster-fill', type: 'fill', source: 'buf-cluster', paint: { 'fill-color': '#eab308', 'fill-opacity': 0.15 } });
      map.addLayer({ id: 'buf-cluster-line', type: 'line', source: 'buf-cluster', paint: { 'line-color': '#eab308', 'line-width': 2, 'line-dasharray': [2, 1] } });
    }
  }

  function applyBufferVisibility(map: maplibregl.Map) {
    const structureVis = showBuffers && bufferMode === 'structure' ? 'visible' : 'none';
    const clusterVis = showBuffers && bufferMode === 'cluster' ? 'visible' : 'none';
    ['buf-structure-fill', 'buf-structure-line'].forEach((id) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', structureVis); });
    ['buf-cluster-fill', 'buf-cluster-line'].forEach((id) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', clusterVis); });
  }

  // ─── Draw structure pins ───────────────────────────
  function drawStructures(map: maplibregl.Map) {
    structureMarkersRef.current.forEach((m) => m.remove());
    structureMarkersRef.current = [];
    STRUCTURES.forEach((s) => {
      const el = document.createElement('div');
      el.style.cssText = 'display:flex;flex-direction:column;align-items:center;';
      el.innerHTML = `<span style="font-size:16px;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.5));">${TYPE_EMOJI[s.type] || '📍'}</span>` +
        `<span style="font-size:9px;font-weight:bold;background:#dc2626;color:#fff;padding:0 3px;border-radius:3px;margin-top:-2px;white-space:nowrap;">${s.id}</span>`;
      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([s.lon, s.lat]).addTo(map);
      structureMarkersRef.current.push(marker);
    });
  }

  function applyStructureVisibility() {
    structureMarkersRef.current.forEach((m) => { m.getElement().style.display = showStructures ? 'flex' : 'none'; });
  }

  // ─── Live geofences (READ-ONLY reference) ──────────
  async function loadLiveFences(map: maplibregl.Map) {
    if (liveFenceLayerIdsRef.current.length > 0) return; // already loaded
    try {
      const resp = await apiClient.get('/api/geofences', { params: { farm_id: SIBANYONI_FARM_ID } });
      (resp.data as Array<{ id: string; name: string; geometry: GeoJSON.Polygon | null }>).forEach((f) => {
        if (!f.geometry) return;
        const srcId = `live-${f.id}`;
        if (map.getSource(srcId)) return;
        map.addSource(srcId, { type: 'geojson', data: { type: 'Feature', properties: { name: f.name }, geometry: f.geometry } });
        map.addLayer({ id: `live-line-${f.id}`, type: 'line', source: srcId, paint: { 'line-color': '#94a3b8', 'line-width': 1, 'line-opacity': 0.7, 'line-dasharray': [1, 2] } });
        liveFenceLayerIdsRef.current.push(f.id);
      });
    } catch {
      // Reference layer only — silently skip if the API is unavailable.
    }
  }

  function applyLiveFenceVisibility(map: maplibregl.Map) {
    const vis = showLiveFences ? 'visible' : 'none';
    liveFenceLayerIdsRef.current.forEach((id) => { if (map.getLayer(`live-line-${id}`)) map.setLayoutProperty(`live-line-${id}`, 'visibility', vis); });
  }

  // ─── Master draw (on load) ─────────────────────────
  function drawAll(map: maplibregl.Map) {
    drawOptions(map);
    drawBuffers(map);
    drawStructures(map);
    applyOptionVisibility(map);
    applyBufferVisibility(map);
    applyStructureVisibility();
  }

  // React to toggle changes
  useEffect(() => { const m = mapRef.current; if (m && !loading) applyOptionVisibility(m); }, [showOptions, loading]);
  useEffect(() => { const m = mapRef.current; if (m && !loading) applyBufferVisibility(m); }, [showBuffers, bufferMode, loading]);
  useEffect(() => { applyStructureVisibility(); }, [showStructures]);
  useEffect(() => {
    const m = mapRef.current;
    if (!m || loading) return;
    if (showLiveFences) loadLiveFences(m).then(() => applyLiveFenceVisibility(m));
    else applyLiveFenceVisibility(m);
  }, [showLiveFences, loading]);

  const selected = BOUNDARY_OPTIONS.find((o) => o.id === selectedOption);

  return (
    <div className="relative w-full h-full" style={{ height: '100%', width: '100%' }}>
      <div ref={mapContainerRef} className="absolute inset-0" style={{ width: '100%', height: '100%' }} />

      {/* Control panel */}
      <div className="absolute top-4 left-4 z-10 w-72 bg-white/95 dark:bg-gray-800/95 backdrop-blur rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4 max-h-[calc(100%-2rem)] overflow-y-auto">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-bold text-gray-900 dark:text-white">Boundary Planner</h2>
          <span className="text-[10px] uppercase tracking-wide bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 px-2 py-0.5 rounded">Planning · read-only</span>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Sibanyoni Farm · candidate boundaries vs. 14 exclusion structures. Nothing here is saved or alerted.</p>

        {/* Boundary options */}
        <div className="mb-3">
          <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Boundary options</div>
          {BOUNDARY_OPTIONS.map((opt) => (
            <label key={opt.id} className="flex items-start gap-2 py-1 cursor-pointer">
              <input
                type="checkbox"
                checked={showOptions[opt.id]}
                onChange={(e) => setShowOptions((prev) => ({ ...prev, [opt.id]: e.target.checked }))}
                className="mt-0.5"
              />
              <span className="flex-1 text-sm">
                <button
                  type="button"
                  onClick={() => setSelectedOption(selectedOption === opt.id ? null : opt.id)}
                  className="text-left font-medium hover:underline"
                  style={{ color: opt.color }}
                >
                  {opt.name}
                </button>
                <span className="block text-[11px] text-gray-500 dark:text-gray-400">
                  ~{opt.areaHa} ha · {opt.keepsRealCentre ? 'real centre' : 'moved west'}{opt.draft ? ' · draft' : ''}
                </span>
              </span>
            </label>
          ))}
        </div>

        {/* Structures + buffers */}
        <div className="mb-3 border-t border-gray-200 dark:border-gray-700 pt-3">
          <label className="flex items-center gap-2 py-1 cursor-pointer">
            <input type="checkbox" checked={showStructures} onChange={(e) => setShowStructures(e.target.checked)} />
            <span className="text-sm">Structures (X1–X14)</span>
          </label>
          <label className="flex items-center gap-2 py-1 cursor-pointer">
            <input type="checkbox" checked={showBuffers} onChange={(e) => setShowBuffers(e.target.checked)} />
            <span className="text-sm">Buffer zones</span>
          </label>
          <div className="flex gap-2 mt-1 ml-6">
            <button
              type="button"
              onClick={() => setBufferMode('cluster')}
              className={`text-xs px-2 py-1 rounded ${bufferMode === 'cluster' ? 'bg-yellow-500 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
            >Per cluster (5)</button>
            <button
              type="button"
              onClick={() => setBufferMode('structure')}
              className={`text-xs px-2 py-1 rounded ${bufferMode === 'structure' ? 'bg-orange-500 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
            >Per structure (14)</button>
          </div>
        </div>

        {/* Reference + basemap */}
        <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
          <label className="flex items-center gap-2 py-1 cursor-pointer">
            <input type="checkbox" checked={showLiveFences} onChange={(e) => setShowLiveFences(e.target.checked)} />
            <span className="text-sm">Show live geofences (reference)</span>
          </label>
          <div className="flex gap-2 mt-2">
            <button type="button" onClick={() => setTile('satellite')} className={`text-xs px-2 py-1 rounded ${tile === 'satellite' ? 'bg-brand-700 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}>Satellite</button>
            <button type="button" onClick={() => setTile('street')} className={`text-xs px-2 py-1 rounded ${tile === 'street' ? 'bg-brand-700 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}>Street</button>
          </div>
        </div>
      </div>

      {/* Selected option detail */}
      {selected && (
        <div className="absolute bottom-4 left-4 z-10 w-80 bg-white/95 dark:bg-gray-800/95 backdrop-blur rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-bold text-sm" style={{ color: selected.color }}>{selected.name}</h3>
            <button onClick={() => setSelectedOption(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none">×</button>
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-300">{selected.summary}</p>
          {selected.draft && (
            <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2">⚠ Draft proposal — not surveyed. Review before adopting.</p>
          )}
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100/60 dark:bg-gray-900/60 z-20">
          <span className="text-sm text-gray-600 dark:text-gray-300">Loading planner…</span>
        </div>
      )}
    </div>
  );
}
