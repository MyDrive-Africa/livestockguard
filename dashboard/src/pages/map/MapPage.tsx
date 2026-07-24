import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useAuthStore } from '@/stores/authStore';
import { useThemeStore } from '@/stores/themeStore';
import { apiClient } from '@/api/client';

// South Africa centre (Free State - Boschhoek Farm)
const DEFAULT_CENTER: [number, number] = [26.21, -29.12];
const DEFAULT_ZOOM = 14;

// Map tile sources
const TILE_SOURCES = {
  osm: {
    label: 'Street',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '&copy; OpenStreetMap contributors',
  },
  satellite: {
    label: 'Satellite',
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution: '&copy; Esri',
  },
  terrain: {
    label: 'Terrain',
    tiles: ['https://tile.opentopomap.org/{z}/{x}/{y}.png'],
    attribution: '&copy; OpenTopoMap',
  },
};

// Demo geofences (matching seed_data.sql)
const DEMO_GEOFENCES = [
  {
    id: 'paddock-north', name: 'Paddock North', type: 'inclusion', color: '#22c55e',
    coords: [[26.200,-29.110],[26.220,-29.110],[26.220,-29.125],[26.200,-29.125],[26.200,-29.110]],
  },
  {
    id: 'paddock-south', name: 'Paddock South', type: 'inclusion', color: '#3b82f6',
    coords: [[26.200,-29.125],[26.220,-29.125],[26.220,-29.140],[26.200,-29.140],[26.200,-29.125]],
  },
  {
    id: 'exclusion-dam', name: 'Exclusion Zone (Dam)', type: 'exclusion', color: '#ef4444',
    coords: [[26.208,-29.118],[26.212,-29.118],[26.212,-29.122],[26.208,-29.122],[26.208,-29.118]],
  },
];

const DEMO_ANIMALS = [
  { id: '1', name: 'Bella', lng: 26.208, lat: -29.117, battery: 85 },
  { id: '2', name: 'Storm', lng: 26.212, lat: -29.119, battery: 92 },
  { id: '3', name: 'Thunder', lng: 26.215, lat: -29.121, battery: 78 },
  { id: '4', name: 'Daisy', lng: 26.205, lat: -29.123, battery: 65 },
  { id: '5', name: 'Rosie', lng: 26.210, lat: -29.130, battery: 15 },
];

type TileSource = keyof typeof TILE_SOURCES;
type LayerToggle = 'animals' | 'geofences' | 'trails';

export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const [animalCount, setAnimalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tileSource, setTileSource] = useState<TileSource>('osm');
  const [layers, setLayers] = useState<Record<LayerToggle, boolean>>({
    animals: true, geofences: true, trails: false,
  });
  const [selectedAnimal, setSelectedAnimal] = useState<string | null>(null);
  const [trailData, setTrailData] = useState<[number, number][]>([]);
  const [drawingMode, setDrawingMode] = useState(false);
  const [drawingPoints, setDrawingPoints] = useState<[number, number][]>([]);

  const positions = useRealtimeStore((state) => state.positions);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const resolved = useThemeStore((state) => state.resolved);

  // ─── Initialize Map ─────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const source = TILE_SOURCES[tileSource];
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8, name: 'LivestockGuard',
        sources: { 'base-tiles': { type: 'raster', tiles: source.tiles, tileSize: 256, attribution: source.attribution } },
        layers: [{ id: 'base-layer', type: 'raster', source: 'base-tiles', minzoom: 0, maxzoom: 19 }],
      },
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    map.on('load', () => {
      setLoading(false);
      loadGeofences(map);
      fetchPositions(map);
    });

    map.on('click', (e) => {
      if (drawingMode) {
        setDrawingPoints((prev) => [...prev, [e.lngLat.lng, e.lngLat.lat]]);
      }
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // ─── Tile Source Switching ──────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    const source = TILE_SOURCES[tileSource];
    const s = map.getSource('base-tiles') as maplibregl.RasterTileSource;
    if (s) {
      map.removeLayer('base-layer');
      map.removeSource('base-tiles');
      map.addSource('base-tiles', { type: 'raster', tiles: source.tiles, tileSize: 256, attribution: source.attribution });
      map.addLayer({ id: 'base-layer', type: 'raster', source: 'base-tiles' }, map.getStyle().layers[1]?.id);
    }
  }, [tileSource, loading]);

  // ─── Geofence Polygon Overlays ─────────────────────
  function addGeofenceToMap(map: maplibregl.Map, id: string, name: string, type: string, geometry: any) {
    const color = type === 'exclusion' ? '#ef4444' : '#22c55e';
    map.addSource(`fence-${id}`, {
      type: 'geojson',
      data: { type: 'Feature', properties: { name }, geometry },
    });
    map.addLayer({ id: `fence-fill-${id}`, type: 'fill', source: `fence-${id}`, paint: { 'fill-color': color, 'fill-opacity': 0.1 } });
    map.addLayer({ id: `fence-outline-${id}`, type: 'line', source: `fence-${id}`, paint: { 'line-color': color, 'line-width': 2, 'line-dasharray': type === 'exclusion' ? [4, 2] : [1] } });
    map.addLayer({ id: `fence-label-${id}`, type: 'symbol', source: `fence-${id}`, layout: { 'text-field': name, 'text-size': 11 }, paint: { 'text-color': color, 'text-halo-color': '#fff', 'text-halo-width': 1.5 } });
  }

  async function loadGeofences(map: maplibregl.Map) {
    try {
      const farmId = currentFarm || '22222222-2222-2222-2222-222222222222';
      const resp = await apiClient.get('/api/geofences', { params: { farm_id: farmId } });
      const fences = resp.data;
      if (fences.length > 0) {
        fences.forEach((fence: any) => {
          if (fence.geometry) {
            addGeofenceToMap(map, fence.id, fence.name, fence.fence_type, fence.geometry);
          }
        });
        return;
      }
    } catch {
      // Fall through to demo geofences
    }
    // Fallback: demo geofences
    addDemoGeofences(map);
  }

  function addDemoGeofences(map: maplibregl.Map) {
    DEMO_GEOFENCES.forEach((fence) => {
      addGeofenceToMap(map, fence.id, fence.name, fence.type, { type: 'Polygon', coordinates: [fence.coords] });
    });
  }

  // ─── Geofence Visibility Toggle ────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    DEMO_GEOFENCES.forEach((fence) => {
      const vis = layers.geofences ? 'visible' : 'none';
      ['fill', 'outline', 'label'].forEach((t) => {
        const id = `fence-${t}-${fence.id}`;
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
      });
    });
  }, [layers.geofences, loading]);

  // ─── Animal Marker Visibility ──────────────────────
  useEffect(() => {
    markersRef.current.forEach((marker) => {
      marker.getElement().style.display = layers.animals ? 'flex' : 'none';
    });
  }, [layers.animals]);

  // ─── Movement Trail (Click → 24h path) ────────────
  async function showTrail(animalId: string) {
    const map = mapRef.current;
    if (!map) return;
    setSelectedAnimal(animalId);

    try {
      const resp = await apiClient.get(`/api/animals/${animalId}/history`, { params: { hours: 24, limit: 200 } });
      const points: [number, number][] = resp.data.positions.map((p: any) => [p.lon, p.lat]);
      setTrailData(points);
      renderTrail(map, points);
    } catch {
      // Demo trail
      const demo: [number, number][] = [];
      for (let i = 0; i < 50; i++) {
        const t = i / 50;
        demo.push([26.210 + Math.sin(t * 6) * 0.003, -29.120 + Math.cos(t * 4) * 0.002 - t * 0.005]);
      }
      setTrailData(demo);
      renderTrail(map, demo);
    }
  }

  function renderTrail(map: maplibregl.Map, points: [number, number][]) {
    if (map.getLayer('trail-line')) map.removeLayer('trail-line');
    if (map.getLayer('trail-dots')) map.removeLayer('trail-dots');
    if (map.getSource('trail-source')) map.removeSource('trail-source');
    if (points.length < 2) return;

    map.addSource('trail-source', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: points } } });
    map.addLayer({ id: 'trail-line', type: 'line', source: 'trail-source', paint: { 'line-color': '#8b5cf6', 'line-width': 3, 'line-opacity': 0.7 } });
    map.addLayer({ id: 'trail-dots', type: 'circle', source: 'trail-source', paint: { 'circle-radius': 3, 'circle-color': '#8b5cf6', 'circle-opacity': 0.5 } });
  }

  function clearTrail() {
    const map = mapRef.current;
    if (!map) return;
    if (map.getLayer('trail-line')) map.removeLayer('trail-line');
    if (map.getLayer('trail-dots')) map.removeLayer('trail-dots');
    if (map.getSource('trail-source')) map.removeSource('trail-source');
    setSelectedAnimal(null);
    setTrailData([]);
  }

  // ─── Geofence Drawing Tool ─────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    if (map.getLayer('drawing-fill')) map.removeLayer('drawing-fill');
    if (map.getLayer('drawing-line')) map.removeLayer('drawing-line');
    if (map.getSource('drawing-source')) map.removeSource('drawing-source');

    if (drawingMode && drawingPoints.length >= 2) {
      const closed = [...drawingPoints, drawingPoints[0]];
      map.addSource('drawing-source', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [closed] } } });
      map.addLayer({ id: 'drawing-fill', type: 'fill', source: 'drawing-source', paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.2 } });
      map.addLayer({ id: 'drawing-line', type: 'line', source: 'drawing-source', paint: { 'line-color': '#f59e0b', 'line-width': 2 } });
    }
  }, [drawingPoints, drawingMode, loading]);

  async function finishDrawing() {
    if (drawingPoints.length >= 3) {
      const name = prompt('Geofence name:');
      if (name) {
        const fenceType = confirm('Is this an inclusion zone? (Cancel = exclusion zone)') ? 'inclusion' : 'exclusion';
        const closed = [...drawingPoints, drawingPoints[0]];
        const geometry = { type: 'Polygon' as const, coordinates: [closed] };

        try {
          const farmId = currentFarm || '22222222-2222-2222-2222-222222222222';
          await apiClient.post('/api/geofences', {
            name,
            farm_id: farmId,
            geometry,
            fence_type: fenceType,
            active: true,
            alert_on_breach: true,
          });

          // Add the new geofence to the map
          const map = mapRef.current;
          if (map) {
            const color = fenceType === 'exclusion' ? '#ef4444' : '#22c55e';
            const fenceId = `user-fence-${Date.now()}`;
            map.addSource(`fence-${fenceId}`, {
              type: 'geojson',
              data: { type: 'Feature', properties: { name }, geometry },
            });
            map.addLayer({ id: `fence-fill-${fenceId}`, type: 'fill', source: `fence-${fenceId}`, paint: { 'fill-color': color, 'fill-opacity': 0.1 } });
            map.addLayer({ id: `fence-outline-${fenceId}`, type: 'line', source: `fence-${fenceId}`, paint: { 'line-color': color, 'line-width': 2, 'line-dasharray': fenceType === 'exclusion' ? [4, 2] : [1] } });
            map.addLayer({ id: `fence-label-${fenceId}`, type: 'symbol', source: `fence-${fenceId}`, layout: { 'text-field': name, 'text-size': 11 }, paint: { 'text-color': color, 'text-halo-color': '#fff', 'text-halo-width': 1.5 } });
          }
        } catch (err) {
          console.error('Failed to save geofence:', err);
          alert('Failed to save geofence. Check console for details.');
        }
      }
    }
    setDrawingMode(false);
    setDrawingPoints([]);
    const map = mapRef.current;
    if (map) {
      if (map.getLayer('drawing-fill')) map.removeLayer('drawing-fill');
      if (map.getLayer('drawing-line')) map.removeLayer('drawing-line');
      if (map.getSource('drawing-source')) map.removeSource('drawing-source');
    }
  }

  // ─── Fetch & Render Positions ──────────────────────
  async function fetchPositions(map: maplibregl.Map) {
    try {
      const resp = await apiClient.get('/api/animals', { params: { farm_id: '22222222-2222-2222-2222-222222222222' } });
      setAnimalCount(resp.data.length);
      resp.data.forEach((a: any) => {
        if (a.last_latitude && a.last_longitude) addOrUpdateMarker(map, a.id, a.name, a.last_longitude, a.last_latitude, a.battery_level);
      });
    } catch { addDemoMarkers(map); }
  }

  function addDemoMarkers(map: maplibregl.Map) {
    DEMO_ANIMALS.forEach((a) => addOrUpdateMarker(map, a.id, a.name, a.lng, a.lat, a.battery));
    setAnimalCount(DEMO_ANIMALS.length);
  }

  function addOrUpdateMarker(map: maplibregl.Map, id: string, name: string, lng: number, lat: number, battery?: number | null) {
    const existing = markersRef.current.get(id);
    if (existing) { existing.setLngLat([lng, lat]); return; }

    const isLow = battery != null && battery < 20;
    const el = document.createElement('div');
    el.style.cssText = `width:32px;height:32px;background:${isLow ? '#ea580c' : '#16a34a'};border:2px solid ${resolved === 'dark' ? '#374151' : 'white'};border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 6px rgba(0,0,0,0.3);transition:transform 0.3s;`;
    el.innerHTML = '🐄';
    el.title = name;
    el.addEventListener('click', (e) => { e.stopPropagation(); showTrail(id); });

    const popup = new maplibregl.Popup({ offset: 20 }).setHTML(`
      <div style="padding:8px;min-width:140px;">
        <strong>${name}</strong><br/>
        <span style="color:#666;font-size:12px;">
          📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}<br/>
          🔋 ${battery ?? '?'}% ${isLow ? '⚠️' : ''}<br/>
          <em>Click marker for 24h trail</em>
        </span>
      </div>
    `);

    const marker = new maplibregl.Marker({ element: el }).setLngLat([lng, lat]).setPopup(popup).addTo(map);
    markersRef.current.set(id, marker);
  }

  // Realtime updates
  useEffect(() => {
    if (!mapRef.current) return;
    positions.forEach((pos, id) => addOrUpdateMarker(mapRef.current!, id, pos.animalName, pos.position.longitude, pos.position.latitude, pos.batteryLevel));
  }, [positions]);

  // Auto-refresh (fallback — primary updates come via WebSocket)
  useEffect(() => {
    const i = setInterval(() => { if (mapRef.current) fetchPositions(mapRef.current); }, 120000);
    return () => clearInterval(i);
  }, []);

  function toggleLayer(l: LayerToggle) {
    setLayers((p) => ({ ...p, [l]: !p[l] }));
    if (l === 'trails' && layers.trails) clearTrail();
  }

  // ─── Render ────────────────────────────────────────
  return (
    <div className="h-full w-full flex flex-col" style={{ height: '100%' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-10 shrink-0 theme-transition">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-800">Live Map</h2>
          <div className="flex items-center gap-1.5 text-xs">
            {(['animals', 'geofences', 'trails'] as LayerToggle[]).map((l) => (
              <button key={l} onClick={() => toggleLayer(l)}
                className={`px-2.5 py-1 rounded-full border capitalize ${layers[l] ? 'bg-green-100 border-green-400 text-green-700' : 'bg-gray-50 border-gray-300 text-gray-500'}`}>
                {l === 'animals' ? '🐄 ' : l === 'geofences' ? '🏗️ ' : '📍 '}{l}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 text-xs ml-2 border-l pl-3">
            {(Object.keys(TILE_SOURCES) as TileSource[]).map((s) => (
              <button key={s} onClick={() => setTileSource(s)}
                className={`px-2 py-1 rounded ${tileSource === s ? 'bg-blue-100 text-blue-700 border border-blue-300' : 'text-gray-500 hover:text-gray-700'}`}>
                {TILE_SOURCES[s].label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedAnimal && <button onClick={clearTrail} className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded border border-purple-300">✕ Clear Trail</button>}
          {!drawingMode ? (
            <button onClick={() => { setDrawingMode(true); setDrawingPoints([]); }} className="px-3 py-1.5 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700">+ Draw Fence</button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600">Click map ({drawingPoints.length} pts)</span>
              <button onClick={finishDrawing} disabled={drawingPoints.length < 3} className="px-2 py-1 text-xs bg-green-600 text-white rounded disabled:opacity-50">✓ Finish</button>
              <button onClick={() => { setDrawingMode(false); setDrawingPoints([]); }} className="px-2 py-1 text-xs bg-red-600 text-white rounded">✕</button>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 min-h-0 relative" style={{ minHeight: 0 }}>
        <div ref={mapContainerRef} className="absolute inset-0" style={{ cursor: drawingMode ? 'crosshair' : 'grab', width: '100%', height: '100%' }} />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100/80 dark:bg-gray-900/80 z-10">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full mx-auto mb-2"></div>
              <p className="text-gray-500">Loading map...</p>
            </div>
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-400 z-10 shrink-0 theme-transition">
        <div className="flex items-center gap-4">
          <span className="text-green-600 font-medium">🟢 {animalCount} animals</span>
          <span className="text-blue-600">{DEMO_GEOFENCES.length} geofences</span>
          {selectedAnimal && <span className="text-purple-600">Trail: {trailData.length} pts</span>}
          {drawingMode && <span className="text-amber-600 font-medium">Drawing active</span>}
        </div>
        <span className="text-gray-400">Tiles: {TILE_SOURCES[tileSource].label} | Live via WebSocket</span>
      </div>
    </div>
  );
}
