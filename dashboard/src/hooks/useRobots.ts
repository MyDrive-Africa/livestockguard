/**
 * TanStack Query hooks for the robotic-herdsman API endpoints.
 *
 * Queries the herding-robot fleet, jobs, and containment status, and exposes
 * mutations for manual robot commands and the emergency stop-all. All are farm
 * scoped via the same auto-resolving farm helper used by the analytics hooks.
 *
 * @see /api/v1/robots — backend router (cloud/services/api_gateway/app/routers/robots.py)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { Robot, HerdingJob, HerdingStatus } from '@/types';

// ─── Farm ID Resolution ──────────────────────────────────────────────────────

/**
 * Returns the active farm ID — from the auth store or auto-fetched (first farm).
 * Mirrors the helper in useAnalytics so robot data works without an explicit
 * farm selection.
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
    let cancelled = false;
    async function autoSelect() {
      try {
        const resp = await apiClient.get('/api/farms');
        if (!cancelled && resp.data?.length > 0) {
          setResolvedFarmId(resp.data[0].id);
          switchFarm(resp.data[0].id);
        }
      } catch {
        try {
          const resp = await apiClient.get('/api/v1/assignments/me/farms');
          if (!cancelled && resp.data?.length > 0) {
            setResolvedFarmId(resp.data[0].farm_id);
            switchFarm(resp.data[0].farm_id);
          }
        } catch {
          /* no farms available */
        }
      }
    }
    autoSelect();
    return () => { cancelled = true; };
  }, [storeFarmId, switchFarm]);

  return resolvedFarmId;
}

// ─── Command types ───────────────────────────────────────────────────────────

export type RobotCommandName = 'move_to' | 'return_home' | 'stop' | 'patrol' | 'shepherd';

export interface RobotCommand {
  command: RobotCommandName;
  latitude?: number;
  longitude?: number;
}

// ─── Queries ─────────────────────────────────────────────────────────────────

/** The full robot fleet for the active farm. Polls as a fallback to the WS feed. */
export function useRobots() {
  const farmId = useActiveFarmId();
  return useQuery<Robot[]>({
    queryKey: ['robots', 'fleet', farmId],
    queryFn: async () => {
      const resp = await apiClient.get('/api/v1/robots', { params: { farm_id: farmId } });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/** Active + recent herding jobs for the active farm. */
export function useHerdingJobs(status?: string) {
  const farmId = useActiveFarmId();
  return useQuery<HerdingJob[]>({
    queryKey: ['robots', 'jobs', farmId, status],
    queryFn: async () => {
      const params: Record<string, string> = { farm_id: farmId! };
      if (status) params.status = status;
      const resp = await apiClient.get('/api/v1/robots/herding/jobs', { params });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

/** Containment summary (fleet + active jobs) for the active farm. */
export function useHerdingStatus() {
  const farmId = useActiveFarmId();
  return useQuery<HerdingStatus>({
    queryKey: ['robots', 'status', farmId],
    queryFn: async () => {
      const resp = await apiClient.get('/api/v1/robots/herding/status', {
        params: { farm_id: farmId },
      });
      return resp.data;
    },
    enabled: !!farmId,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

/** Issue a manual override command to one robot (by serial). */
export function useRobotCommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ serial, command }: { serial: string; command: RobotCommand }) => {
      const resp = await apiClient.post(`/api/v1/robots/${serial}/command`, command);
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robots'] });
    },
  });
}

/** Emergency stop: halt the whole fleet on the active farm. */
export function useStopAll() {
  const queryClient = useQueryClient();
  const farmId = useActiveFarmId();
  return useMutation({
    mutationFn: async () => {
      const resp = await apiClient.post('/api/v1/robots/herding/stop-all', null, {
        params: { farm_id: farmId },
      });
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robots'] });
    },
  });
}
