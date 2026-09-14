/**
 * @file HerdingPanel.tsx
 * @description Floating map panel for the robotic-herdsman layer. Shows the
 * containment summary (how many robots are active/charging, active jobs), the
 * fleet list with per-robot status + battery, and controls: send a robot home,
 * and an emergency STOP ALL that halts every robot on the farm.
 *
 * @see useHerdingStatus / useRobots / useHerdingJobs — data
 * @see useStopAll / useRobotCommand — actions
 */
import { motion } from 'framer-motion';
import { useHerdingStatus, useRobots, useHerdingJobs, useStopAll, useRobotCommand } from '@/hooks/useRobots';
import { useToastStore } from '@/stores/toastStore';
import type { Robot, RobotStatus } from '@/types';

interface HerdingPanelProps {
  onClose: () => void;
}

const STATUS_STYLES: Record<RobotStatus, string> = {
  idle: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  patrolling: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  enroute: 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
  shepherding: 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
  charging: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  fault: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  offline: 'bg-gray-200 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
};

function batteryColor(pct?: number | null): string {
  if (pct == null) return 'text-gray-400';
  if (pct < 20) return 'text-red-500';
  if (pct < 50) return 'text-amber-500';
  return 'text-green-500';
}

export function HerdingPanel({ onClose }: HerdingPanelProps) {
  const { data: status } = useHerdingStatus();
  const { data: fleet } = useRobots();
  const { data: jobs } = useHerdingJobs('active');
  const stopAll = useStopAll();
  const command = useRobotCommand();
  const addToast = useToastStore((s) => s.addToast);

  const handleStopAll = () => {
    stopAll.mutate(undefined, {
      onSuccess: (data) => addToast({
        title: 'Fleet stopped',
        message: `Stop sent to ${data?.robots ?? 0} robot(s).`,
        severity: 'high', duration: 4000,
      }),
      onError: () => addToast({
        title: 'Stop failed', message: 'Could not reach the fleet.', severity: 'critical', duration: 0,
      }),
    });
  };

  const handleReturnHome = (serial: string) => {
    command.mutate({ serial, command: { command: 'return_home' } }, {
      onSuccess: () => addToast({
        title: 'Command sent', message: `${serial} returning to dock.`, severity: 'info', duration: 3000,
      }),
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="absolute top-16 right-3 z-30 w-72 max-h-[calc(100%-5rem)] overflow-y-auto rounded-lg bg-white/95 dark:bg-gray-800/95 backdrop-blur shadow-lg border border-gray-200 dark:border-gray-700"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
          <span>🤖</span> Herding Fleet
        </h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none"
          aria-label="Close herding panel"
        >
          ×
        </button>
      </div>

      {/* Containment summary */}
      <div className="grid grid-cols-3 gap-1 p-3 text-center">
        <div className="rounded-md bg-gray-50 dark:bg-gray-700/50 py-2">
          <div className="text-lg font-bold text-gray-900 dark:text-white">{status?.robots_total ?? '—'}</div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Robots</div>
        </div>
        <div className="rounded-md bg-pink-50 dark:bg-pink-900/20 py-2">
          <div className="text-lg font-bold text-pink-600 dark:text-pink-400">{status?.robots_active ?? '—'}</div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Herding</div>
        </div>
        <div className="rounded-md bg-purple-50 dark:bg-purple-900/20 py-2">
          <div className="text-lg font-bold text-purple-600 dark:text-purple-400">{status?.active_jobs ?? '—'}</div>
          <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Jobs</div>
        </div>
      </div>

      {/* STOP ALL */}
      <div className="px-3 pb-2">
        <button
          onClick={handleStopAll}
          disabled={stopAll.isPending}
          className="w-full rounded-md bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white text-sm font-semibold py-2 transition-colors"
        >
          {stopAll.isPending ? 'Stopping…' : '■ STOP ALL'}
        </button>
      </div>

      {/* Fleet list */}
      <div className="px-3 pb-3 space-y-1.5">
        {(fleet ?? []).length === 0 && (
          <p className="text-xs text-gray-500 dark:text-gray-400 py-2 text-center">
            No robots registered for this farm.
          </p>
        )}
        {(fleet ?? []).map((r: Robot) => (
          <div
            key={r.serial_number}
            className="flex items-center justify-between rounded-md bg-gray-50 dark:bg-gray-700/40 px-2 py-1.5"
          >
            <div className="min-w-0">
              <div className="text-xs font-medium text-gray-900 dark:text-white truncate">
                {r.name} <span className="text-gray-400">· {r.serial_number}</span>
              </div>
              <div className="mt-0.5 flex items-center gap-1.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_STYLES[r.status] ?? STATUS_STYLES.idle}`}>
                  {r.status}
                </span>
                <span className={`text-[10px] font-medium ${batteryColor(r.battery_pct)}`}>
                  {r.battery_pct != null ? `${r.battery_pct}%` : '—'}
                </span>
              </div>
            </div>
            <button
              onClick={() => handleReturnHome(r.serial_number)}
              disabled={command.isPending}
              className="ml-2 shrink-0 text-[10px] px-2 py-1 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50"
              title="Send robot back to its charging dock"
            >
              Home
            </button>
          </div>
        ))}
      </div>

      {/* Active jobs (compact) */}
      {(jobs ?? []).length > 0 && (
        <div className="px-3 pb-3 border-t border-gray-200 dark:border-gray-700 pt-2">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">Active jobs</div>
          {(jobs ?? []).slice(0, 5).map((j) => (
            <div key={j.id} className="text-[11px] text-gray-600 dark:text-gray-300 truncate">
              <span className="text-purple-500">•</span> {j.reason || `${j.job_type} (p${j.priority})`}
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
