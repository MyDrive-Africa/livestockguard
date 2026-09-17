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
import { existsSync } from 'fs';
import path from 'path';
import type { Plugin } from 'vite';

let simulatorProcesses: ChildProcess[] = [];
let isRunning = false;
/** Non-empty when the most recent (re)start failed — surfaced via /status. */
let lastError: string | null = null;
/** True while a deliberate stop is in progress, so exits aren't seen as crashes. */
let stopping = false;

const SIMULATOR_DIR = path.resolve(__dirname, '../tools/simulator');
const VENV_DIR = path.join(SIMULATOR_DIR, '.venv');

/**
 * A simulator that exits within this window is treated as a launch failure
 * (e.g. missing Python deps). Python interpreter startup can be slow (~2s), so
 * the window is generous; the (re)start handlers wait just past it before
 * responding, so a slow import crash is reported rather than a false success.
 */
const CRASH_WINDOW_MS = 3000;
const SPAWN_SETTLE_MS = CRASH_WINDOW_MS + 300;

/**
 * Resolve the Python interpreter for the simulators.
 *
 * Prefer the project's simulator virtualenv (tools/simulator/.venv), created by
 * `make setup` / scripts/setup.sh, because it is guaranteed to have the sim
 * dependencies (click, requests). Fall back to host `python3` only if the venv
 * isn't present — in which case the sims rely on those packages being installed
 * globally, and a missing one will now surface as an error (see spawn handling)
 * instead of a silent exit.
 */
function resolvePythonBin(): { bin: string; usingVenv: boolean } {
  const posixVenv = path.join(VENV_DIR, 'bin', 'python3');
  const windowsVenv = path.join(VENV_DIR, 'Scripts', 'python.exe');
  if (existsSync(posixVenv)) return { bin: posixVenv, usingVenv: true };
  if (existsSync(windowsVenv)) return { bin: windowsVenv, usingVenv: true };
  return { bin: 'python3', usingVenv: false };
}

/** Spawn both farm loop simulators and track them. Returns the spawned procs. */
function spawnLoopSimulators(): ChildProcess[] {
  lastError = null;
  const { bin, usingVenv } = resolvePythonBin();

  const scripts = ['gateway_daily_sim.py', 'sibanyoni_daily_sim.py'];

  const procs: ChildProcess[] = scripts.map((script) => {
    // Capture stderr so an early crash (e.g. missing click/requests) is visible
    // rather than swallowed. stdout is ignored to avoid noisy log spam.
    const proc = spawn(bin, [script, '--speed', '120', '--loop'], {
      cwd: SIMULATOR_DIR,
      stdio: ['ignore', 'ignore', 'pipe'],
      detached: false,
    });

    let stderrTail = '';
    proc.stderr?.on('data', (chunk: Buffer) => {
      // Keep only the last ~2KB — enough to show an import traceback tail.
      stderrTail = (stderrTail + chunk.toString()).slice(-2048);
    });

    // If a sim dies almost immediately, treat it as a startup failure and
    // record the reason (usually a Python import/dependency error).
    const startedAt = Date.now();
    proc.on('exit', (code) => {
      const aliveMs = Date.now() - startedAt;
      if (!stopping && code !== 0 && aliveMs < CRASH_WINDOW_MS) {
        const hint = usingVenv
          ? 'Simulator venv may be broken — re-run `make setup`.'
          : 'No tools/simulator/.venv found and host python3 is missing deps. Run `make setup` (creates the venv with click/requests).';
        lastError = `${script} exited (code ${code}) after ${aliveMs}ms. ${hint}` +
          (stderrTail.trim() ? `\n${stderrTail.trim().split('\n').slice(-3).join('\n')}` : '');
      }
      simulatorProcesses = simulatorProcesses.filter((p) => p !== proc);
      if (simulatorProcesses.length === 0) isRunning = false;
    });

    proc.on('error', (err) => {
      lastError = `Failed to launch ${script} with "${bin}": ${err.message}`;
    });

    return proc;
  });

  simulatorProcesses = procs;
  isRunning = true;
  return procs;
}

/**
 * Write the JSON result of a spawn attempt. If a simulator died on launch
 * (lastError set, e.g. missing Python deps), respond 500 with the reason so the
 * banner shows a real error instead of a false "data will resume".
 */
function respondSpawnResult(
  res: import('http').ServerResponse,
  successStatus: 'started' | 'restarted',
  usingVenv: boolean,
): void {
  const alive = simulatorProcesses.length > 0 && !lastError;
  res.setHeader('Content-Type', 'application/json');
  if (alive) {
    res.statusCode = 200;
    res.end(JSON.stringify({
      status: successStatus,
      using_venv: usingVenv,
      pids: simulatorProcesses.map((p) => p.pid),
      farms: ['Loch Vaal Plot 30', 'Sibanyoni Farm'],
    }));
  } else {
    res.statusCode = 500;
    res.end(JSON.stringify({
      status: 'failed',
      using_venv: usingVenv,
      error: lastError || 'Simulators exited immediately after launch.',
    }));
  }
}

/** SIGTERM all tracked simulator processes and reset state. */
function stopSimulators(): void {
  stopping = true;
  for (const proc of simulatorProcesses) {
    try {
      proc.kill('SIGTERM');
    } catch {
      /* already dead */
    }
  }
  simulatorProcesses = [];
  isRunning = false;
  lastError = null;
  // Clear the guard shortly after — long enough to cover the SIGTERM exits.
  setTimeout(() => {
    stopping = false;
  }, 500);
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
          const { usingVenv } = resolvePythonBin();
          spawnLoopSimulators();
          // Give the sims a moment; if one dies on launch (missing deps),
          // lastError is populated so we can report a real failure.
          setTimeout(() => {
            respondSpawnResult(res, 'started', usingVenv);
          }, SPAWN_SETTLE_MS);
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
          const { usingVenv } = resolvePythonBin();
          stopSimulators();
          // Pause so the OS reaps the old processes before we re-spawn, then a
          // little longer so a launch failure surfaces before we respond.
          setTimeout(() => {
            try {
              spawnLoopSimulators();
              setTimeout(() => {
                respondSpawnResult(res, 'restarted', usingVenv);
              }, SPAWN_SETTLE_MS);
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

        const { usingVenv } = resolvePythonBin();
        res.statusCode = 200;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({
          running: isRunning,
          using_venv: usingVenv,
          error: lastError,
          processes: simulatorProcesses.map(p => ({ pid: p.pid, killed: p.killed })),
        }));
      });
    },
  };
}
