/**
 * TanStack Query hooks for the analytics API endpoints.
 *
 * All hooks accept farm_id and a date range, and return typed data
 * from the /api/v1/analytics/* endpoints.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { useEffect, useState } from 'react';

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
  fence_type: string;
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

// ─── Farm ID Resolution ──────────────────────────────────────────────────────

/**
 * Returns the active farm ID — either from the auth store or auto-fetched
 * from the API (first available farm). This ensures analytics work even when
 * no farm has been explicitly selected in the dashboard.
 */
function useActiveFarmId(): string | null {
  const storeFarmId = useAuthStore((s) => s.currentFarm);
  const switchFarm = useAuthStore((s) => s.switchFarm);
  const [resolvedFarmId, setResolvedFarmId] = useState<string | null>(storeFarmId);

  useEffect(() => {
    if (storeFarmId) {
      setResolvedFarmId(storeFarmId);
      return;
    }

    // No farm selected — fetch farms and auto-select the first one
    let cancelled = false;
    async function autoSelect() {
      try {
        const resp = await apiClient.get('/api/farms');
        if (!cancelled && resp.data?.length > 0) {
          const firstFarmId = resp.data[0].id;
          setResolvedFarmId(firstFarmId);
          switchFarm(firstFarmId);
        }
      } catch {
        // Try assignments endpoint as fallback
        try {
          const resp = await apiClient.get('/api/v1/assignments/me/farms');
          if (!cancelled && resp.data?.length > 0) {
            const firstFarmId = resp.data[0].farm_id;
            setResolvedFarmId(firstFarmId);
            switchFarm(firstFarmId);
          }
        } catch {
          // No farms available
        }
      }
    }
    autoSelect();
    return () => { cancelled = true; };
  }, [storeFarmId, switchFarm]);

  return resolvedFarmId;
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

export function useHeatmap(dateRange: DateRange, resolution = 50) {
  const farmId = useActiveFarmId();
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
  const farmId = useActiveFarmId();
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
  const farmId = useActiveFarmId();
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

export function useCompliance(dateRange: DateRange, geofenceId?: string, category?: string) {
  const farmId = useActiveFarmId();
  const { start, end } = getTimeRange(dateRange);

  return useQuery<ComplianceResponse>({
    queryKey: ['analytics', 'compliance', farmId, dateRange, geofenceId, category],
    queryFn: async () => {
      const params: Record<string, string> = {
        farm_id: farmId!,
        start,
        end,
      };
      if (geofenceId) params.geofence_id = geofenceId;
      if (category) params.category = category;

      const resp = await apiClient.get('/api/v1/analytics/compliance', { params });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}


// ─── Insights (Anomalies, Suggestions, Reports) ─────────────────────────────

export interface Anomaly {
  id: string;
  farm_id: string;
  animal_id: string | null;
  animal_name: string | null;
  anomaly_type: string;
  severity: string;
  status: string;
  description: string;
  evidence: Record<string, unknown>;
  detected_at: string;
  resolved_at: string | null;
}

export interface Suggestion {
  id: string;
  farm_id: string;
  anomaly_id: string | null;
  category: string;
  priority: string;
  title: string;
  description: string;
  recommended_action: string;
  evidence: Record<string, unknown> | null;
  status: string;
  created_at: string;
  expires_at: string | null;
}

export interface InsightsDashboardResponse {
  anomalies_active: number;
  anomalies_high: number;
  suggestions_pending: number;
  suggestions_high: number;
  latest_report_date: string | null;
  latest_report_summary: string | null;
  anomalies: Anomaly[];
  suggestions: Suggestion[];
}

export function useInsightsDashboard() {
  const farmId = useActiveFarmId();

  return useQuery<InsightsDashboardResponse>({
    queryKey: ['insights', 'dashboard', farmId],
    queryFn: async () => {
      const resp = await apiClient.get('/api/v1/insights/dashboard', {
        params: { farm_id: farmId },
      });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 60_000,
  });
}
