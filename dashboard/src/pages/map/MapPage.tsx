import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useAuthStore } from '@/stores/authStore';
import { useThemeStore } from '@/stores/themeStore';
import { apiClient } from '@/api/client';
import { useToastStore } from '@/stores/toastStore';
import type { Farm } from '@/types';

// Fallback centre (South Africa overview) — used only if no farm is selected
const DEFAULT_CENTER: [number, number] = [27.5, -28.0];
const DEFAULT_ZOOM = 7;

// Calculate appropriate zoom based on farm area
function farmZoom(farm?: { area_hectares?: number }): number {
  if (!farm?.area_hectares) return 15;
  const ha = farm.area_hectares;
  if (ha > 200) return 14;    // Large farms (Boschhoek 450ha)
  if (ha > 50) return 15;     // Medium farms
  return 16;                   // Small plots (Loch Vaal 25ha)
}

// Map tile sources
const TILE_SOURCES = {
  osm: {
    label: 'Street',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '&copy; OpenStreetMap contributors',
  },
  satellite: {
    label: 'Satellite',
    tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'],
    attribution: '&copy; Google',
  },
  terrain: {
    label: 'Terrain',
    tiles: ['https://tile.opentopomap.org/{z}/{x}/{y}.png'],
    attribution: '&copy; OpenTopoMap',
  },
  dark: {
    label: 'Dark',
    tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'],
    attribution: '&copy; CartoDB &copy; OpenStreetMap contributors',
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
  const drawingModeRef = useRef(false);
  const [editingFenceId, setEditingFenceId] = useState<string | null>(null);
  const [editingFenceName, setEditingFenceName] = useState<string>('');

  // Keep ref in sync with state
  useEffect(() => { drawingModeRef.current = drawingMode; }, [drawingMode]);

  // Check URL for ?editFence=id (from Geofences page "Redraw" button)
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const editId = searchParams.get('editFence');
    if (editId) {
      setEditingFenceId(editId);
      setDrawingMode(true);
      setDrawingPoints([]);
      // Clean the URL param
      searchParams.delete('editFence');
      setSearchParams(searchParams, { replace: true });
    }
  }, []);

  const positions = useRealtimeStore((state) => state.positions);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const resolved = useThemeStore((state) => state.resolved);
  const addToast = useToastStore((state) => state.addToast);

  // Multi-farm support
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<string>(currentFarm || '');
  const [geofenceIds, setGeofenceIds] = useState<string[]>([]);

  // Fetch available farms on mount
  useEffect(() => {
    async function loadFarms() {
      try {
        const resp = await apiClient.get('/api/farms');
        setFarms(resp.data);
        // Auto-select first farm if none selected
        if (!selectedFarmId && resp.data.length > 0) {
          setSelectedFarmId(resp.data[0].id);
        }
      } catch {
        // Fallback: use known demo farms
        setFarms([
          { id: '22222222-2222-2222-2222-222222222222', name: 'Boschhoek Farm', organisation_id: '', latitude: -29.12, longitude: 26.21, timezone: 'Africa/Johannesburg', province: 'Free State' },
          { id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', name: 'Loch Vaal Plot 30', organisation_id: '', latitude: -26.719088, longitude: 27.709759, timezone: 'Africa/Johannesburg', province: 'Gauteng' },
        ]);
        if (!selectedFarmId) setSelectedFarmId('22222222-2222-2222-2222-222222222222');
      }
    }
    loadFarms();
  }, []);

  // Fly to selected farm when it changes, or when map finishes loading
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedFarmId || loading) return;
    const farm = farms.find((f) => f.id === selectedFarmId);
    if (farm?.latitude && farm?.longitude) {
      map.flyTo({ center: [farm.longitude, farm.latitude], zoom: farmZoom(farm as any), duration: 1500 });
    }
    // Load geofences & animals for the selected farm
    clearAllGeofences(map);
    clearAllMarkers();
    loadGeofencesForFarm(map, selectedFarmId);
    fetchPositionsForFarm(map, selectedFarmId);
  }, [selectedFarmId, farms, loading]);

  function clearAllGeofences(map: maplibregl.Map) {
    geofenceIds.forEach((id) => {
      ['fill', 'outline'].forEach((t) => {
        const layerId = `fence-${t}-${id}`;
        if (map.getLayer(layerId)) map.removeLayer(layerId);
      });
      if (map.getSource(`fence-${id}`)) map.removeSource(`fence-${id}`);
      // Remove label marker
      const labelMarker = fenceLabelMarkersRef.current.get(id);
      if (labelMarker) { labelMarker.remove(); fenceLabelMarkersRef.current.delete(id); }
    });
    setGeofenceIds([]);
  }

  function clearAllMarkers() {
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current.clear();
    setAnimalCount(0);
  }

  // ─── Initialize Map ─────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Determine initial centre from selected farm
    const farm = farms.find((f) => f.id === selectedFarmId);
    const center: [number, number] = farm?.longitude && farm?.latitude
      ? [farm.longitude, farm.latitude]
      : DEFAULT_CENTER;
    const zoom = farm?.latitude ? farmZoom(farm as any) : DEFAULT_ZOOM;

    const source = TILE_SOURCES[tileSource];
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8, name: 'LivestockGuard',
        sources: { 'base-tiles': { type: 'raster', tiles: source.tiles, tileSize: 256, attribution: source.attribution } },
        layers: [{ id: 'base-layer', type: 'raster', source: 'base-tiles', minzoom: 0, maxzoom: 19 }],
      },
      center,
      zoom,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    map.on('load', () => {
      setLoading(false);
      // Data loading is handled by the selectedFarmId useEffect
      // (waits for farms API response before loading geofences/animals)
    });

    map.on('click', (e) => {
      if (drawingModeRef.current) {
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

  // ─── Auto-switch to dark tiles when theme changes ──
  useEffect(() => {
    if (loading) return;
    // If user hasn't manually picked a tile source, auto-switch based on theme
    if (resolved === 'dark' && tileSource === 'osm') {
      setTileSource('dark');
    } else if (resolved === 'light' && tileSource === 'dark') {
      setTileSource('osm');
    }
  }, [resolved, loading]);

  // ─── Geofence Polygon Overlays ─────────────────────
  const fenceLabelMarkersRef = useRef<Map<string, maplibregl.Marker>>(new Map());

  function addGeofenceToMap(map: maplibregl.Map, id: string, name: string, type: string, geometry: any, areaHectares?: number | null) {
    const color = type === 'exclusion' ? '#ef4444' : '#22c55e';
    map.addSource(`fence-${id}`, {
      type: 'geojson',
      data: { type: 'Feature', properties: { name }, geometry },
    });
    map.addLayer({ id: `fence-fill-${id}`, type: 'fill', source: `fence-${id}`, paint: { 'fill-color': color, 'fill-opacity': 0.12 } });
    map.addLayer({ id: `fence-outline-${id}`, type: 'line', source: `fence-${id}`, paint: { 'line-color': color, 'line-width': 2.5, 'line-dasharray': type === 'exclusion' ? [4, 2] : [1] } });

    // Add name + area as HTML marker at polygon centroid
    const coords = geometry.coordinates?.[0];
    if (coords && coords.length > 0) {
      let cx = 0, cy = 0;
      coords.forEach((c: number[]) => { cx += c[0]; cy += c[1]; });
      cx /= coords.length; cy /= coords.length;

      let areaText = '';
      if (areaHectares != null && areaHectares > 0) {
        if (areaHectares >= 100) areaText = ` · ${(areaHectares / 100).toFixed(0)} km²`;
        else if (areaHectares >= 1) areaText = ` · ${areaHectares.toFixed(1)} ha`;
        else areaText = ` · ${Math.round(areaHectares * 10000)} m²`;
      }

      const el = document.createElement('div');
      el.style.cssText = `font-size:11px;font-weight:bold;color:#fff;background:${color};padding:2px 6px;border-radius:4px;white-space:nowrap;pointer-events:none;opacity:0.9;`;
      el.textContent = `${name}${areaText}`;
      const marker = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([cx, cy]).addTo(map);
      fenceLabelMarkersRef.current.set(id, marker);
    }
  }

  async function loadGeofencesForFarm(map: maplibregl.Map, farmId: string) {
    try {
      const fid = farmId || currentFarm || '22222222-2222-2222-2222-222222222222';
      const resp = await apiClient.get('/api/geofences', { params: { farm_id: fid } });
      const fences = resp.data;
      const ids: string[] = [];
      if (fences.length > 0) {
        fences.forEach((fence: any) => {
          if (fence.geometry) {
            addGeofenceToMap(map, fence.id, fence.name, fence.fence_type, fence.geometry, fence.area_hectares);
            ids.push(fence.id);
          }
        });
        setGeofenceIds(ids);
        return;
      }
    } catch {
      // Fall through to demo geofences only for Boschhoek
    }
    // Fallback: demo geofences (only if Boschhoek farm)
    if (!farmId || farmId === '22222222-2222-2222-2222-222222222222') {
      addDemoGeofences(map);
      setGeofenceIds(DEMO_GEOFENCES.map((f) => f.id));
    }
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
    const allFenceIds = geofenceIds.length > 0 ? geofenceIds : DEMO_GEOFENCES.map((f) => f.id);
    allFenceIds.forEach((id) => {
      const vis = layers.geofences ? 'visible' : 'none';
      ['fill', 'outline'].forEach((t) => {
        const layerId = `fence-${t}-${id}`;
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', vis);
      });
      // Toggle label marker visibility
      const labelMarker = fenceLabelMarkersRef.current.get(id);
      if (labelMarker) {
        labelMarker.getElement().style.display = layers.geofences ? 'block' : 'none';
      }
    });
  }, [layers.geofences, loading, geofenceIds]);

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
      const positions = resp.data.positions;
      const points: [number, number][] = positions.map((p: any) => [p.lon, p.lat]);
      setTrailData(points);
      renderTrail(map, points);

      // Add time markers at start and end of trail
      if (positions.length > 0) {
        const first = positions[positions.length - 1]; // oldest
        const last = positions[0]; // newest
        const startTime = new Date(first.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const endTime = new Date(last.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Remove old time markers
        document.querySelectorAll('.trail-time-marker').forEach(el => el.remove());

        // Start marker
        const startEl = document.createElement('div');
        startEl.className = 'trail-time-marker';
        startEl.style.cssText = 'font-size:10px;background:#7c3aed;color:#fff;padding:1px 4px;border-radius:3px;white-space:nowrap;';
        startEl.textContent = `Start ${startTime}`;
        new maplibregl.Marker({ element: startEl, anchor: 'bottom' }).setLngLat([first.lon, first.lat]).addTo(map);

        // End marker
        const endEl = document.createElement('div');
        endEl.className = 'trail-time-marker';
        endEl.style.cssText = 'font-size:10px;background:#7c3aed;color:#fff;padding:1px 4px;border-radius:3px;white-space:nowrap;';
        endEl.textContent = `Now ${endTime}`;
        new maplibregl.Marker({ element: endEl, anchor: 'bottom' }).setLngLat([last.lon, last.lat]).addTo(map);
      }
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
    document.querySelectorAll('.trail-time-marker').forEach(el => el.remove());
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
      const closed = [...drawingPoints, drawingPoints[0]];
      const geometry = { type: 'Polygon' as const, coordinates: [closed] };

      try {
        if (editingFenceId) {
          // REDRAW existing geofence — update geometry via PUT
          const newName = prompt('Rename geofence (or leave as-is):', editingFenceName) || editingFenceName;
          await apiClient.put(`/api/geofences/${editingFenceId}`, { geometry, name: newName });
          addToast({ title: 'Geofence Updated', message: `"${newName}" redrawn with new boundary`, severity: 'success', duration: 5000 });
          setEditingFenceId(null);
          setEditingFenceName('');
          // Reload all geofences to reflect change
          const map = mapRef.current;
          if (map) {
            clearAllGeofences(map);
            loadGeofencesForFarm(map, selectedFarmId);
          }
        } else {
          // CREATE new geofence
          const name = prompt('Geofence name:');
          if (name) {
            const fenceType = confirm('Is this an inclusion zone? (Cancel = exclusion zone)') ? 'inclusion' : 'exclusion';
            const farmId = selectedFarmId || currentFarm || '22222222-2222-2222-2222-222222222222';
            await apiClient.post('/api/geofences', {
              name,
              farm_id: farmId,
              geometry,
              fence_type: fenceType,
              active: true,
              alert_on_breach: true,
            });
            addToast({ title: 'Geofence Saved', message: `"${name}" (${fenceType}) saved`, severity: 'success', duration: 5000 });
            // Reload geofences
            const map = mapRef.current;
            if (map) {
              clearAllGeofences(map);
              loadGeofencesForFarm(map, selectedFarmId);
            }
          }
        }
      } catch (err) {
        console.error('Failed to save geofence:', err);
        addToast({ title: 'Save Failed', message: 'Could not save geofence', severity: 'high', duration: 5000 });
      }
    }
    setDrawingMode(false);
    setDrawingPoints([]);
    setEditingFenceId(null);
    const map = mapRef.current;
    if (map) {
      if (map.getLayer('drawing-fill')) map.removeLayer('drawing-fill');
      if (map.getLayer('drawing-line')) map.removeLayer('drawing-line');
      if (map.getSource('drawing-source')) map.removeSource('drawing-source');
    }
  }

  // ─── Fetch & Render Positions ──────────────────────
  async function fetchPositions(map: maplibregl.Map) {
    await fetchPositionsForFarm(map, selectedFarmId);
  }

  async function fetchPositionsForFarm(map: maplibregl.Map, farmId: string) {
    try {
      const fid = farmId || currentFarm || '22222222-2222-2222-2222-222222222222';
      const resp = await apiClient.get('/api/animals', { params: { farm_id: fid } });
      setAnimalCount(resp.data.length);

      // Spread animals that share the same coordinates (BLE animals at gateway position)
      const positionMap = new Map<string, number>(); // "lat,lng" -> count
      const animals = resp.data.filter((a: any) => a.last_latitude && a.last_longitude);

      animals.forEach((a: any) => {
        const key = `${a.last_latitude.toFixed(5)},${a.last_longitude.toFixed(5)}`;
        positionMap.set(key, (positionMap.get(key) || 0) + 1);
      });

      // For each animal, if it shares a position with others, spread in a circle
      const placed = new Map<string, number>(); // tracks how many placed at each key
      animals.forEach((a: any) => {
        const key = `${a.last_latitude.toFixed(5)},${a.last_longitude.toFixed(5)}`;
        const total = positionMap.get(key) || 1;
        const idx = placed.get(key) || 0;
        placed.set(key, idx + 1);

        let lng = a.last_longitude;
        let lat = a.last_latitude;

        // Spread markers in a circle if multiple at same point
        if (total > 1) {
          const angle = (idx / total) * 2 * Math.PI;
          const radius = 0.0003 + (total > 5 ? 0.0002 : 0); // ~30-50m spread
          lng += Math.cos(angle) * radius;
          lat += Math.sin(angle) * radius;
        }

        addOrUpdateMarker(map, a.id, a.name, lng, lat, a.battery_level);
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
          <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Live Map</h2>
          {/* Farm Selector */}
          {farms.length > 0 && (
            <select
              value={selectedFarmId}
              onChange={(e) => setSelectedFarmId(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-brand-500"
              aria-label="Select farm"
            >
              {farms.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.name}{farm.province ? ` (${farm.province})` : ''}
                </option>
              ))}
            </select>
          )}
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
              <span className="text-xs text-amber-600">
                {editingFenceId ? '✏️ Redraw: ' : ''}Click map ({drawingPoints.length} pts)
              </span>
              <button onClick={finishDrawing} disabled={drawingPoints.length < 3} className="px-2 py-1 text-xs bg-green-600 text-white rounded disabled:opacity-50">✓ Finish</button>
              <button onClick={() => { setDrawingMode(false); setDrawingPoints([]); setEditingFenceId(null); }} className="px-2 py-1 text-xs bg-red-600 text-white rounded">✕</button>
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
          <span className="text-blue-600">{geofenceIds.length || DEMO_GEOFENCES.length} geofences</span>
          {selectedAnimal && <span className="text-purple-600">Trail: {trailData.length} pts</span>}
          {drawingMode && <span className="text-amber-600 font-medium">Drawing active</span>}
        </div>
        <span className="text-gray-400">Tiles: {TILE_SOURCES[tileSource].label} | Live via WebSocket</span>
      </div>
    </div>
  );
}
