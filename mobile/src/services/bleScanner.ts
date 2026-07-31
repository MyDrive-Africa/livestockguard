/**
 * BLE Scanner Service — Farm-Aware with Cumulative Daily Tracking
 *
 * Tracks two counts:
 * 1. IN RANGE (now): cattle within BLE range this instant
 * 2. SEEN TODAY (cumulative): unique tags detected at any point since shift start
 *
 * The "seen today" set only grows during a shift. Each unique MAC detected in any
 * batch gets added once. This gives accurate daily coverage even on large farms
 * where cattle are scattered — the herdsman walks through different areas and the
 * cumulative count climbs toward 100%.
 *
 * Shift lifecycle:
 * - Shift starts when herdsman begins patrol (or auto-resets at configured time)
 * - Shift ends at kraal return (evening verification)
 * - Seen today persists in AsyncStorage (survives app restart during shift)
 */

import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from './api';

// Configuration
const POLL_INTERVAL_MS = 8000;
const BLE_MAX_RANGE_M = 100;
const BLE_RELIABLE_RANGE_M = 50;
const STORAGE_KEY_SEEN_TODAY = 'ble_seen_today';
const STORAGE_KEY_SHIFT = 'ble_shift_state';

interface CattleSighting {
  animalId: string;
  animalName: string;
  mac: string;
  rssi: number;
  lastSeen: Date;
  inRange: boolean;
}

interface TagRecord {
  mac: string;
  name: string;
  firstSeenAt: Date;
  lastSeenAt: Date;
  seenCount: number;
}

interface ShiftState {
  farmId: string;
  startedAt: string; // ISO timestamp
  departureCount: number; // count at shift start (kraal)
  mode: 'patrol' | 'kraal';
}

class BLEScanner {
  private isRunning = false;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private registeredMacs: Map<string, string> = new Map(); // mac -> animal name
  private recentSightings: Map<string, CattleSighting> = new Map(); // mac -> current sighting
  private seenToday: Map<string, TagRecord> = new Map(); // mac -> cumulative record
  private totalRegistered = 0;
  private farmId: string | null = null;
  private shiftState: ShiftState | null = null;
  private useSimulatorMode = true;

  /**
   * Initialize with a specific farm ID — loads registered BLE tags for that farm.
   * Also restores any persisted "seen today" state from AsyncStorage.
   */
  async init(farmId?: string) {
    if (farmId) {
      // If farm changed, reset everything
      if (this.farmId && this.farmId !== farmId) {
        this.seenToday.clear();
        this.recentSightings.clear();
      }
      this.farmId = farmId;
    }

    if (!this.farmId) {
      console.warn('[BLE] No farm ID set — cannot initialize');
      return;
    }

    this.registeredMacs.clear();
    this.recentSightings.clear();
    this.totalRegistered = 0;

    // Load registered tags
    try {
      const resp = await api.get(`/api/gateway/tags?farm_id=${this.farmId}`);
      const tags = resp.data;
      this.totalRegistered = tags.length;
      tags.forEach((t: any) => {
        this.registeredMacs.set(t.mac_address, t.animal_name || t.tag_name || 'Unknown');
      });
      console.log(`[BLE] Initialized for farm ${this.farmId}: ${this.totalRegistered} registered tags`);
    } catch {
      // Fallback: use animals endpoint
      try {
        const animalsResp = await api.get(`/api/animals?farm_id=${this.farmId}`);
        const animals = animalsResp.data;
        this.totalRegistered = animals.length;
        animals.forEach((a: any) => {
          const mac = a.tag_id || `SIM:${a.id.substring(0, 11)}`;
          this.registeredMacs.set(mac, a.name || `Animal-${a.id.substring(0, 6)}`);
        });
        console.log(`[BLE] Fallback: loaded ${this.totalRegistered} animals`);
      } catch {
        console.warn('[BLE] Could not load animals');
      }
    }

    // Restore persisted shift state
    await this.restoreState();

    this.useSimulatorMode = Platform.OS === 'web' || __DEV__;
  }

  /**
   * Start a new shift (patrol begins). Resets the "seen today" set.
   * Called when herdsman starts their day or leaves the kraal.
   */
  async startShift() {
    this.seenToday.clear();
    this.shiftState = {
      farmId: this.farmId || '',
      startedAt: new Date().toISOString(),
      departureCount: this.recentSightings.size, // snapshot current count as departure baseline
      mode: 'patrol',
    };

    // If we can see cattle right now (kraal), add them all to seen today
    for (const [mac, sighting] of this.recentSightings.entries()) {
      const name = this.registeredMacs.get(mac) || sighting.animalName;
      this.seenToday.set(mac, {
        mac,
        name,
        firstSeenAt: new Date(),
        lastSeenAt: new Date(),
        seenCount: 1,
      });
    }

    await this.persistState();
    console.log(`[BLE] Shift started: ${this.seenToday.size} cattle at departure`);
  }

  /**
   * End the shift (return to kraal). Switches to kraal verification mode.
   */
  async endShift() {
    if (this.shiftState) {
      this.shiftState.mode = 'kraal';
      await this.persistState();
    }
    console.log(`[BLE] Shift ended: ${this.seenToday.size}/${this.totalRegistered} seen today, ${this.recentSightings.size} in kraal now`);
  }

  /**
   * Start scanning.
   */
  start() {
    if (this.isRunning) return;
    this.isRunning = true;

    if (this.useSimulatorMode) {
      this.startSimulatorMode();
    } else {
      this.startSimulatorMode(); // Fallback until real BLE is wired
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
   * SIMULATOR MODE: Simulates BLE detection + updates cumulative "seen today".
   */
  private startSimulatorMode() {
    const poll = async () => {
      if (!this.farmId || this.totalRegistered === 0) return;

      try {
        const resp = await api.get(`/api/gateway/herd-count/${this.farmId}`);
        const data = resp.data;

        if (data.total_registered) {
          this.totalRegistered = data.total_registered;
        }

        this.recentSightings.clear();

        if (data.missing) {
          const missingNames = new Set(data.missing.map((m: any) => m.name));
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (!missingNames.has(name)) {
              const rssi = -45 - Math.floor(Math.random() * 25);
              this.recentSightings.set(mac, {
                animalId: mac, animalName: name, mac, rssi, lastSeen: new Date(), inRange: true,
              });
              this.addToSeenToday(mac, name);
            }
          }
        } else {
          // Use seen_today from API if available
          const seenCount = data.seen_today || 0;
          let i = 0;
          for (const [mac, name] of this.registeredMacs.entries()) {
            if (i >= seenCount) break;
            const rssi = -45 - Math.floor(Math.random() * 25);
            this.recentSightings.set(mac, {
              animalId: mac, animalName: name, mac, rssi, lastSeen: new Date(), inRange: true,
            });
            this.addToSeenToday(mac, name);
            i++;
          }
        }
      } catch {
        // Fallback: local simulation
        this.simulateLocalBLE();
      }

      // Persist cumulative state periodically
      await this.persistState();
    };

    poll();
    this.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  /**
   * Local BLE simulation with cumulative tracking.
   */
  private simulateLocalBLE() {
    this.recentSightings.clear();

    const isLargeFarm = this.totalRegistered > 20;
    const minDetectPct = isLargeFarm ? 0.40 : 0.70;
    const maxDetectPct = isLargeFarm ? 0.80 : 0.95;
    const detectPct = minDetectPct + Math.random() * (maxDetectPct - minDetectPct);
    const numDetected = Math.round(this.totalRegistered * detectPct);

    const allMacs = Array.from(this.registeredMacs.entries());
    const shuffled = allMacs.sort(() => Math.random() - 0.5);

    for (let i = 0; i < Math.min(numDetected, shuffled.length); i++) {
      const [mac, name] = shuffled[i];
      const distance = Math.random() * BLE_MAX_RANGE_M;
      const rssi = distance < BLE_RELIABLE_RANGE_M
        ? -40 - Math.floor(Math.random() * 15)
        : -60 - Math.floor(Math.random() * 25);

      this.recentSightings.set(mac, {
        animalId: mac, animalName: name, mac, rssi, lastSeen: new Date(), inRange: rssi > -80,
      });

      // Add to cumulative "seen today"
      this.addToSeenToday(mac, name);
    }
  }

  /**
   * Add a MAC to the "seen today" cumulative set.
   * Only records first seen time once; updates last seen and count on each detection.
   */
  private addToSeenToday(mac: string, name: string) {
    if (!this.shiftState) return; // Only track during active shift

    const existing = this.seenToday.get(mac);
    if (existing) {
      existing.lastSeenAt = new Date();
      existing.seenCount += 1;
    } else {
      this.seenToday.set(mac, {
        mac,
        name,
        firstSeenAt: new Date(),
        lastSeenAt: new Date(),
        seenCount: 1,
      });
    }
  }

  // ─── Persistence ──────────────────────────────────────────────────────

  private async persistState() {
    try {
      const seenData = Array.from(this.seenToday.entries()).map(([mac, record]) => ({
        mac,
        name: record.name,
        firstSeenAt: record.firstSeenAt.toISOString(),
        lastSeenAt: record.lastSeenAt.toISOString(),
        seenCount: record.seenCount,
      }));
      await AsyncStorage.setItem(STORAGE_KEY_SEEN_TODAY, JSON.stringify(seenData));

      if (this.shiftState) {
        await AsyncStorage.setItem(STORAGE_KEY_SHIFT, JSON.stringify(this.shiftState));
      }
    } catch {
      // Silent fail — non-critical
    }
  }

  private async restoreState() {
    try {
      // Restore shift state
      const shiftJson = await AsyncStorage.getItem(STORAGE_KEY_SHIFT);
      if (shiftJson) {
        const shift = JSON.parse(shiftJson) as ShiftState;
        // Only restore if same farm and shift started today
        const shiftDate = new Date(shift.startedAt).toDateString();
        const today = new Date().toDateString();
        if (shift.farmId === this.farmId && shiftDate === today) {
          this.shiftState = shift;

          // Restore seen today
          const seenJson = await AsyncStorage.getItem(STORAGE_KEY_SEEN_TODAY);
          if (seenJson) {
            const records = JSON.parse(seenJson) as any[];
            this.seenToday.clear();
            for (const r of records) {
              this.seenToday.set(r.mac, {
                mac: r.mac,
                name: r.name,
                firstSeenAt: new Date(r.firstSeenAt),
                lastSeenAt: new Date(r.lastSeenAt),
                seenCount: r.seenCount,
              });
            }
            console.log(`[BLE] Restored shift: ${this.seenToday.size} seen today`);
          }
        } else {
          // Different day or farm — don't restore
          this.shiftState = null;
          this.seenToday.clear();
        }
      }
    } catch {
      // Fresh start
    }
  }

  // ─── Public API ────────────────────────────────────────────────────────

  /** Cattle within BLE range right now. */
  getCattleInRange(): number {
    return this.recentSightings.size;
  }

  /** Total registered cattle for this farm. */
  getTotalRegistered(): number {
    return this.totalRegistered;
  }

  /** Cumulative unique tags seen since shift start. */
  getSeenTodayCount(): number {
    return this.seenToday.size;
  }

  /** List of tags seen today with timestamps. */
  getSeenTodayRecords(): TagRecord[] {
    return Array.from(this.seenToday.values());
  }

  /** Tags registered but NOT seen at all today — the concern list. */
  getNotSeenToday(): string[] {
    const seen = new Set(this.seenToday.keys());
    const notSeen: string[] = [];
    for (const [mac, name] of this.registeredMacs.entries()) {
      if (!seen.has(mac)) {
        notSeen.push(name);
      }
    }
    return notSeen;
  }

  /** Tags registered but not in range right now. */
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

  /** Time of last new unique tag detection. */
  getLastNewTagTime(): Date | null {
    let latest: Date | null = null;
    for (const record of this.seenToday.values()) {
      if (record.seenCount === 1 || !latest || record.firstSeenAt > latest) {
        if (!latest || record.firstSeenAt > latest) {
          latest = record.firstSeenAt;
        }
      }
    }
    return latest;
  }

  /** Whether a shift is currently active. */
  isShiftActive(): boolean {
    return this.shiftState !== null;
  }

  /** Current mode (patrol or kraal). */
  getMode(): 'patrol' | 'kraal' | 'idle' {
    if (!this.shiftState) return 'idle';
    return this.shiftState.mode;
  }

  /** Departure count (baseline from morning kraal scan). */
  getDepartureCount(): number {
    return this.shiftState?.departureCount || 0;
  }

  /** Get shift start time. */
  getShiftStartTime(): Date | null {
    return this.shiftState ? new Date(this.shiftState.startedAt) : null;
  }

  /** Get current farm ID. */
  getFarmId(): string | null {
    return this.farmId;
  }
}

export const bleScanner = new BLEScanner();
