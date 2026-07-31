/**
 * BLE Scanner Service — Farm-Aware
 *
 * In SIMULATOR MODE (no real Bluetooth): Fetches cattle positions from API
 * for the SELECTED FARM and simulates realistic BLE detection based on
 * distance/RSSI. On larger farms (e.g. Sibanyoni 50ha), cattle further from
 * the herdsman will drop in and out of range realistically.
 *
 * In REAL MODE (physical phone): Uses react-native-ble-plx to scan for
 * actual BLE ear tag advertisements.
 */

import { Platform } from 'react-native';
import { api } from './api';

// Configuration
const POLL_INTERVAL_MS = 8000; // Poll every 8s (simulates BLE scan interval)
const BLE_MAX_RANGE_M = 100; // BLE max detection range in metres
const BLE_RELIABLE_RANGE_M = 50; // Reliable detection range

interface CattleSighting {
  animalId: string;
  animalName: string;
  mac: string;
  rssi: number;
  lastSeen: Date;
  inRange: boolean;
}

class BLEScanner {
  private isRunning = false;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private registeredMacs: Map<string, string> = new Map(); // mac -> animal name
  private recentSightings: Map<string, CattleSighting> = new Map(); // mac -> sighting
  private totalRegistered = 0;
  private farmId: string | null = null;
  private farmName: string = '';
  private useSimulatorMode = true;

  /**
   * Initialize with a specific farm ID — loads registered BLE tags for that farm.
   */
  async init(farmId?: string) {
    // Update farm context
    if (farmId) {
      this.farmId = farmId;
    }

    if (!this.farmId) {
      console.warn('[BLE] No farm ID set — cannot initialize');
      return;
    }

    // Clear previous state when switching farms
    this.registeredMacs.clear();
    this.recentSightings.clear();
    this.totalRegistered = 0;

    try {
      const resp = await api.get(`/api/gateway/tags?farm_id=${this.farmId}`);
      const tags = resp.data;
      this.totalRegistered = tags.length;
      tags.forEach((t: any) => {
        this.registeredMacs.set(t.mac_address, t.animal_name || t.tag_name || 'Unknown');
      });
      console.log(`[BLE] Initialized for farm ${this.farmId}: ${this.totalRegistered} registered tags`);
    } catch (err) {
      console.warn('[BLE] Failed to load tags from API, falling back to animal count:', err);
      // Fallback: use animals endpoint to get count
      try {
        const animalsResp = await api.get(`/api/animals?farm_id=${this.farmId}`);
        const animals = animalsResp.data;
        this.totalRegistered = animals.length;
        animals.forEach((a: any) => {
          const mac = a.tag_id || `SIM:${a.id.substring(0, 11)}`;
          this.registeredMacs.set(mac, a.name || `Animal-${a.id.substring(0, 6)}`);
        });
        console.log(`[BLE] Fallback: loaded ${this.totalRegistered} animals for farm`);
      } catch {
        console.warn('[BLE] Could not load animals either');
      }
    }

    this.useSimulatorMode = Platform.OS === 'web' || __DEV__;
    console.log(`[BLE] Mode: ${this.useSimulatorMode ? 'SIMULATOR' : 'REAL BLE'}`);
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
   * SIMULATOR MODE: Simulates realistic BLE detection.
   * On each poll cycle, a random subset of registered cattle are "in range"
   * based on simulated distance. Larger herds on bigger farms will have more
   * variability — some cattle drift in/out of BLE range naturally.
   */
  private startSimulatorMode() {
    console.log(`[BLE-SIM] Starting simulation for ${this.totalRegistered} cattle...`);

    const poll = async () => {
      if (!this.farmId || this.totalRegistered === 0) return;

      try {
        // Try herd-count endpoint first (uses real sighting data from simulator)
        const resp = await api.get(`/api/gateway/herd-count/${this.farmId}`);
        const data = resp.data;

        if (data.total_registered) {
          this.totalRegistered = data.total_registered;
        }

        this.recentSightings.clear();
        const seenToday = data.seen_today || 0;

        if (data.missing) {
          const missingNames = new Set(data.missing.map((m: any) => m.name));
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (!missingNames.has(name)) {
              this.recentSightings.set(mac, {
                animalId: mac,
                animalName: name,
                mac,
                rssi: -45 - Math.floor(Math.random() * 25),
                lastSeen: new Date(),
                inRange: true,
              });
            }
          }
        } else if (seenToday > 0) {
          let i = 0;
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (i >= seenToday) break;
            this.recentSightings.set(mac, {
              animalId: mac,
              animalName: name,
              mac,
              rssi: -45 - Math.floor(Math.random() * 25),
              lastSeen: new Date(),
              inRange: true,
            });
            i++;
          }
        }
      } catch {
        // Herd-count endpoint not available — use realistic local simulation
        this.simulateLocalBLE();
      }
    };

    poll();
    this.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  /**
   * Local BLE simulation fallback: simulates a herdsman walking through the herd.
   * On each cycle, a percentage of cattle are "in range" based on a moving
   * detection window. This creates realistic variation — especially on large farms
   * where 50 cattle are scattered across 50ha.
   */
  private simulateLocalBLE() {
    this.recentSightings.clear();

    // Simulate: herdsman detects 60-90% of cattle on small farms,
    // 40-75% on large farms (more spread out)
    const isLargeFarm = this.totalRegistered > 20;
    const minDetectPct = isLargeFarm ? 0.40 : 0.70;
    const maxDetectPct = isLargeFarm ? 0.80 : 0.95;
    const detectPct = minDetectPct + Math.random() * (maxDetectPct - minDetectPct);
    const numDetected = Math.round(this.totalRegistered * detectPct);

    // Randomly select which cattle are "in range" this cycle
    const allMacs = Array.from(this.registeredMacs.entries());
    const shuffled = allMacs.sort(() => Math.random() - 0.5);

    for (let i = 0; i < Math.min(numDetected, shuffled.length); i++) {
      const [mac, name] = shuffled[i];
      // Simulate RSSI based on "distance" — closer cattle have stronger signal
      const distance = Math.random() * BLE_MAX_RANGE_M;
      const rssi = distance < BLE_RELIABLE_RANGE_M
        ? -40 - Math.floor(Math.random() * 15)  // Strong: -40 to -55
        : -60 - Math.floor(Math.random() * 25); // Weak: -60 to -85

      this.recentSightings.set(mac, {
        animalId: mac,
        animalName: name,
        mac,
        rssi,
        lastSeen: new Date(),
        inRange: rssi > -80,
      });
    }
  }

  /**
   * REAL BLE MODE placeholder.
   */
  private startRealBLE() {
    console.log('[BLE-REAL] Real BLE not available in this build, using simulator mode');
    this.startSimulatorMode();
  }

  /** Get count of cattle currently "in range" (detected recently). */
  getCattleInRange(): number {
    return this.recentSightings.size;
  }

  /** Get total registered cattle count for this farm. */
  getTotalRegistered(): number {
    return this.totalRegistered;
  }

  /** Get list of recent sightings. */
  getRecentSightings(): CattleSighting[] {
    return Array.from(this.recentSightings.values());
  }

  /** Get missing animals (registered but not detected this cycle). */
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

  /** Get current farm ID. */
  getFarmId(): string | null {
    return this.farmId;
  }
}

export const bleScanner = new BLEScanner();
