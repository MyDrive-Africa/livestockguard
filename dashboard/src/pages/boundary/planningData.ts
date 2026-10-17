/**
 * @file planningData.ts
 * @description Static planning data for the Sibanyoni Boundary Planner.
 *
 * This module is DELIBERATELY isolated from the operational system:
 *   - Nothing here is written to the `geofences` table.
 *   - Nothing here triggers breach detection or alerts.
 *   - No simulator, beam, or robot preset reads this file.
 *
 * It is a pure data source for the read-only Boundary Planner page, which
 * draws candidate farm-boundary options over the 14 verified exclusion
 * structures so a human can compare them and pick one. Promotion of a chosen
 * option into a real geofence is a separate, deliberate step (not built yet).
 *
 * Source of truth for the coordinates:
 *   docs/SIBANYONI_EXCLUSION_REGISTER.md (verified 2 Aug 2026)
 *
 * Coordinate convention: GeoJSON uses [lon, lat] order.
 */

// ─── Farm reference ───────────────────────────────────────────────────────────

export const SIBANYONI_CENTRE = { lat: -25.3580560, lon: 25.3612750 };

/** Metres-per-degree at the Sibanyoni latitude (used for buffer circles). */
const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 100023; // ≈ 111320 * cos(-25.36°)

// ─── Verified exclusion structures (X1–X14) ────────────────────────────────────

export type StructureType = 'house' | 'compound' | 'field';

export interface Structure {
  id: string; // "X1".."X14"
  label: string;
  type: StructureType;
  lat: number;
  lon: number;
  cluster: ClusterId;
  notes: string;
}

export type ClusterId = 'A' | 'B' | 'C' | 'D' | 'E';

export const STRUCTURES: Structure[] = [
  { id: 'X1', label: 'House 1', type: 'house', lat: -25.3576415, lon: 25.3608834, cluster: 'A', notes: 'Primary dwelling, tin roof visible' },
  { id: 'X2', label: 'Structure of House 1', type: 'compound', lat: -25.3576270, lon: 25.3607225, cluster: 'A', notes: 'Outbuilding/annex of X1' },
  { id: 'X3', label: 'Compound', type: 'house', lat: -25.3574864, lon: 25.3601109, cluster: 'A', notes: 'Separate dwelling, cleared yard' },
  { id: 'X4', label: 'House', type: 'house', lat: -25.3572489, lon: 25.3599822, cluster: 'A', notes: 'Standalone house, near X3' },
  { id: 'X5', label: 'Compound', type: 'compound', lat: -25.3568780, lon: 25.3586491, cluster: 'B', notes: 'Multi-structure compound' },
  { id: 'X6', label: 'Structure', type: 'house', lat: -25.3568320, lon: 25.3587591, cluster: 'B', notes: 'Structure adjacent to X5' },
  { id: 'X7', label: 'Compound', type: 'house', lat: -25.3574428, lon: 25.3602423, cluster: 'A', notes: 'House within compound cluster' },
  { id: 'X8', label: 'Compound', type: 'compound', lat: -25.3593503, lon: 25.3597435, cluster: 'C', notes: 'Southern compound, multiple structures' },
  { id: 'X9', label: 'Compound', type: 'compound', lat: -25.3592073, lon: 25.3594270, cluster: 'C', notes: 'Southern compound, adjacent to X8' },
  { id: 'X10', label: 'Compound', type: 'compound', lat: -25.3601307, lon: 25.3598963, cluster: 'D', notes: 'Far south compound' },
  { id: 'X11', label: 'Field', type: 'field', lat: -25.3600508, lon: 25.3593009, cluster: 'D', notes: 'Cultivated/fenced field' },
  { id: 'X12', label: 'Compound', type: 'compound', lat: -25.3605840, lon: 25.3597998, cluster: 'D', notes: 'Southernmost compound identified' },
  { id: 'X13', label: 'Compound', type: 'house', lat: -25.3585892, lon: 25.3503101, cluster: 'E', notes: 'Western compound (far west of main cluster)' },
  { id: 'X14', label: 'House', type: 'house', lat: -25.3583081, lon: 25.3493445, cluster: 'E', notes: 'Far western house (westernmost structure)' },
];

// ─── Clusters (A–E) with recommended buffers ────────────────────────────────────

export interface Cluster {
  id: ClusterId;
  name: string;
  bufferM: number; // recommended buffer from the register (20–30 m)
  description: string;
}

export const CLUSTERS: Cluster[] = [
  { id: 'A', name: 'North-East', bufferM: 30, description: 'X1–X4, X7 — residential neighbourhood along the road' },
  { id: 'B', name: 'North-West', bufferM: 20, description: 'X5, X6 — compound with adjacent structure' },
  { id: 'C', name: 'Centre-South', bufferM: 20, description: 'X8, X9 — two adjacent compounds' },
  { id: 'D', name: 'Far South', bufferM: 30, description: 'X10–X12 — compounds plus a cultivated field' },
  { id: 'E', name: 'Far West', bufferM: 30, description: 'X13, X14 — two structures ~1 km west' },
];

// ─── Geometry helpers ───────────────────────────────────────────────────────────

/** Offset a lat/lon point by metres (dx east, dy north). Returns [lon, lat]. */
function offsetMetres(lat: number, lon: number, dxM: number, dyM: number): [number, number] {
  return [lon + dxM / M_PER_DEG_LON, lat + dyM / M_PER_DEG_LAT];
}

/** Build a closed circle polygon ring around a point, radius in metres. */
export function circleRing(lat: number, lon: number, radiusM: number, steps = 48): [number, number][] {
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    ring.push(offsetMetres(lat, lon, radiusM * Math.cos(theta), radiusM * Math.sin(theta)));
  }
  return ring;
}

/** Axis-aligned bounding box (with padding) around a set of points → closed ring. */
function bboxRing(pts: { lat: number; lon: number }[], padM: number): [number, number][] {
  const lats = pts.map((p) => p.lat);
  const lons = pts.map((p) => p.lon);
  const padLat = padM / M_PER_DEG_LAT;
  const padLon = padM / M_PER_DEG_LON;
  const minLat = Math.min(...lats) - padLat;
  const maxLat = Math.max(...lats) + padLat;
  const minLon = Math.min(...lons) - padLon;
  const maxLon = Math.max(...lons) + padLon;
  return [
    [minLon, maxLat],
    [maxLon, maxLat],
    [maxLon, minLat],
    [minLon, minLat],
    [minLon, maxLat],
  ];
}

// ─── Buffer features (per-structure and per-cluster) ────────────────────────────

export interface BufferMode {
  perStructure: GeoJSON.Feature<GeoJSON.Polygon>[];
  perCluster: GeoJSON.Feature<GeoJSON.Polygon>[];
}

/** Per-structure buffer circles (14 circles), each using its cluster's buffer. */
export function structureBuffers(): GeoJSON.Feature<GeoJSON.Polygon>[] {
  return STRUCTURES.map((s) => {
    const buffer = CLUSTERS.find((c) => c.id === s.cluster)?.bufferM ?? 25;
    return {
      type: 'Feature',
      properties: { id: s.id, label: s.label, cluster: s.cluster, bufferM: buffer },
      geometry: { type: 'Polygon', coordinates: [circleRing(s.lat, s.lon, buffer)] },
    };
  });
}

/** Per-cluster buffer zones (5 padded bounding boxes). */
export function clusterBuffers(): GeoJSON.Feature<GeoJSON.Polygon>[] {
  return CLUSTERS.map((cluster) => {
    const members = STRUCTURES.filter((s) => s.cluster === cluster.id);
    return {
      type: 'Feature',
      properties: { id: cluster.id, name: cluster.name, bufferM: cluster.bufferM, count: members.length },
      geometry: { type: 'Polygon', coordinates: [bboxRing(members, cluster.bufferM)] },
    };
  });
}

// ─── Candidate boundary options ─────────────────────────────────────────────────

export interface BoundaryOption {
  id: 'P1' | 'P2' | 'P3';
  name: string;
  color: string;
  areaHa: number;
  keepsRealCentre: boolean;
  summary: string;
  /** Outer boundary ring(s). P3 uses a boundary + separate exclusion pockets. */
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
  /** Optional exclusion pockets drawn separately (P3). */
  pockets?: GeoJSON.Feature<GeoJSON.Polygon>[];
  draft: boolean;
}

// P1 — AS-v2 corridor rectangle (already in seed_data.sql, moves farm west).
const P1_RING: [number, number][] = [
  [25.3506000, -25.3545566],
  [25.3583000, -25.3545566],
  [25.3583000, -25.3615634],
  [25.3506000, -25.3615634],
  [25.3506000, -25.3545566],
];

// P2 — DRAFT concave boundary kept on the real farm centre.
// Strategy: a box around the real centre (approx the original 50ha extent,
// nudged so the south edge clears clusters C/D and the north edge sits below
// clusters A/B), with the north-east corner notched inward to carve out the
// Cluster A residential strip (X1–X4, X7) with a ~30 m margin.
// This is a best-fit PROPOSAL for review — not surveyed.
//
// Real-centre reference box: lon 25.3548 → 25.3612, lat -25.3583 → -25.3648
// Cluster A sits around lat -25.3572..-25.3577, lon 25.3600..25.3609 (north-east),
// so we cut the NE corner in to lon 25.3596 / lat -25.3585 with a margin.
const P2_RING: [number, number][] = [
  [25.3548000, -25.3583000], // NW
  [25.3595500, -25.3583000], // N edge up to the notch (west of Cluster A + 30m)
  [25.3595500, -25.3589000], // step south to clear Cluster A / B underside
  [25.3612000, -25.3589000], // continue east along the notched (lower) north edge
  [25.3612000, -25.3648000], // SE
  [25.3548000, -25.3648000], // SW
  [25.3548000, -25.3583000], // close
];

// P3 — generous boundary on the real centre + separate exclusion pockets.
// The boundary is a simple rectangle covering the real usable land; the
// structure clusters become their own exclusion pockets (drawn separately),
// mirroring how the firebreak/dam exclusions already work operationally.
const P3_RING: [number, number][] = [
  [25.3548000, -25.3568000], // NW (kept south of clusters A/B)
  [25.3612000, -25.3568000], // NE
  [25.3612000, -25.3648000], // SE
  [25.3548000, -25.3648000], // SW
  [25.3548000, -25.3568000], // close
];

export const BOUNDARY_OPTIONS: BoundaryOption[] = [
  {
    id: 'P1',
    name: 'P1 · AS-v2 corridor (baseline)',
    color: '#3b82f6',
    areaHa: 60,
    keepsRealCentre: false,
    summary: 'Rectangle in the clear 775m corridor between the western (X13/14) and eastern (X1–12) clusters. Excludes all structures but relocates the farm ~700m west of its real centre. This is the boundary currently in seed_data.sql.',
    geometry: { type: 'Polygon', coordinates: [P1_RING] },
    draft: false,
  },
  {
    id: 'P2',
    name: 'P2 · Concave, real centre (DRAFT)',
    color: '#a855f7',
    areaHa: 36,
    keepsRealCentre: true,
    summary: 'Keeps the farm on its real centre and notches the north-east corner inward to carve out the Cluster A residential strip with a 30m margin. Best-fit proposal derived from structure coordinates — not surveyed. Review the notch before adopting.',
    geometry: { type: 'Polygon', coordinates: [P2_RING] },
    draft: true,
  },
  {
    id: 'P3',
    name: 'P3 · Boundary + exclusion pockets (DRAFT)',
    color: '#14b8a6',
    areaHa: 41,
    keepsRealCentre: true,
    summary: 'A generous rectangular boundary on the real centre, with each structure cluster modelled as its own exclusion pocket (like the existing firebreak/dam exclusions). Breach = inside boundary AND outside every pocket.',
    geometry: { type: 'Polygon', coordinates: [P3_RING] },
    pockets: clusterBuffers().filter((f) => {
      // Only pockets that actually fall inside the P3 rectangle are relevant.
      const [minLon, maxLon] = [25.3548, 25.3612];
      const [minLat, maxLat] = [-25.3648, -25.3568];
      const ring = f.geometry.coordinates[0];
      return ring.some(([lon, lat]) => lon >= minLon && lon <= maxLon && lat >= minLat && lat <= maxLat);
    }),
    draft: true,
  },
];
