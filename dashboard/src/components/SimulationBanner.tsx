/**
 * SimulationBanner
 *
 * A slim global banner shown only in "simulation mode" — i.e. when the Vite
 * dev-server simulator control plane (GET /dev/simulator/status) is reachable.
 * In production builds those endpoints don't exist, so this renders nothing.
 *
 * It surfaces the per-farm simulation preflight (from
 * GET /api/v1/system/simulation-status): which farms have data flowing today
 * and which are stale ("nothing being detected"). When a farm is stale it's
 * almost always because a simulator isn't running, so the banner offers a
 * one-click "Restart everything" that stops and re-spawns the loop simulators
 * on the host via POST /dev/simulator/restart.
 */

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useSimulationHealth, type SimulationFarmHealth } from '@/hooks/useSimulationHealth';
import { useToastStore } from '@/stores/toastStore';

/** Probe the dev-only simulator control plane. Resolves false in production. */
async function probeSimMode(): Promise<boolean> {
  try {
    const resp = await fetch('/dev/simulator/status');
    return resp.ok;
  } catch {
    return false;
  }
}

function FarmChip({ farm }: { farm: SimulationFarmHealth }) {
  const ok = !farm.stale;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
        ok
          ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
      }`}
      title={
        ok
          ? `${farm.animals_today} animals seen today, ${farm.sightings_today} sightings`
          : 'No sightings today — simulator likely stopped'
      }
    >
      <span
        className={`w-2 h-2 rounded-full ${ok ? 'bg-green-500 animate-pulse' : 'bg-amber-500'}`}
      />
      {farm.farm_name}
      <span className="opacity-70">
        {ok ? `${farm.animals_today}/${farm.registered_tags}` : 'idle'}
      </span>
    </span>
  );
}

export default function SimulationBanner() {
  const [simMode, setSimMode] = useState<boolean | null>(null);
  const [restarting, setRestarting] = useState(false);
  const addToast = useToastStore((s) => s.addToast);

  // Detect simulation mode (dev control plane reachable), then keep checking.
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const on = await probeSimMode();
      if (!cancelled) setSimMode(on);
    };
    check();
    const id = setInterval(check, 15_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const { data, refetch } = useSimulationHealth(simMode === true);

  // Hidden entirely outside simulation mode (e.g. production).
  if (simMode !== true) return null;

  const anyStale = (data?.stale_farm_count ?? 0) > 0;
  const overall = data?.overall ?? 'idle';

  const headline =
    overall === 'healthy'
      ? 'Simulation running — all farms reporting'
      : overall === 'partial'
        ? 'Simulation partially idle — some farms have no data today'
        : overall === 'idle'
          ? 'Simulation idle — no farm is reporting data today'
          : 'Simulation mode';

  const restartEverything = async () => {
    if (restarting) return;
    setRestarting(true);
    addToast({
      title: 'Restarting simulators',
      message: 'Stopping and re-launching the farm simulators…',
      severity: 'info',
      duration: 4000,
    });
    try {
      const resp = await fetch('/dev/simulator/restart', { method: 'POST' });
      const body = await resp.json().catch(() => ({}));
      if (resp.ok && body.status === 'restarted') {
        addToast({
          title: 'Simulators restarted',
          message: `Loch Vaal and Sibanyoni simulators are running${
            body.using_venv === false ? ' (host python3)' : ''
          }. Data should resume shortly.`,
          severity: 'success',
          duration: 6000,
        });
        // Give the sims a moment to emit their first batch, then refresh.
        setTimeout(() => refetch(), 5000);
      } else if (body.status === 'failed') {
        // The control plane was reached but the sims failed to launch
        // (e.g. missing Python deps). Surface the real reason.
        addToast({
          title: 'Simulators failed to start',
          message:
            body.error ||
            'The simulators exited on launch. Run `make setup` to build the simulator venv, then try again.',
          severity: 'high',
          duration: 10000,
        });
        // eslint-disable-next-line no-console
        console.error('Simulator restart failed:', body.error);
      } else {
        throw new Error(body.error || 'Restart failed');
      }
    } catch (err) {
      addToast({
        title: 'Restart unavailable',
        message:
          'Could not reach the dev simulator control. Run `make simulate-loop` in a terminal instead.',
        severity: 'high',
        duration: 8000,
      });
      // eslint-disable-next-line no-console
      console.error('Simulator restart failed:', err);
    } finally {
      setRestarting(false);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: 'auto', opacity: 1 }}
        exit={{ height: 0, opacity: 0 }}
        className={`w-full border-b ${
          anyStale
            ? 'bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900'
            : 'bg-brand-50 border-brand-200 dark:bg-gray-800 dark:border-gray-700'
        }`}
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center justify-between gap-3 px-4 py-2 flex-wrap">
          <div className="flex items-center gap-3 min-w-0 flex-wrap">
            <span className="text-base flex-shrink-0" aria-hidden>
              {anyStale ? '⚠️' : '🧪'}
            </span>
            <span className="text-sm font-medium text-gray-800 dark:text-gray-100">
              {headline}
            </span>
            <div className="flex items-center gap-2 flex-wrap">
              {data?.farms.map((f) => (
                <FarmChip key={f.farm_id} farm={f} />
              ))}
            </div>
          </div>

          <button
            onClick={restartEverything}
            disabled={restarting}
            className={`flex-shrink-0 inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              restarting
                ? 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400 cursor-not-allowed'
                : anyStale
                  ? 'bg-amber-600 text-white hover:bg-amber-700'
                  : 'bg-brand-600 text-white hover:bg-brand-700'
            }`}
            title="Stop and re-launch all farm simulators"
          >
            <span className={restarting ? 'animate-spin' : ''} aria-hidden>
              🔄
            </span>
            {restarting ? 'Restarting…' : 'Restart everything'}
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
