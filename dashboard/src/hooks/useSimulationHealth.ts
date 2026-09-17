/**
 * TanStack Query hook for the simulation preflight endpoint.
 *
 * Polls GET /api/v1/system/simulation-status, which reports — per farm that
 * owns a BLE gateway — whether data is actually flowing today (sightings,
 * distinct animals, an active herdsman session, gateway last-seen). The
 * dashboard banner uses this to make an idle/stopped simulator obvious instead
 * of looking like a scanning failure.
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

export interface SimulationFarmHealth {
  farm_id: string;
  farm_name: string;
  gateway_serial: string;
  gateway_last_seen: string | null;
  registered_tags: number;
  sightings_today: number;
  animals_today: number;
  session_active: boolean;
  /** True when the farm has tags to detect but nothing has been seen today. */
  stale: boolean;
}

export type SimulationOverall = 'healthy' | 'partial' | 'idle' | 'no_gateways';

export interface SimulationHealthResponse {
  status: string;
  overall: SimulationOverall;
  timestamp: string;
  farm_count: number;
  active_farm_count: number;
  stale_farm_count: number;
  farms: SimulationFarmHealth[];
}

export function useSimulationHealth(enabled = true) {
  return useQuery<SimulationHealthResponse>({
    queryKey: ['simulation', 'health'],
    queryFn: async () => {
      const resp = await apiClient.get('/api/v1/system/simulation-status');
      return resp.data;
    },
    enabled,
    refetchInterval: 10_000, // keep the banner fresh
    staleTime: 5_000,
  });
}
