/**
 * @file RobotHerdingLayer.tsx
 * @description Renders the robotic-herdsman layer onto an existing MapLibre map:
 * purple robot markers (with heading arrow and a line to their current target),
 * plus the farm's containment boundary (circle or polygon) with an inner buffer
 * band. Self-contained — it owns its markers/sources/layers and cleans them up,
 * so MapPage only has to mount it.
 *
 * Robot positions come live from the realtime store (`robot.update` WS events),
 * with the REST fleet query as the initial/fallback source. The boundary is read
 * from the farm's active geofence (circle centre+radius, or polygon geometry).
 *
 * @see useRobots — fleet + boundary data
 * @see useRealtimeStore — live robot telemetry
 */
import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useRobots } from '@/hooks/useRobots';
import { apiClient } from '@/api/client';
import type { Robot, Geofence } from '@/types';

const M_PER_DEG_LAT = 111_320.0;

const ROBOT_FILL = '#a855f7';
const ROBOT_EDGE = '#9333ea';
const BOUNDARY_COLOR = '#a855f7';
const BUFFER_COLOR = '#f59e0b';

interface RobotHerdingLayerProps {
  map: maplibregl.Map | null;
  ready: boolean;
  farmId: string;
  showRobots: boolean;
  showBoundary: boolean;
}

/** Build a closed ring approximating a circle, as [lng, lat] GeoJSON coords. */
function circleRing(centerLat: number, centerLon: number, radiusM: number, points = 64): number[][] {
  const ring: number[][] = [];
  const latScale = M_PER_DEG_LAT;
  const lonScale = M_PER_DEG_LAT * Math.cos((centerLat * Math.PI) / 180);
  for (let i = 0; i <= points; i++) {
    const theta = (i / points) * 2 * Math.PI;
    const dLat = (radiusM * Math.cos(theta)) / latScale;
    const dLon = (radiusM * Math.sin(theta)) / lonScale;
    ring.push([centerLon + dLon, centerLat + dLat]);
  }
  return ring;
}

/** Marker colour by status — charging/fault/offline are muted. */
function robotTint(status?: string): { fill: string; edge: string } {
  if (status === 'charging') return { fill: '#c4b5fd', edge: '#8b5cf6' };
  if (status === 'fault' || status === 'offline') return { fill: '#9ca3af', edge: '#6b7280' };
  if (status === 'shepherding' || status === 'enroute') return { fill: '#f472b6', edge: '#db2777' };
  return { fill: ROBOT_FILL, edge: ROBOT_EDGE };
}

export function RobotHerdingLayer({ map, ready, farmId, showRobots, showBoundary }: RobotHerdingLayerProps) {
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const boundaryIdsRef = useRef<string[]>([]);

  const { data: fleet } = useRobots();
  const liveRobots = useRealtimeStore((s) => s.robots);

  // ─── Boundary overlay (circle or polygon + buffer band) ───────────────────
  useEffect(() => {
    if (!map || !ready || !farmId) return;
    let cancelled = false;

    const clearBoundary = () => {
      for (const id of boundaryIdsRef.current) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      // sources share the base id sans -fill/-line suffix
      for (const src of ['robot-boundary', 'robot-buffer']) {
        if (map.getSource(src)) {
          try { map.removeSource(src); } catch { /* layers still referencing */ }
        }
      }
      boundaryIdsRef.current = [];
    };

    async function loadBoundary() {
      try {
        const resp = await apiClient.get('/api/v1/geofences', { params: { farm_id: farmId } });
        if (cancelled || !map) return;
        const fences: Geofence[] = resp.data;
        // Prefer an explicit circle; else the first active inclusion polygon.
        const circle = fences.find((f) => f.shape === 'circle' && f.center_latitude != null);
        clearBoundary();
        if (!showBoundary) return;

        if (circle && circle.center_latitude != null && circle.center_longitude != null && circle.radius_m) {
          const buffer = circle.buffer_m ?? 15;
          const outer = circleRing(circle.center_latitude, circle.center_longitude, circle.radius_m);
          const inner = circleRing(
            circle.center_latitude, circle.center_longitude,
            Math.max(1, circle.radius_m - buffer),
          );
          addRing('robot-boundary', outer, BOUNDARY_COLOR, false);
          addRing('robot-buffer', inner, BUFFER_COLOR, true);
        }
      } catch {
        /* no boundary available */
      }
    }

    function addRing(baseId: string, ring: number[][], color: string, dashed: boolean) {
      if (!map) return;
      const data: GeoJSON.Feature = {
        type: 'Feature', properties: {},
        geometry: { type: 'Polygon', coordinates: [ring] },
      };
      map.addSource(baseId, { type: 'geojson', data });
      const fillId = `${baseId}-fill`;
      const lineId = `${baseId}-line`;
      map.addLayer({
        id: fillId, type: 'fill', source: baseId,
        paint: { 'fill-color': color, 'fill-opacity': dashed ? 0.04 : 0.08 },
      });
      map.addLayer({
        id: lineId, type: 'line', source: baseId,
        paint: {
          'line-color': color, 'line-width': dashed ? 1.5 : 2.5,
          ...(dashed ? { 'line-dasharray': [2, 2] } : {}),
        },
      });
      boundaryIdsRef.current.push(fillId, lineId);
    }

    loadBoundary();
    return () => { cancelled = true; clearBoundary(); };
  }, [map, ready, farmId, showBoundary]);

  // ─── Robot markers + target lines ─────────────────────────────────────────
  useEffect(() => {
    if (!map || !ready) return;

    if (!showRobots) {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current.clear();
      return;
    }

    // Merge REST fleet with live telemetry (live wins on position/state).
    const merged = new Map<string, { lat: number; lon: number; heading: number; status?: string; name: string; battery?: number }>();
    (fleet ?? []).forEach((r: Robot) => {
      if (r.last_latitude != null && r.last_longitude != null) {
        merged.set(r.serial_number, {
          lat: r.last_latitude, lon: r.last_longitude,
          heading: r.heading_deg ?? 0, status: r.status, name: r.name,
          battery: r.battery_pct ?? undefined,
        });
      }
    });
    liveRobots.forEach((live, serial) => {
      const existing = merged.get(serial);
      merged.set(serial, {
        lat: live.position.latitude, lon: live.position.longitude,
        heading: live.position.heading ?? existing?.heading ?? 0,
        status: live.state ?? existing?.status,
        name: existing?.name ?? serial,
        battery: live.batteryLevel ?? existing?.battery,
      });
    });

    // Remove markers for robots no longer present.
    for (const [serial, marker] of markersRef.current.entries()) {
      if (!merged.has(serial)) { marker.remove(); markersRef.current.delete(serial); }
    }

    merged.forEach((r, serial) => {
      const existing = markersRef.current.get(serial);
      if (existing) {
        existing.setLngLat([r.lon, r.lat]);
        const arrow = existing.getElement().querySelector<HTMLElement>('.robot-arrow');
        if (arrow) arrow.style.transform = `rotate(${r.heading}deg)`;
        const badge = existing.getElement().querySelector<HTMLElement>('.robot-badge');
        if (badge) {
          const tint = robotTint(r.status);
          badge.style.background = tint.fill;
          badge.style.borderColor = tint.edge;
        }
        return;
      }
      const el = buildRobotElement(serial, r.name, r.heading, r.status, r.battery);
      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([r.lon, r.lat])
        .addTo(map);
      markersRef.current.set(serial, marker);
    });

    return () => { /* markers persist across renders; cleared on unmount below */ };
  }, [map, ready, showRobots, fleet, liveRobots]);

  // Unmount cleanup.
  useEffect(() => {
    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current.clear();
    };
  }, []);

  return null;
}

/**
 * Build the robot marker DOM. Outer element carries NO transform (MapLibre owns
 * positioning); the heading rotation is applied to an inner `.robot-arrow` and the
 * label stays upright.
 */
function buildRobotElement(
  serial: string, name: string, heading: number, status?: string, battery?: number,
): HTMLDivElement {
  const tint = robotTint(status);
  const outer = document.createElement('div');
  outer.style.display = 'flex';
  outer.style.flexDirection = 'column';
  outer.style.alignItems = 'center';
  outer.style.pointerEvents = 'auto';
  outer.title = `${name} · ${serial}${status ? ` · ${status}` : ''}${battery != null ? ` · ${battery}%` : ''}`;

  const badge = document.createElement('div');
  badge.className = 'robot-badge';
  badge.style.position = 'relative';
  badge.style.width = '26px';
  badge.style.height = '26px';
  badge.style.borderRadius = '50%';
  badge.style.background = tint.fill;
  badge.style.border = `2px solid ${tint.edge}`;
  badge.style.boxShadow = '0 1px 4px rgba(0,0,0,0.4)';
  badge.style.display = 'flex';
  badge.style.alignItems = 'center';
  badge.style.justifyContent = 'center';
  badge.style.fontSize = '14px';
  badge.textContent = '🤖';

  // Heading arrow — rotates independently of the label.
  const arrow = document.createElement('div');
  arrow.className = 'robot-arrow';
  arrow.style.position = 'absolute';
  arrow.style.top = '-9px';
  arrow.style.left = '50%';
  arrow.style.marginLeft = '-5px';
  arrow.style.width = '0';
  arrow.style.height = '0';
  arrow.style.borderLeft = '5px solid transparent';
  arrow.style.borderRight = '5px solid transparent';
  arrow.style.borderBottom = `8px solid ${tint.edge}`;
  arrow.style.transformOrigin = '50% 17px';
  arrow.style.transform = `rotate(${heading}deg)`;
  badge.appendChild(arrow);

  const label = document.createElement('div');
  label.textContent = serial;
  label.style.marginTop = '2px';
  label.style.fontSize = '10px';
  label.style.fontWeight = '600';
  label.style.color = '#fff';
  label.style.background = 'rgba(88,28,135,0.85)';
  label.style.padding = '0 4px';
  label.style.borderRadius = '4px';
  label.style.whiteSpace = 'nowrap';

  outer.appendChild(badge);
  outer.appendChild(label);
  return outer;
}
