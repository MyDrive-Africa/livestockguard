/**
 * @file MapPage.tsx
 * @description Real-time GPS tracking map showing animal positions, movement trails,
 * and geofence polygons. The primary operational view for farmers to monitor
 * their livestock across multiple farms.
 *
 * Features:
 * - Live animal position markers with battery/signal indicators
 * - Geofence polygons rendered as map layers (fill + outline)
 * - Movement trail history with time-based filtering
 * - Multiple tile sources (street, satellite, terrain)
 * - Auto-centres on the selected farm with adaptive zoom
 * - Real-time updates via WebSocket (markers update without page refresh)
 *
 * @see useRealtimeStore — Provides live position updates via WebSocket
 * @see useAuthStore — Determines which farm to display
 */
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
type LayerToggle = 'animals' | 'geofences' | 'trails' | 'markers';

export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const herdsmanMarkersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const mapReadyRef = useRef(false);
  const [animalCount, setAnimalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tileSource, setTileSource] = useState<TileSource>('satellite');
  const [layers, setLayers] = useState<Record<LayerToggle, boolean>>({
    animals: true, geofences: true, trails: false, markers: true,
  });
  const [selectedAnimal, setSelectedAnimal] = useState<string | null>(null);
  const [trailData, setTrailData] = useState<[number, number][]>([]);
  const [trailDate, setTrailDate] = useState<string>(''); // YYYY-MM-DD or '' for today
  const [drawingMode, setDrawingMode] = useState(false);
  const [drawingPoints, setDrawingPoints] = useState<[number, number][]>([]);
  const drawingModeRef = useRef(false);
  const [editingFenceId, setEditingFenceId] = useState<string | null>(null);
  const [editingFenceName, setEditingFenceName] = useState<string>('');

  // Mark Structure mode
  const [markingMode, setMarkingMode] = useState(false);
  const markingModeRef = useRef(false);
  const [markedStructures, setMarkedStructures] = useState<Array<{ id: number; lat: number; lon: number; label: string; type: string }>>([]);
  const markedMarkersRef = useRef<maplibregl.Marker[]>([]);
  const [showMarkedPanel, setShowMarkedPanel] = useState(false);
  const markIdCounter = useRef(1);

  // Geofence filter: show only active fences by default
  const [showActiveOnly, setShowActiveOnly] = useState(true);

  // Keep refs in sync
  useEffect(() => { drawingModeRef.current = drawingMode; }, [drawingMode]);
  useEffect(() => { markingModeRef.current = markingMode; }, [markingMode]);

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

  const connectionStatus = useRealtimeStore((state) => state.connectionStatus);
  const positions = useRealtimeStore((state) => state.positions);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const resolved = useThemeStore((state) => state.resolved);
  const addToast = useToastStore((state) => state.addToast);

  // Multi-farm support
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<string>(currentFarm || '');
  const [geofenceIds, setGeofenceIds] = useState<string[]>([]);
  const geofenceIdsRef = useRef<string[]>([]);

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
  const prevFarmIdRef = useRef<string>('');
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedFarmId || loading) return;
    const farm = farms.find((f) => f.id === selectedFarmId);
    if (farm?.latitude && farm?.longitude) {
      map.flyTo({ center: [farm.longitude, farm.latitude], zoom: farmZoom(farm as any), duration: 1500 });

      // Place farm centre marker (📍 pin with farm name)
      if (farmCentreMarkerRef.current) {
        farmCentreMarkerRef.current.remove();
        farmCentreMarkerRef.current = null;
      }
      const el = document.createElement('div');
      el.style.cssText = 'display:flex;flex-direction:column;align-items:center;pointer-events:auto;cursor:default;';
      el.innerHTML = `
        <div style="font-size:24px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.4));">📍</div>
        <div style="font-size:10px;font-weight:bold;color:#fff;background:#1d4ed8;padding:1px 5px;border-radius:3px;margin-top:-4px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,0.3);">${farm.name}</div>
        <div style="font-size:9px;color:#93c5fd;background:#1e3a5f;padding:0 4px;border-radius:2px;margin-top:1px;">${farm.latitude.toFixed(5)}, ${farm.longitude.toFixed(5)}</div>
      `;
      farmCentreMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([farm.longitude, farm.latitude])
        .addTo(map);
    }
    // Only clear and reload markers when farm actually changes (not on every farms/loading re-render)
    const farmChanged = prevFarmIdRef.current !== selectedFarmId;
    const firstLoad = prevFarmIdRef.current === '';
    if (farmChanged || firstLoad) {
      prevFarmIdRef.current = selectedFarmId;
      clearAllGeofences(map);
      clearAllMarkers();
      loadGeofencesForFarm(map, selectedFarmId);
      fetchPositionsForFarm(map, selectedFarmId);
    }
  }, [selectedFarmId, farms, loading]);

  function clearAllGeofences(map: maplibregl.Map) {
    geofenceIdsRef.current.forEach((id) => {
      ['fill', 'outline'].forEach((t) => {
        const layerId = `fence-${t}-${id}`;
        if (map.getLayer(layerId)) map.removeLayer(layerId);
      });
      if (map.getSource(`fence-${id}`)) map.removeSource(`fence-${id}`);
      // Remove label marker
      const labelMarker = fenceLabelMarkersRef.current.get(id);
      if (labelMarker) { labelMarker.remove(); fenceLabelMarkersRef.current.delete(id); }
    });
    geofenceIdsRef.current = [];
    setGeofenceIds([]);
  }

  function clearAllMarkers() {
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current.clear();
    herdsmanMarkersRef.current.forEach((marker) => marker.remove());
    herdsmanMarkersRef.current.clear();
    setAnimalCount(0);
  }

  // Refresh data for the currently selected farm without changing location
  async function refreshDashboard() {
    const map = mapRef.current;
    if (!map || !selectedFarmId || refreshing) return;
    setRefreshing(true);
    try {
      clearAllGeofences(map);
      clearAllMarkers();
      await loadGeofencesForFarm(map, selectedFarmId);
      await fetchPositionsForFarm(map, selectedFarmId);
      await fetchHerdsmanPositions(map, selectedFarmId);
      addToast({ title: 'Refreshed', message: 'Dashboard data updated', severity: 'info', duration: 2000 });
    } finally {
      setRefreshing(false);
    }
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
      mapReadyRef.current = true;
      // Data loading is handled by the selectedFarmId useEffect
    });

    map.on('click', (e) => {
      if (drawingModeRef.current) {
        setDrawingPoints((prev) => [...prev, [e.lngLat.lng, e.lngLat.lat]]);
      } else if (markingModeRef.current) {
        const lat = e.lngLat.lat;
        const lon = e.lngLat.lng;
        const label = prompt('Label this structure (e.g. House, Field, Kraal, Road, Compound):') || 'Structure';
        const type = prompt('Type: house / field / road / compound / other', 'house') || 'house';
        if (label) {
          const id = markIdCounter.current++;
          setMarkedStructures((prev) => [...prev, { id, lat, lon, label, type }]);
          // Add visual marker
          const el = document.createElement('div');
          el.style.cssText = 'display:flex;flex-direction:column;align-items:center;';
          const typeEmoji: Record<string, string> = { house: '🏠', field: '🌾', road: '🛤️', compound: '🏘️', other: '📍' };
          el.innerHTML = `<span style="font-size:20px;">${typeEmoji[type] || '📍'}</span><span style="font-size:9px;font-weight:bold;background:#dc2626;color:#fff;padding:1px 4px;border-radius:3px;margin-top:-2px;white-space:nowrap;">X${id}: ${label}</span>`;
          const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([lon, lat]).addTo(map);
          markedMarkersRef.current.push(marker);
        }
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
      // Insert base layer at the very bottom (below geofences)
      const firstLayerId = map.getStyle().layers[0]?.id;
      map.addLayer({ id: 'base-layer', type: 'raster', source: 'base-tiles', minzoom: 0, maxzoom: 19 }, firstLayerId);
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
  const farmCentreMarkerRef = useRef<maplibregl.Marker | null>(null);

  function addGeofenceToMap(map: maplibregl.Map, id: string, name: string, type: string, geometry: any, areaHectares?: number | null) {
    // Distinct colors per zone type (based on emoji/name prefix)
    let color = type === 'exclusion' ? '#ef4444' : '#22c55e';
    let labelBg = color;
    if (name.includes('Option A') || name.includes('Option B') || name.includes('Option C') || name.includes('⬜')) { color = '#3b82f6'; labelBg = '#60a5fa'; }
    else if (name.includes('🔥') || name.includes('Firebreak')) { color = '#f97316'; labelBg = '#fb923c'; }
    else if (name.includes('🐄') || name.includes('Kraal')) { color = '#a855f7'; labelBg = '#c084fc'; }
    else if (name.includes('🏗️') || name.includes('Handling')) { color = '#6366f1'; labelBg = '#a5b4fc'; }
    else if (name.includes('🦶') || name.includes('Foot Bath')) { color = '#14b8a6'; labelBg = '#5eead4'; }
    else if (name.includes('🌱') || name.includes('Lucerne')) { color = '#84cc16'; labelBg = '#bef264'; }
    else if (name.includes('🌿') || name.includes('Grazing')) { color = '#22c55e'; labelBg = '#86efac'; }
    else if (name.includes('🏠') || name.includes('Herdsman')) { color = '#f59e0b'; labelBg = '#fcd34d'; }
    else if (name.includes('🚜') || name.includes('Machinery') || name.includes('Storage')) { color = '#64748b'; labelBg = '#cbd5e1'; }
    else if (name.includes('🏡') || name.includes('Homestead')) { color = '#ec4899'; labelBg = '#f9a8d4'; }
    else if (type === 'exclusion') { color = '#ef4444'; labelBg = '#fca5a5'; }

    map.addSource(`fence-${id}`, {
      type: 'geojson',
      data: { type: 'Feature', properties: { name }, geometry },
    });
    map.addLayer({ id: `fence-fill-${id}`, type: 'fill', source: `fence-${id}`, paint: { 'fill-color': color, 'fill-opacity': 0.15 } });
    map.addLayer({ id: `fence-outline-${id}`, type: 'line', source: `fence-${id}`, paint: { 'line-color': color, 'line-width': 2.5, 'line-dasharray': type === 'exclusion' ? [4, 2] : [1] } });

    // Add name + area as HTML marker at polygon centroid (clickable to show/hide)
    const coords = geometry.coordinates?.[0];
    if (coords && coords.length > 0) {
      let cx = 0, cy = 0;
      let minLat = 90, maxLat = -90;
      coords.forEach((c: number[]) => { cx += c[0]; cy += c[1]; if (c[1] < minLat) minLat = c[1]; if (c[1] > maxLat) maxLat = c[1]; });
      cx /= coords.length; cy /= coords.length;

      // Place label at top-centre of polygon (north edge) to reduce overlap
      const labelLat = maxLat;

      let areaText = '';
      if (areaHectares != null && areaHectares > 0) {
        if (areaHectares >= 100) areaText = ` · ${(areaHectares / 100).toFixed(0)} km²`;
        else if (areaHectares >= 1) areaText = ` · ${areaHectares.toFixed(1)} ha`;
        else areaText = ` · ${Math.round(areaHectares * 10000)} m²`;
      }

      const el = document.createElement('div');
      const fontSize = (areaHectares != null && areaHectares < 1) ? '10px' : '12px';
      el.style.cssText = `font-size:${fontSize};font-weight:bold;background:${labelBg};padding:2px 6px;border-radius:4px;white-space:nowrap;cursor:pointer;opacity:0.95;user-select:none;border:1px solid ${color};box-shadow:0 2px 4px rgba(0,0,0,0.4);`;
      el.style.setProperty('color', '#000', 'important');
      el.textContent = `${name}${areaText}`;
      el.title = 'Click to show/hide boundary';

      // Click to toggle this geofence's fill/outline visibility
      let visible = true;
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        visible = !visible;
        const vis = visible ? 'visible' : 'none';
        if (map.getLayer(`fence-fill-${id}`)) map.setLayoutProperty(`fence-fill-${id}`, 'visibility', vis);
        if (map.getLayer(`fence-outline-${id}`)) map.setLayoutProperty(`fence-outline-${id}`, 'visibility', vis);
        el.style.opacity = visible ? '0.9' : '0.4';
        el.style.textDecoration = visible ? 'none' : 'line-through';
      });

      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([cx, labelLat]).addTo(map);
      fenceLabelMarkersRef.current.set(id, marker);
    }
  }

  async function loadGeofencesForFarm(map: maplibregl.Map, farmId: string) {
    try {
      const fid = farmId || currentFarm || '22222222-2222-2222-2222-222222222222';
      const params: Record<string, string> = { farm_id: fid };
      if (showActiveOnly) params.active = 'true';
      const resp = await apiClient.get('/api/geofences', { params });
      const fences = resp.data;
      const ids: string[] = [];
      if (fences.length > 0) {
        fences.forEach((fence: any) => {
          if (fence.geometry) {
            addGeofenceToMap(map, fence.id, fence.name, fence.fence_type, fence.geometry, fence.area_hectares);
            ids.push(fence.id);
          }
        });
        geofenceIdsRef.current = ids;
        setGeofenceIds(ids);
        return;
      }
    } catch {
      // Fall through to demo geofences only for Boschhoek
    }
    // Fallback: demo geofences (only if Boschhoek farm)
    if (!farmId || farmId === '22222222-2222-2222-2222-222222222222') {
      addDemoGeofences(map);
      const demoIds = DEMO_GEOFENCES.map((f) => f.id);
      geofenceIdsRef.current = demoIds;
      setGeofenceIds(demoIds);
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

  // ─── Reload geofences when filter changes ──────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading || !selectedFarmId) return;
    clearAllGeofences(map);
    loadGeofencesForFarm(map, selectedFarmId);
  }, [showActiveOnly]);

  // ─── Animal Marker Visibility ──────────────────────
  useEffect(() => {
    markersRef.current.forEach((marker) => {
      marker.getElement().style.display = layers.animals ? 'flex' : 'none';
    });
  }, [layers.animals]);

  // ─── Marked Structures Visibility ──────────────────
  useEffect(() => {
    markedMarkersRef.current.forEach((marker) => {
      marker.getElement().style.display = layers.markers ? 'flex' : 'none';
    });
    // Also toggle farm centre pin
    if (farmCentreMarkerRef.current) {
      farmCentreMarkerRef.current.getElement().style.display = layers.markers ? 'flex' : 'none';
    }
  }, [layers.markers]);

  // ─── Movement Trail (Click → daily path) ────────────
  async function showTrail(animalId: string, forDate?: string) {
    const map = mapRef.current;
    if (!map) return;
    setSelectedAnimal(animalId);

    try {
      const params: Record<string, any> = { limit: 500 };
      if (forDate || trailDate) {
        params.date = forDate || trailDate;
      } else {
        params.hours = 24;
      }
      const resp = await apiClient.get(`/api/animals/${animalId}/history`, { params });
      const positions = resp.data.positions;
      const points: [number, number][] = positions.map((p: any) => [p.lon, p.lat]);

      // Ensure trail ends at the cow's current marker position (which may be scattered)
      const animalMarker = markersRef.current.get(animalId);
      if (animalMarker && points.length > 0) {
        const markerPos = animalMarker.getLngLat();
        // Replace the last (newest) point with the marker's actual display position
        points[0] = [markerPos.lng, markerPos.lat];
      }

      setTrailData(points);
      renderTrail(map, points);

      // Add time markers at start and end of trail
      if (positions.length > 0) {
        const first = positions[positions.length - 1]; // oldest
        const last = positions[0]; // newest

        // Use marker position for end point (matches visual)
        const endLng = animalMarker ? animalMarker.getLngLat().lng : last.lon;
        const endLat = animalMarker ? animalMarker.getLngLat().lat : last.lat;

        const startTime = new Date(first.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const endTime = new Date(last.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Remove old time markers
        document.querySelectorAll('.trail-time-marker').forEach(el => el.remove());

        // Start marker (oldest position)
        const startEl = document.createElement('div');
        startEl.className = 'trail-time-marker';
        startEl.style.cssText = 'font-size:10px;background:#7c3aed;color:#fff;padding:1px 4px;border-radius:3px;white-space:nowrap;';
        startEl.textContent = `Start ${startTime}`;
        new maplibregl.Marker({ element: startEl, anchor: 'bottom' }).setLngLat([first.lon, first.lat]).addTo(map);

        // End marker (at cow's current visual position)
        const endEl = document.createElement('div');
        endEl.className = 'trail-time-marker';
        endEl.style.cssText = 'font-size:10px;background:#7c3aed;color:#fff;padding:1px 4px;border-radius:3px;white-space:nowrap;';
        endEl.textContent = `Now ${endTime}`;
        new maplibregl.Marker({ element: endEl, anchor: 'bottom' }).setLngLat([endLng, endLat]).addTo(map);
      }
    } catch {
      // No trail data available — don't render a fallback trail at wrong coordinates
      setTrailData([]);
      addToast({ title: 'No Trail', message: 'No movement history available for this animal', severity: 'info', duration: 3000 });
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
    setTrailDate('');
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

  // ─── Live Area Calculation (Shoelace Formula) ──────
  function calculatePolygonAreaHa(points: [number, number][]): number {
    // points are [lng, lat] pairs
    if (points.length < 3) return 0;
    // Use shoelace formula with projected coordinates (approx metres)
    const refLat = points[0][1];
    const mPerDegLat = 111320;
    const mPerDegLon = 111320 * Math.cos(refLat * Math.PI / 180);

    let area = 0;
    const n = points.length;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const xi = points[i][0] * mPerDegLon;
      const yi = points[i][1] * mPerDegLat;
      const xj = points[j][0] * mPerDegLon;
      const yj = points[j][1] * mPerDegLat;
      area += xi * yj - xj * yi;
    }
    return Math.abs(area / 2) / 10000; // m² → hectares
  }

  const drawingAreaHa = calculatePolygonAreaHa(drawingPoints);
  const TARGET_HA_MIN = 50;
  const TARGET_HA_MAX = 70;
  const areaInRange = drawingAreaHa >= TARGET_HA_MIN && drawingAreaHa <= TARGET_HA_MAX;
  const areaColor = drawingAreaHa < TARGET_HA_MIN ? '#ef4444' : areaInRange ? '#22c55e' : '#f59e0b';

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

      // Deterministic hash from animal ID for stable scatter positioning.
      // Same animal always gets the same offset regardless of API response order.
      function stableHash(id: string): number {
        let h = 0;
        for (let i = 0; i < id.length; i++) {
          h = ((h << 5) - h + id.charCodeAt(i)) | 0;
        }
        return Math.abs(h);
      }

      // For animals sharing a position, scatter using ID-based deterministic offset
      animals.forEach((a: any) => {
        const key = `${a.last_latitude.toFixed(5)},${a.last_longitude.toFixed(5)}`;
        const total = positionMap.get(key) || 1;

        let lng = a.last_longitude;
        let lat = a.last_latitude;

        // Deterministic scatter for overlapping positions (seeded by animal ID)
        if (total > 1) {
          const hash = stableHash(a.id);
          // Use hash-derived angle for even angular distribution
          const angle = (hash % 1000) / 1000 * Math.PI * 2;
          // Radius varies by hash — spread between ~20-55m
          const radius = 0.00015 + ((hash % 997) / 997) * 0.00035;
          // Small deterministic jitter from a second hash derivative
          const jitterA = angle + ((hash >> 8) % 100) / 100 * 0.3;
          const jitterR = radius * (0.75 + ((hash >> 16) % 100) / 100 * 0.5);
          lng += Math.cos(jitterA) * jitterR;
          lat += Math.sin(jitterA) * jitterR * 0.8;
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
    const pinColor = isLow ? '#ea580c' : '#dc2626';

    // Outer element: static container, no transforms — MapLibre controls positioning
    const el = document.createElement('div');
    el.style.cssText = 'display:flex;flex-direction:column;align-items:center;cursor:pointer;';
    el.title = name;

    // Inner wrapper: handles hover scale without affecting MapLibre's position transform
    const inner = document.createElement('div');
    inner.style.cssText = `display:flex;flex-direction:column;align-items:center;transition:transform 0.15s ease;transform-origin:bottom center;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.4));`;
    inner.innerHTML = `
      <div style="width:30px;height:30px;background:${pinColor};border:2px solid ${resolved === 'dark' ? '#374151' : 'white'};border-radius:50% 50% 50% 0;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;">
        <span style="transform:rotate(45deg);font-size:14px;">🐄</span>
      </div>
      <div style="width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:6px solid ${pinColor};margin-top:-2px;"></div>
    `;
    el.appendChild(inner);

    // Hover effect on inner element only — won't displace the marker
    el.addEventListener('mouseenter', () => { inner.style.transform = 'scale(1.15)'; });
    el.addEventListener('mouseleave', () => { inner.style.transform = 'scale(1)'; });
    el.addEventListener('click', (e) => { e.stopPropagation(); showTrail(id); });

    // No popup — click shows trail directly, tooltip on hover via title attribute
    const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat([lng, lat])
      .addTo(map);
    markersRef.current.set(id, marker);
  }

  // Realtime updates — apply same deterministic scatter as initial fetch
  useEffect(() => {
    if (!mapRef.current) return;

    // Collect raw positions to detect overlaps
    const posEntries = Array.from(positions.entries());
    const positionCounts = new Map<string, number>();
    posEntries.forEach(([, pos]) => {
      const key = `${pos.position.latitude.toFixed(5)},${pos.position.longitude.toFixed(5)}`;
      positionCounts.set(key, (positionCounts.get(key) || 0) + 1);
    });

    function stableHash(id: string): number {
      let h = 0;
      for (let i = 0; i < id.length; i++) {
        h = ((h << 5) - h + id.charCodeAt(i)) | 0;
      }
      return Math.abs(h);
    }

    posEntries.forEach(([id, pos]) => {
      let lng = pos.position.longitude;
      let lat = pos.position.latitude;
      const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
      const total = positionCounts.get(key) || 1;

      if (total > 1) {
        const hash = stableHash(id);
        const angle = (hash % 1000) / 1000 * Math.PI * 2;
        const radius = 0.00015 + ((hash % 997) / 997) * 0.00035;
        const jitterA = angle + ((hash >> 8) % 100) / 100 * 0.3;
        const jitterR = radius * (0.75 + ((hash >> 16) % 100) / 100 * 0.5);
        lng += Math.cos(jitterA) * jitterR;
        lat += Math.sin(jitterA) * jitterR * 0.8;
      }

      addOrUpdateMarker(mapRef.current!, id, pos.animalName, lng, lat, pos.batteryLevel);
    });
  }, [positions]);

  // Auto-refresh (fallback — primary updates come via WebSocket)
  useEffect(() => {
    if (!selectedFarmId) return;
    const i = setInterval(() => {
      const map = mapRef.current;
      if (map && selectedFarmId) {
        fetchPositionsForFarm(map, selectedFarmId);
        fetchHerdsmanPositions(map, selectedFarmId);
      }
    }, 30000);
    return () => clearInterval(i);
  }, [selectedFarmId]);

  // ─── Herdsman Gateway Markers (Blue Person Icon) ───
  function addOrUpdateHerdsmanMarker(
    map: maplibregl.Map,
    id: string,
    name: string,
    serial: string,
    lng: number,
    lat: number,
    _battery?: number | null,
    _lastSeen?: string | null,
  ) {
    const existing = herdsmanMarkersRef.current.get(id);
    if (existing) { existing.setLngLat([lng, lat]); return; }

    // Outer element: static, no transforms — MapLibre controls positioning
    const el = document.createElement('div');
    el.style.cssText = 'display:flex;flex-direction:column;align-items:center;cursor:pointer;';
    el.title = `${name} (${serial})`;

    // Inner wrapper: handles hover scale without affecting MapLibre's position
    const inner = document.createElement('div');
    inner.style.cssText = 'display:flex;flex-direction:column;align-items:center;transition:transform 0.15s ease;transform-origin:bottom center;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.4));';
    inner.innerHTML = `
      <div style="width:32px;height:32px;background:#2563eb;border:2px solid ${resolved === 'dark' ? '#374151' : 'white'};border-radius:50%;display:flex;align-items:center;justify-content:center;">
        <span style="font-size:16px;">🚶</span>
      </div>
      <div style="font-size:9px;font-weight:bold;color:#fff;background:#1d4ed8;padding:1px 5px;border-radius:3px;margin-top:2px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,0.3);">${name}</div>
    `;
    el.appendChild(inner);

    el.addEventListener('mouseenter', () => { inner.style.transform = 'scale(1.15)'; });
    el.addEventListener('mouseleave', () => { inner.style.transform = 'scale(1)'; });

    const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat([lng, lat])
      .addTo(map);
    herdsmanMarkersRef.current.set(id, marker);
  }

  function clearHerdsmanMarkers() {
    herdsmanMarkersRef.current.forEach((marker) => marker.remove());
    herdsmanMarkersRef.current.clear();
  }

  async function fetchHerdsmanPositions(map: maplibregl.Map, farmId: string) {
    try {
      const fid = farmId || currentFarm || '';
      if (!fid) return;
      const resp = await apiClient.get('/api/gateway', { params: { farm_id: fid } });
      const gateways = resp.data;

      // Remove markers for gateways no longer in response
      const activeIds = new Set(gateways.map((g: any) => g.id));
      herdsmanMarkersRef.current.forEach((marker, id) => {
        if (!activeIds.has(id)) { marker.remove(); herdsmanMarkersRef.current.delete(id); }
      });

      // Add/update markers for gateways with positions
      gateways.forEach((g: any) => {
        if (g.last_latitude && g.last_longitude) {
          addOrUpdateHerdsmanMarker(
            map, g.id, g.herdsman_name || g.name, g.serial_number,
            g.last_longitude, g.last_latitude, g.last_battery_pct, g.last_seen,
          );
        }
      });
    } catch {
      // Gateway fetch failed — silently ignore, cattle markers still work
    }
  }

  // Load herdsman markers when farm changes
  useEffect(() => {
    if (!mapRef.current || !selectedFarmId || loading) return;
    clearHerdsmanMarkers();
    fetchHerdsmanPositions(mapRef.current, selectedFarmId);
  }, [selectedFarmId, loading]);

  // ─── Breach Alert Markers ──────────────────────────
  const alertMarkersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (loading || !mapRef.current) return;
    const map = mapRef.current;

    async function fetchAlerts() {
      try {
        const resp = await apiClient.get('/api/alerts', { params: { status: 'active' } });
        const alerts = resp.data;

        // Clear old alert markers
        alertMarkersRef.current.forEach(m => m.remove());
        alertMarkersRef.current = [];

        // For alerts without coordinates, use the animal's last known position
        for (const alert of alerts) {
          let lat = alert.latitude || alert.metadata?.latitude;
          let lon = alert.longitude || alert.metadata?.longitude;

          // If no coords in alert, try to get from the animal's current marker position
          if (!lat || !lon) {
            // Find the animal marker by checking all markers
            const animalMarker = Array.from(markersRef.current.values()).find(m => {
              const title = m.getElement()?.title || '';
              return alert.animal_name && title === alert.animal_name;
            });
            if (animalMarker) {
              const lngLat = animalMarker.getLngLat();
              lat = lngLat.lat;
              lon = lngLat.lng;
            }
          }

          if (!lat || !lon) continue;

          const el = document.createElement('div');
          el.style.cssText = `width:22px;height:22px;background:#ef4444;border:3px solid #fff;border-radius:50%;cursor:pointer;animation:pulse-badge 1.5s infinite;box-shadow:0 0 12px rgba(239,68,68,0.6);position:relative;z-index:100;`;
          el.title = `⚠️ ${alert.alert_type}: ${alert.message || ''}`;

          const popup = new maplibregl.Popup({ offset: 15 }).setHTML(`
            <div style="padding:8px;max-width:220px;">
              <strong style="color:#dc2626;">⚠️ ${(alert.alert_type || '').replace(/_/g, ' ').toUpperCase()}</strong><br/>
              <span style="font-size:12px;color:#666;">
                ${alert.message || 'Active alert'}<br/>
                Severity: <strong>${alert.severity}</strong><br/>
                ${alert.animal_name ? `Animal: ${alert.animal_name}` : ''}
              </span>
            </div>
          `);

          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([lon, lat])
            .setPopup(popup)
            .addTo(map);
          alertMarkersRef.current.push(marker);
        }
      } catch { /* alerts not available */ }
    }

    fetchAlerts();
    const alertInterval = setInterval(fetchAlerts, 15000); // Check every 15s
    return () => clearInterval(alertInterval);
  }, [loading]);

  function toggleLayer(l: LayerToggle) {
    setLayers((p) => ({ ...p, [l]: !p[l] }));
    if (l === 'trails' && layers.trails) clearTrail();
  }

  // Fly to herdsman position and show coordinate labels on distant cow markers
  function flyToHerdsman() {
    const map = mapRef.current;
    if (!map) return;

    // Find first herdsman marker
    const firstHerdsman = herdsmanMarkersRef.current.entries().next();
    if (!firstHerdsman.value) {
      addToast({ title: 'No Herdsman', message: 'No active herdsman on this farm', severity: 'info', duration: 3000 });
      return;
    }

    const [, herdsmanMarker] = firstHerdsman.value;
    const herdsmanPos = herdsmanMarker.getLngLat();

    // Fly to herdsman
    map.flyTo({ center: [herdsmanPos.lng, herdsmanPos.lat], zoom: 17, duration: 1200 });

    // Remove any existing coordinate labels
    document.querySelectorAll('.cow-coord-label').forEach(el => el.remove());

    // Show coordinate labels on cow markers that are far from the herdsman (>100m)
    markersRef.current.forEach((marker) => {
      const pos = marker.getLngLat();
      const distM = Math.sqrt(
        Math.pow((pos.lat - herdsmanPos.lat) * 111320, 2) +
        Math.pow((pos.lng - herdsmanPos.lng) * 111320 * Math.cos(pos.lat * Math.PI / 180), 2)
      );
      if (distM > 100) {
        const labelEl = document.createElement('div');
        labelEl.className = 'cow-coord-label';
        labelEl.style.cssText = 'font-size:9px;background:rgba(220,38,38,0.9);color:#fff;padding:2px 5px;border-radius:3px;white-space:nowrap;pointer-events:none;';
        labelEl.textContent = `${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)} (${Math.round(distM)}m)`;
        new maplibregl.Marker({ element: labelEl, anchor: 'top' })
          .setLngLat([pos.lng, pos.lat])
          .addTo(map);
      }
    });

    // Show herdsman coords
    const herdsmanLabel = document.createElement('div');
    herdsmanLabel.className = 'cow-coord-label';
    herdsmanLabel.style.cssText = 'font-size:10px;background:rgba(37,99,235,0.95);color:#fff;padding:2px 6px;border-radius:3px;white-space:nowrap;font-weight:bold;pointer-events:none;';
    herdsmanLabel.textContent = `Herdsman: ${herdsmanPos.lat.toFixed(5)}, ${herdsmanPos.lng.toFixed(5)}`;
    new maplibregl.Marker({ element: herdsmanLabel, anchor: 'top', offset: [0, 20] })
      .setLngLat([herdsmanPos.lng, herdsmanPos.lat])
      .addTo(map);

    addToast({ title: 'Herdsman Located', message: `Position: ${herdsmanPos.lat.toFixed(5)}, ${herdsmanPos.lng.toFixed(5)}`, severity: 'info', duration: 5000 });
  }

  // ─── Render ────────────────────────────────────────
  // Icons for tile sources
  const tileIcons: Record<TileSource, { icon: React.ReactNode; label: string }> = {
    osm: {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      ),
      label: 'Street',
    },
    satellite: {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      label: 'Satellite',
    },
    terrain: {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4-4 4 4 4-8 4 8" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M2 20h20" />
        </svg>
      ),
      label: 'Terrain',
    },
    dark: {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      ),
      label: 'Dark',
    },
  };

  return (
    <div className="h-full w-full flex flex-col" style={{ height: '100%' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-2 sm:px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-10 shrink-0 theme-transition gap-2 flex-wrap">
        <div className="flex items-center gap-2 sm:gap-4 flex-wrap min-w-0">
          <h2 className="text-base sm:text-lg font-semibold text-gray-800 dark:text-white whitespace-nowrap">Live Map</h2>
          {/* Farm Selector */}
          {farms.length > 0 && (
            <select
              value={selectedFarmId}
              onChange={(e) => setSelectedFarmId(e.target.value)}
              className="px-2 py-1 sm:px-3 sm:py-1.5 text-xs sm:text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-brand-500 max-w-[140px] sm:max-w-none truncate"
              aria-label="Select farm"
            >
              {farms.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.name}{farm.province ? ` (${farm.province})` : ''}
                </option>
              ))}
            </select>
          )}
          {/* Refresh Button */}
          <button
            onClick={refreshDashboard}
            disabled={refreshing || loading}
            className="p-1.5 sm:p-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 hover:text-gray-900 dark:hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Refresh dashboard data"
            title="Refresh data for selected location"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
        <div className="flex items-center gap-2">
          {selectedAnimal && (
            <>
              <input
                type="date"
                value={trailDate}
                onChange={(e) => { setTrailDate(e.target.value); if (selectedAnimal) showTrail(selectedAnimal, e.target.value); }}
                className="px-2 py-1 text-xs border border-purple-300 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                title="Select date to view that day's trail"
              />
              <button onClick={clearTrail} className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded border border-purple-300">✕</button>
            </>
          )}
          {!drawingMode ? (
            <button onClick={() => { setDrawingMode(true); setMarkingMode(false); setDrawingPoints([]); }} className="px-2 py-1 sm:px-3 sm:py-1.5 text-xs sm:text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 whitespace-nowrap">+ Fence</button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600">
                {editingFenceId ? '✏️ ' : ''}{drawingPoints.length} pts
                {drawingPoints.length >= 3 && (
                  <span style={{ color: areaColor, fontWeight: 'bold', marginLeft: 6 }}>
                    📐 {drawingAreaHa < 1 ? `${Math.round(drawingAreaHa * 10000)} m²` : `${drawingAreaHa.toFixed(1)} ha`}
                    {drawingAreaHa > 0 && drawingAreaHa < TARGET_HA_MIN && (
                      <span className="text-red-500 ml-1">(need {(TARGET_HA_MIN - drawingAreaHa).toFixed(1)} more ha)</span>
                    )}
                    {areaInRange && <span className="text-green-600 ml-1">✓ Target</span>}
                    {drawingAreaHa > TARGET_HA_MAX && <span className="text-amber-500 ml-1">(over target)</span>}
                  </span>
                )}
              </span>
              <button onClick={() => setDrawingPoints(p => p.slice(0, -1))} disabled={drawingPoints.length === 0} className="px-2 py-1 text-xs bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded disabled:opacity-50" title="Undo last point">↩</button>
              <button onClick={finishDrawing} disabled={drawingPoints.length < 3} className="px-2 py-1 text-xs bg-green-600 text-white rounded disabled:opacity-50">✓</button>
              <button onClick={() => { setDrawingMode(false); setDrawingPoints([]); setEditingFenceId(null); }} className="px-2 py-1 text-xs bg-red-600 text-white rounded">✕</button>
            </div>
          )}
          {/* Mark Structure tool */}
          {!markingMode ? (
            <button onClick={() => { setMarkingMode(true); setDrawingMode(false); setShowMarkedPanel(true); }} className="px-2 py-1 sm:px-3 sm:py-1.5 text-xs sm:text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 whitespace-nowrap">📍 Mark</button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-red-400 animate-pulse">Click structures on map</span>
              <button onClick={() => setShowMarkedPanel(!showMarkedPanel)} className="px-2 py-1 text-xs bg-gray-600 text-white rounded">{markedStructures.length} marked</button>
              <button onClick={() => { setMarkingMode(false); }} className="px-2 py-1 text-xs bg-red-600 text-white rounded">Done</button>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 min-h-0 relative" style={{ minHeight: 0 }}>
        <div ref={mapContainerRef} className="absolute inset-0" style={{ cursor: (drawingMode || markingMode) ? 'crosshair' : 'grab', width: '100%', height: '100%' }} />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100/80 dark:bg-gray-900/80 z-10">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full mx-auto mb-2"></div>
              <p className="text-gray-500">Loading map...</p>
            </div>
          </div>
        )}

        {/* Floating Map Controls — always visible */}

        {/* Live Area Indicator (visible during drawing) */}
        {drawingMode && drawingPoints.length >= 2 && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 bg-gray-900/90 backdrop-blur-sm text-white px-4 py-2 rounded-xl shadow-lg flex items-center gap-3">
            <span className="text-2xl">📐</span>
            <div>
              <div className="text-lg font-bold" style={{ color: areaColor }}>
                {drawingAreaHa < 1 ? `${Math.round(drawingAreaHa * 10000)} m²` : `${drawingAreaHa.toFixed(2)} ha`}
              </div>
              <div className="text-xs text-gray-300">
                {drawingAreaHa < TARGET_HA_MIN && `Need ~${(TARGET_HA_MIN - drawingAreaHa).toFixed(1)} more ha to reach target`}
                {areaInRange && `✓ Within target range (${TARGET_HA_MIN}–${TARGET_HA_MAX} ha)`}
                {drawingAreaHa > TARGET_HA_MAX && `Over target by ${(drawingAreaHa - TARGET_HA_MAX).toFixed(1)} ha`}
                {drawingPoints.length < 3 && 'Add at least 1 more point'}
              </div>
            </div>
            <div className="text-xs text-gray-400 border-l border-gray-600 pl-3">
              {drawingPoints.length} points<br/>
              Target: {TARGET_HA_MIN}–{TARGET_HA_MAX} ha
            </div>
          </div>
        )}

        {/* Marked Structures Panel */}
        {showMarkedPanel && markedStructures.length > 0 && (
          <div className="absolute top-16 right-3 z-30 bg-gray-900/95 backdrop-blur-sm rounded-xl shadow-xl p-3 max-w-xs max-h-80 overflow-auto">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-white text-sm font-bold">📍 Marked Structures ({markedStructures.length})</h3>
              <button onClick={() => setShowMarkedPanel(false)} className="text-gray-400 text-xs">✕</button>
            </div>
            <div className="space-y-1">
              {markedStructures.map((s) => (
                <div key={s.id} className="text-xs bg-gray-800 rounded p-1.5 flex items-center gap-2">
                  <span className="text-red-400 font-bold">X{s.id}</span>
                  <span className="text-white flex-1">{s.label} ({s.type})</span>
                  <span className="text-gray-400 text-[10px]">{s.lat.toFixed(6)}, {s.lon.toFixed(6)}</span>
                  <button onClick={() => {
                    setMarkedStructures(prev => prev.filter(x => x.id !== s.id));
                    const m = markedMarkersRef.current[s.id - 1];
                    if (m) m.remove();
                  }} className="text-red-500 text-xs">×</button>
                </div>
              ))}
            </div>
            <button
              onClick={() => {
                const csv = ['ID,Label,Type,Latitude,Longitude', ...markedStructures.map(s => `X${s.id},${s.label},${s.type},${s.lat.toFixed(7)},${s.lon.toFixed(7)}`)].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = 'sibanyoni_exclusion_structures.csv'; a.click();
                URL.revokeObjectURL(url);
              }}
              className="mt-2 w-full px-2 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
            >📥 Export CSV (for council)</button>
            <button
              onClick={() => {
                const text = markedStructures.map(s => `X${s.id}: ${s.label} (${s.type}) — Lat: ${s.lat.toFixed(7)}, Lon: ${s.lon.toFixed(7)}`).join('\n');
                navigator.clipboard.writeText(text);
                addToast({ title: 'Copied', message: 'Coordinates copied to clipboard', severity: 'success', duration: 3000 });
              }}
              className="mt-1 w-full px-2 py-1.5 text-xs bg-gray-700 text-white rounded hover:bg-gray-600"
            >📋 Copy coordinates</button>
          </div>
        )}

        <div className="absolute top-3 left-3 z-20 flex flex-col gap-2">
          {/* Tile Source Switcher */}
          <div className="bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm rounded-lg shadow-lg p-1.5 flex flex-col gap-1">
            {(Object.keys(TILE_SOURCES) as TileSource[]).map((key) => (
              <button
                key={key}
                onClick={() => setTileSource(key)}
                className={`map-control-btn relative p-2 rounded-md transition-colors ${
                  tileSource === key
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                aria-label={tileIcons[key].label}
              >
                {tileIcons[key].icon}
                <span className="map-control-tooltip">{tileIcons[key].label}</span>
              </button>
            ))}
          </div>

          {/* Layer Toggles */}
          <div className="bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm rounded-lg shadow-lg p-1.5 flex flex-col gap-1">
            <button
              onClick={() => toggleLayer('animals')}
              className={`map-control-btn relative p-2 rounded-md transition-colors ${
                layers.animals
                  ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400'
                  : 'text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              aria-label="Toggle animals"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="4" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 2v2m0 16v2m10-10h-2M4 12H2m15.07-7.07l-1.41 1.41M8.34 15.66l-1.41 1.41m12.14 0l-1.41-1.41M8.34 8.34L6.93 6.93" />
              </svg>
              <span className="map-control-tooltip">Animals</span>
            </button>
            <button
              onClick={() => toggleLayer('geofences')}
              className={`map-control-btn relative p-2 rounded-md transition-colors ${
                layers.geofences
                  ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400'
                  : 'text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              aria-label="Toggle geofences"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              <span className="map-control-tooltip">Geofences</span>
            </button>
            <button
              onClick={() => setShowActiveOnly(!showActiveOnly)}
              className={`map-control-btn relative p-2 rounded-md transition-colors text-[10px] font-bold leading-none ${
                showActiveOnly
                  ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400'
                  : 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400'
              }`}
              aria-label="Filter geofences: active only or all"
              title={showActiveOnly ? 'Showing active fences only — click to show all' : 'Showing ALL fences — click to filter active only'}
            >
              {showActiveOnly ? 'A' : '✱'}
              <span className="map-control-tooltip">{showActiveOnly ? 'Active Only' : 'All Fences'}</span>
            </button>
            <button
              onClick={() => toggleLayer('trails')}
              className={`map-control-btn relative p-2 rounded-md transition-colors ${
                layers.trails
                  ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400'
                  : 'text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              aria-label="Toggle trails"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span className="map-control-tooltip">Trails</span>
            </button>
            <button
              onClick={() => toggleLayer('markers')}
              className={`map-control-btn relative p-2 rounded-md transition-colors ${
                layers.markers
                  ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400'
                  : 'text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              aria-label="Toggle marked structures"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span className="map-control-tooltip">Structures</span>
            </button>
            <button
              onClick={flyToHerdsman}
              className="map-control-btn relative p-2 rounded-md transition-colors text-gray-400 dark:text-gray-500 hover:bg-blue-100 dark:hover:bg-blue-900/40 hover:text-blue-700 dark:hover:text-blue-400"
              aria-label="Fly to herdsman"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="map-control-tooltip">Find Herdsman</span>
            </button>
          </div>
        </div>
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-400 z-10 shrink-0 theme-transition">
        <div className="flex items-center gap-4">
          <span className="text-green-600 font-medium">🟢 {animalCount} animals</span>
          <span className="text-blue-600">{geofenceIds.length || DEMO_GEOFENCES.length} geofences</span>
          {selectedAnimal && <span className="text-purple-600">Trail: {trailData.length} pts</span>}
          {drawingMode && <span className="text-amber-600 font-medium">Drawing active</span>}
        </div>
        <span className="text-gray-400">
          Tiles: {TILE_SOURCES[tileSource].label} |{' '}
          {connectionStatus === 'connected' && <span className="text-green-500">Live via WebSocket</span>}
          {connectionStatus === 'connecting' && <span className="text-yellow-500">Connecting...</span>}
          {connectionStatus === 'disconnected' && <span className="text-red-400">Disconnected (polling)</span>}
        </span>
      </div>
    </div>
  );
}
