import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapStore } from '@/stores/mapStore';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { apiClient } from '@/api/client';

// South Africa centre (Free State)
const DEFAULT_CENTER: [number, number] = [26.21, -29.12];
const DEFAULT_ZOOM = 13;

export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const [animalCount, setAnimalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const { visibleLayers, isDrawingFence, startDrawing, cancelDrawing } = useMapStore();
  const positions = useRealtimeStore((state) => state.positions);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        name: 'LivestockGuard',
        sources: {
          'osm-tiles': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    map.on('load', () => {
      setLoading(false);
      // Load initial positions from API
      fetchPositions(map);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Fetch latest positions from API and render markers
  async function fetchPositions(map: maplibregl.Map) {
    try {
      const resp = await apiClient.get('/api/animals', {
        params: { farm_id: '22222222-2222-2222-2222-222222222222' },
      });
      const animals = resp.data;
      setAnimalCount(animals.length);

      animals.forEach((animal: any) => {
        if (animal.last_latitude && animal.last_longitude) {
          addOrUpdateMarker(
            map,
            animal.id,
            animal.name,
            animal.last_longitude,
            animal.last_latitude,
            animal.battery_level,
          );
        }
      });
    } catch (err) {
      console.warn('Failed to fetch positions:', err);
      // Show demo markers if API unavailable
      addDemoMarkers(map);
    }
  }

  // Add demo markers for offline development
  function addDemoMarkers(map: maplibregl.Map) {
    const demoAnimals = [
      { id: '1', name: 'Bella', lng: 26.208, lat: -29.117, battery: 85 },
      { id: '2', name: 'Storm', lng: 26.212, lat: -29.119, battery: 92 },
      { id: '3', name: 'Thunder', lng: 26.215, lat: -29.121, battery: 78 },
      { id: '4', name: 'Daisy', lng: 26.205, lat: -29.123, battery: 65 },
      { id: '5', name: 'Rosie', lng: 26.210, lat: -29.130, battery: 45 },
    ];

    demoAnimals.forEach((a) => {
      addOrUpdateMarker(map, a.id, a.name, a.lng, a.lat, a.battery);
    });
    setAnimalCount(demoAnimals.length);
  }

  // Create or update a marker
  function addOrUpdateMarker(
    map: maplibregl.Map,
    id: string,
    name: string,
    lng: number,
    lat: number,
    battery?: number | null,
  ) {
    const existing = markersRef.current.get(id);

    if (existing) {
      existing.setLngLat([lng, lat]);
    } else {
      // Create marker element
      const el = document.createElement('div');
      el.className = 'animal-marker';
      el.style.cssText = `
        width: 32px; height: 32px;
        background: #16a34a; border: 2px solid white;
        border-radius: 50%; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        font-size: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      `;
      el.innerHTML = '🐄';
      el.title = name;

      // Low battery = orange marker
      if (battery !== null && battery !== undefined && battery < 20) {
        el.style.background = '#ea580c';
      }

      const popup = new maplibregl.Popup({ offset: 20 }).setHTML(`
        <div style="padding: 8px; min-width: 120px;">
          <strong>${name}</strong><br/>
          <span style="color: #666; font-size: 12px;">
            ${lat.toFixed(5)}, ${lng.toFixed(5)}<br/>
            Battery: ${battery ?? '?'}%
          </span>
        </div>
      `);

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([lng, lat])
        .setPopup(popup)
        .addTo(map);

      markersRef.current.set(id, marker);
    }
  }

  // Update markers when realtime positions change
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;

    positions.forEach((pos, animalId) => {
      addOrUpdateMarker(
        map,
        animalId,
        pos.animalName,
        pos.position.longitude,
        pos.position.latitude,
        pos.batteryLevel,
      );
    });
  }, [positions]);

  // Refresh positions every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (mapRef.current) fetchPositions(mapRef.current);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-800">Live Map</h2>
          <div className="flex items-center gap-2 text-xs">
            <button className="px-2 py-1 rounded bg-green-100 text-green-700 border border-green-300">
              Animals
            </button>
            <button className="px-2 py-1 rounded bg-blue-100 text-blue-700 border border-blue-300">
              Geofences
            </button>
            <button className="px-2 py-1 rounded bg-gray-100 text-gray-600 border border-gray-300">
              Trails
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isDrawingFence ? (
            <button
              onClick={startDrawing}
              className="px-3 py-1 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700"
            >
              + Draw Fence
            </button>
          ) : (
            <button
              onClick={cancelDrawing}
              className="px-3 py-1 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <div ref={mapContainerRef} className="absolute inset-0" />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100/80 z-10">
            <p className="text-gray-500">Loading map...</p>
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-t text-sm text-gray-600 z-10">
        <div className="flex items-center gap-4">
          <span className="text-green-600 font-medium">
            🟢 {animalCount} animals tracked
          </span>
        </div>
        <span className="text-gray-400">
          Centre: {DEFAULT_CENTER[1].toFixed(4)}, {DEFAULT_CENTER[0].toFixed(4)} | Auto-refresh: 30s
        </span>
      </div>
    </div>
  );
}
