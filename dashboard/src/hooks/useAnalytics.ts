/**
 * TanStack Query hooks for the analytics API endpoints.
 *
 * All hooks accept farm_id and a date range, and return typed data
 * from the /api/v1/analytics/* endpoints.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface HeatmapCell {
  lat: number;
  lon: number;
  count: number;
}

export interface HeatmapResponse {
  farm_id: string;
  resolution: number;
  start: string;
  end: string;
  cells: HeatmapCell[];
}

export interface ActivityBucket {
  time_bucket: string;
  grazing: number;
  resting: number;
  walking: number;
  running: number;
  total: number;
}

export interface ActivityResponse {
  farm_id: string;
  interval: string;
  start: string;
  end: string;
  data: ActivityBucket[];
  summary: {
    grazing_pct: number;
    resting_pct: number;
    walking_pct: number;
    running_pct: number;
  };
}

export interface DistanceBucket {
  time_bucket: string;
  distance_km: number;
  animals_active: number;
}

export interface DistanceAnimalDetail {
  animal_id: string;
  animal_name: string | null;
  distance_km: number;
}

export interface DistanceResponse {
  farm_id: string;
  interval: string;
  start: string;
  end: string;
  total_distance_km: number;
  data: DistanceBucket[];
  top_animals: DistanceAnimalDetail[];
}

export interface ComplianceDetail {
  geofence_id: string;
  geofence_name: string;
  total_points: number;
  inside_points: number;
  compliance_rate: number;
}

export interface ComplianceResponse {
  farm_id: string;
  start: string;
  end: string;
  overall_compliance: number;
  details: ComplianceDetail[];
}

// ─── Date Range Helper ───────────────────────────────────────────────────────

export type DateRange = '24h' | '7d' | '30d';

function getTimeRange(range: DateRange): { start: string; end: string } {
  const end = new Date();
  const start = new Date();

  switch (range) {
    case '24h':
      start.setHours(start.getHours() - 24);
      break;
    case '7d':
      start.setDate(start.getDate() - 7);
      break;
    case '30d':
      start.setDate(start.getDate() - 30);
      break;
  }

  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

export function useHeatmap(dateRange: DateRange, resolution = 50) {
  const farmId = useAuthStore((s) => s.currentFarm);
  const { start, end } = getTimeRange(dateRange);

  return useQuery<HeatmapResponse>({
    queryKey: ['analytics', 'heatmap', farmId, dateRange, resolution],
    queryFn: async () => {
      const resp = await apiClient.get('/api/v1/analytics/heatmap', {
        params: { farm_id: farmId, start, end, resolution },
      });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}

export function useActivity(dateRange: DateRange, interval = '1h', animalId?: string) {
  const farmId = useAuthStore((s) => s.currentFarm);
  const { start, end } = getTimeRange(dateRange);

  return useQuery<ActivityResponse>({
    queryKey: ['analytics', 'activity', farmId, dateRange, interval, animalId],
    queryFn: async () => {
      const params: Record<string, string> = {
        farm_id: farmId!,
        start,
        end,
        interval,
      };
      if (animalId) params.animal_id = animalId;

      const resp = await apiClient.get('/api/v1/analytics/activity', { params });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}

export function useDistance(dateRange: DateRange, interval = '1d', animalId?: string) {
  const farmId = useAuthStore((s) => s.currentFarm);
  const { start, end } = getTimeRange(dateRange);

  return useQuery<DistanceResponse>({
    queryKey: ['analytics', 'distance', farmId, dateRange, interval, animalId],
    queryFn: async () => {
      const params: Record<string, string> = {
        farm_id: farmId!,
        start,
        end,
        interval,
      };
      if (animalId) params.animal_id = animalId;

      const resp = await apiClient.get('/api/v1/analytics/distance', { params });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}

export function useCompliance(dateRange: DateRange, geofenceId?: string) {
  const farmId = useAuthStore((s) => s.currentFarm);
  const { start, end } = getTimeRange(dateRange);

  return useQuery<ComplianceResponse>({
    queryKey: ['analytics', 'compliance', farmId, dateRange, geofenceId],
    queryFn: async () => {
      const params: Record<string, string> = {
        farm_id: farmId!,
        start,
        end,
      };
      if (geofenceId) params.geofence_id = geofenceId;

      const resp = await apiClient.get('/api/v1/analytics/compliance', { params });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}
