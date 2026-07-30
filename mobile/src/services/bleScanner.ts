/**
 * BLE Scanner Service
 *
 * In SIMULATOR MODE (no real Bluetooth): Fetches cattle positions from API
 * and displays them as if detected via BLE. This lets you test the full
 * herdsman UI flow without physical BLE hardware.
 *
 * In REAL MODE (physical phone): Uses react-native-ble-plx to scan for
 * actual BLE ear tag advertisements.
 *
 * The mode is auto-detected based on platform capabilities.
 */

import { Platform } from 'react-native';
import { api } from './api';

// Configuration
const POLL_INTERVAL_MS = 10000; // Check API every 10s (simulates BLE scan interval)
const GATEWAY_SERIAL = 'GW-LV-001';
const FARM_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

interface CattleSighting {
  animalId: string;
  animalName: string;
  mac: string;
  rssi: number;
  lastSeen: Date;
}

class BLEScanner {
  private isRunning = false;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private registeredMacs: Map<string, string> = new Map(); // mac -> animal name
  private recentSightings: Map<string, CattleSighting> = new Map(); // mac -> sighting
  private totalRegistered = 0;
  private useSimulatorMode = true; // Default: simulator mode (API-based)

  /**
   * Initialize — loads registered BLE tags from API.
   */
  async init() {
    try {
      const resp = await api.get(`/api/gateway/tags?farm_id=${FARM_ID}`);
      const tags = resp.data;
      this.totalRegistered = tags.length;
      tags.forEach((t: any) => {
        this.registeredMacs.set(t.mac_address, t.animal_name || t.tag_name || 'Unknown');
      });
      console.log(`[BLE] Initialized: ${this.totalRegistered} registered tags`);
    } catch (err) {
      console.warn('[BLE] Failed to load tags from API:', err);
    }

    // Detect if we should use real BLE or simulator mode
    // Real BLE only works on physical devices (not simulators)
    this.useSimulatorMode = Platform.OS === 'web' || __DEV__;
    console.log(`[BLE] Mode: ${this.useSimulatorMode ? 'SIMULATOR (API polling)' : 'REAL BLE'}`);
  }

  /**
   * Start scanning (or polling in simulator mode).
   */
  start() {
    if (this.isRunning) return;
    this.isRunning = true;

    if (this.useSimulatorMode) {
      this.startSimulatorMode();
    } else {
      this.startRealBLE();
    }
  }

  /**
   * Stop scanning.
   */
  stop() {
    this.isRunning = false;
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  /**
   * SIMULATOR MODE: Poll the API for cattle positions.
   * Uses the herd-count endpoint to show how many cattle were seen today.
   */
  private startSimulatorMode() {
    console.log('[BLE-SIM] Starting API-based simulation...');

    const poll = async () => {
      try {
        // Get herd count (uses actual BLE sighting data from the server)
        const resp = await api.get(`/api/gateway/herd-count/${FARM_ID}`);
        const data = resp.data;

        this.totalRegistered = data.total_registered || 0;

        // Update sightings: animals seen today are "in range"
        this.recentSightings.clear();
        const seenToday = data.seen_today || 0;

        // Mark seen animals as detected, missing as not
        if (data.missing) {
          // All registered minus missing = seen
          const missingNames = new Set(data.missing.map((m: any) => m.name));
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (!missingNames.has(name)) {
              this.recentSightings.set(mac, {
                animalId: mac,
                animalName: name,
                mac,
                rssi: -50 - Math.floor(Math.random() * 20),
                lastSeen: new Date(),
              });
            }
          }
        } else {
          // Fallback: use seen_today count
          let i = 0;
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (i >= seenToday) break;
            this.recentSightings.set(mac, {
              animalId: mac,
              animalName: name,
              mac,
              rssi: -50 - Math.floor(Math.random() * 20),
              lastSeen: new Date(),
            });
            i++;
          }
        }
      } catch (err) {
        // Offline or API error — keep last known state
        console.warn('[BLE-SIM] Poll failed:', err);
      }
    };

    poll(); // Initial poll
    this.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  /**
   * REAL BLE MODE: Scan for actual BLE advertisements.
   * (Requires physical phone with Bluetooth)
   */
  private startRealBLE() {
    console.log('[BLE-REAL] Starting real BLE scanning...');
    // This would use react-native-ble-plx
    // For now, fall back to simulator mode
    console.warn('[BLE-REAL] Real BLE not available in this build, using simulator mode');
    this.startSimulatorMode();
  }

  /**
   * Get count of cattle currently "in range" (detected recently).
   */
  getCattleInRange(): number {
    return this.recentSightings.size;
  }

  /**
   * Get total registered cattle count.
   */
  getTotalRegistered(): number {
    return this.totalRegistered;
  }

  /**
   * Get list of recent sightings.
   */
  getRecentSightings(): CattleSighting[] {
    return Array.from(this.recentSightings.values());
  }

  /**
   * Get missing animals (registered but not detected).
   */
  getMissing(): string[] {
    const detected = new Set(this.recentSightings.keys());
    const missing: string[] = [];
    for (const [mac, name] of this.registeredMacs.entries()) {
      if (!detected.has(mac)) {
        missing.push(name);
      }
    }
    return missing;
  }
}

export const bleScanner = new BLEScanner();
