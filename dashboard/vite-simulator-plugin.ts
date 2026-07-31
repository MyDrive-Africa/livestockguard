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
          // Start Loch Vaal simulator (loop mode)
          const lochvaal = spawn('python3', ['gateway_daily_sim.py', '--speed', '120', '--loop'], {
            cwd: SIMULATOR_DIR,
            stdio: 'ignore',
            detached: false,
          });

          // Start Sibanyoni simulator (loop mode)
          const sibanyoni = spawn('python3', ['sibanyoni_daily_sim.py', '--speed', '120', '--loop'], {
            cwd: SIMULATOR_DIR,
            stdio: 'ignore',
            detached: false,
          });

          simulatorProcesses = [lochvaal, sibanyoni];
          isRunning = true;

          // Auto-cleanup if processes exit
          for (const proc of simulatorProcesses) {
            proc.on('exit', () => {
              simulatorProcesses = simulatorProcesses.filter(p => p !== proc);
              if (simulatorProcesses.length === 0) isRunning = false;
            });
          }

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

      // POST /dev/simulator/stop — kill running simulators
      server.middlewares.use('/dev/simulator/stop', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        for (const proc of simulatorProcesses) {
          try { proc.kill('SIGTERM'); } catch { /* already dead */ }
        }
        simulatorProcesses = [];
        isRunning = false;

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
