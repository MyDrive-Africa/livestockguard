/**
 * Vite Dev Server Plugin — Simulator Control
 *
 * Adds local-only endpoints to start/stop/status the BLE simulators
 * directly from the dashboard UI during development.
 *
 * SAFETY:
 * - Only active during `vite dev` (not in production builds)
 * - Only executes hardcoded simulator scripts (no user input to shell)
 * - Binds to localhost only (Vite default)
 * - Processes are killed cleanly on stop
 */

import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import type { Plugin } from 'vite';

let simulatorProcesses: ChildProcess[] = [];
let isRunning = false;

const SIMULATOR_DIR = path.resolve(__dirname, '../tools/simulator');

/** Spawn both farm loop simulators and track them. Returns the spawned procs. */
function spawnLoopSimulators(): ChildProcess[] {
  // Loch Vaal (BLE gateway, loop mode)
  const lochvaal = spawn('python3', ['gateway_daily_sim.py', '--speed', '120', '--loop'], {
    cwd: SIMULATOR_DIR,
    stdio: 'ignore',
    detached: false,
  });

  // Sibanyoni (50-cattle BLE gateway, loop mode)
  const sibanyoni = spawn('python3', ['sibanyoni_daily_sim.py', '--speed', '120', '--loop'], {
    cwd: SIMULATOR_DIR,
    stdio: 'ignore',
    detached: false,
  });

  simulatorProcesses = [lochvaal, sibanyoni];
  isRunning = true;

  // Auto-cleanup if processes exit on their own
  for (const proc of simulatorProcesses) {
    proc.on('exit', () => {
      simulatorProcesses = simulatorProcesses.filter((p) => p !== proc);
      if (simulatorProcesses.length === 0) isRunning = false;
    });
  }

  return simulatorProcesses;
}

/** SIGTERM all tracked simulator processes and reset state. */
function stopSimulators(): void {
  for (const proc of simulatorProcesses) {
    try {
      proc.kill('SIGTERM');
    } catch {
      /* already dead */
    }
  }
  simulatorProcesses = [];
  isRunning = false;
}

export function simulatorControlPlugin(): Plugin {
  return {
    name: 'simulator-control',
    configureServer(server) {
      // POST /dev/simulator/start — start loop simulators
      server.middlewares.use('/dev/simulator/start', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        if (isRunning) {
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ status: 'already_running', pids: simulatorProcesses.map(p => p.pid) }));
          return;
        }

        try {
          spawnLoopSimulators();

          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({
            status: 'started',
            pids: simulatorProcesses.map(p => p.pid),
            farms: ['Loch Vaal Plot 30', 'Sibanyoni Farm'],
          }));
        } catch (err: any) {
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: err.message }));
        }
      });

      // POST /dev/simulator/restart — stop any running sims, then start fresh.
      // This is the banner's "restart everything" action: it guarantees both
      // farm simulators are running from a clean slate so data starts flowing
      // again. Commands are hardcoded (no user input) and dev/localhost-only.
      server.middlewares.use('/dev/simulator/restart', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        try {
          stopSimulators();
          // Brief pause so the OS reaps the old processes before we re-spawn.
          setTimeout(() => {
            try {
              spawnLoopSimulators();
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({
                status: 'restarted',
                pids: simulatorProcesses.map(p => p.pid),
                farms: ['Loch Vaal Plot 30', 'Sibanyoni Farm'],
              }));
            } catch (err: any) {
              res.statusCode = 500;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: err.message }));
            }
          }, 800);
        } catch (err: any) {
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: err.message }));
        }
      });

      // POST /dev/simulator/stop — kill running simulators
      server.middlewares.use('/dev/simulator/stop', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        stopSimulators();

        res.statusCode = 200;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ status: 'stopped' }));
      });

      // GET /dev/simulator/status — check if running
      server.middlewares.use('/dev/simulator/status', (req, res) => {
        if (req.method !== 'GET') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        res.statusCode = 200;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({
          running: isRunning,
          processes: simulatorProcesses.map(p => ({ pid: p.pid, killed: p.killed })),
        }));
      });
    },
  };
}
