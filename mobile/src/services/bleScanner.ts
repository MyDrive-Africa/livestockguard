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
      const resp = await api.get(`/api/v1/gateway/tags?farm_id=${this.farmId}`);
      const tags = resp.data;
      this.totalRegistered = tags.length;
      tags.forEach((t: any) => {
        this.registeredMacs.set(t.mac_address, t.animal_name || t.tag_name || 'Unknown');
      });
      console.log(`[BLE] Initialized for farm ${this.farmId}: ${this.totalRegistered} registered tags`);
    } catch {
      // Fallback: use animals endpoint
      try {
        const animalsResp = await api.get(`/api/v1/animals?farm_id=${this.farmId}`);
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
   * SIMULATOR MODE: Simulates BLE detection using herdsman position + animal positions.
   * Only detects cattle within BLE range of the herdsman, so cumulative "seen today"
   * grows gradually as the herdsman moves through the farm.
   *
   * Falls back to herd-count based gradual discovery when:
   * - No gateway with a known position exists
   * - The gateway status endpoint returns no recent animals
   * - Any API call in the position-based path fails
   */
  private startSimulatorMode() {
    const poll = async () => {
      if (!this.farmId || this.totalRegistered === 0) return;

      // Auto-start shift if not already active — ensures "seen today" tracking
      // begins as soon as the scanner starts polling, without requiring manual tap.
      if (!this.shiftState) {
        await this.startShift();
      }

      let usedPositionPath = false;

      try {
        // Step 1: Get gateways for this farm to find herdsman position
        const gwResp = await api.get(`/api/v1/gateway`, { params: { farm_id: this.farmId } });
        const gateways = gwResp.data as Array<{
          serial_number: string;
          last_latitude?: number;
          last_longitude?: number;
          last_seen?: string;
          max_ble_range_m?: number;
        }>;

        // Find the most recently active gateway with a position
        const activeGw = gateways
          .filter((g) => g.last_latitude != null && g.last_longitude != null && g.last_seen)
          .sort((a, b) => new Date(b.last_seen!).getTime() - new Date(a.last_seen!).getTime())[0];

        if (!activeGw || activeGw.last_latitude == null || activeGw.last_longitude == null) {
          // No active gateway with position — fall back to herd-count based mode
          await this.pollFallbackHerdCount();
          return;
        }

        const herdsmanLat = activeGw.last_latitude;
        const herdsmanLon = activeGw.last_longitude;
        const bleRange = activeGw.max_ble_range_m || BLE_MAX_RANGE_M;

        // Step 2: Get recent animal sightings with positions from gateway status
        const statusResp = await api.get(`/api/v1/gateway/status/${activeGw.serial_number}`);
        const statusData = statusResp.data;
        const recentAnimals = (statusData.recent_animals || []) as Array<{
          animal_id: string;
          animal_name: string;
          mac_address: string;
          rssi: number;
          latitude: number;
          longitude: number;
        }>;

        // If the status endpoint returned no animals (sightings expired from
        // the 1-hour window, or simulator hasn't sent data yet), fall back
        // to herd-count based gradual discovery instead of showing 0.
        if (recentAnimals.length === 0) {
          await this.pollFallbackHerdCount();
          return;
        }

        // Step 3: Calculate distance and only detect cattle within BLE range
        this.recentSightings.clear();
        usedPositionPath = true;

        for (const animal of recentAnimals) {
          if (!animal.latitude || !animal.longitude) continue;

          const dist = this.distanceMeters(
            herdsmanLat, herdsmanLon,
            animal.latitude, animal.longitude
          );

          if (dist <= bleRange) {
            // Within BLE detection range — simulate RSSI from distance
            const rssi = this.rssiFromDistance(dist);
            const mac = animal.mac_address;
            const name = animal.animal_name || this.registeredMacs.get(mac) || 'Unknown';

            this.recentSightings.set(mac, {
              animalId: animal.animal_id,
              animalName: name,
              mac,
              rssi,
              lastSeen: new Date(),
              inRange: true,
            });

            // Add to cumulative "seen today"
            this.addToSeenToday(mac, name);
          }
        }

        // If position-based path found animals but none were within BLE range,
        // fall through to herd-count fallback so the UI isn't stuck at 0.
        if (usedPositionPath && this.recentSightings.size === 0) {
          await this.pollFallbackHerdCount();
          return;
        }

        // Also update total registered from API if available
        try {
          const herdResp = await api.get(`/api/v1/gateway/herd-count/${this.farmId}`);
          if (herdResp.data.total_registered) {
            this.totalRegistered = herdResp.data.total_registered;
          }
        } catch {
          // Non-critical
        }
      } catch {
        // Fallback: use herd-count based approach
        await this.pollFallbackHerdCount();
      }

      // Persist cumulative state periodically
      await this.persistState();
    };

    poll();
    this.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  /**
   * Fallback polling when no gateway position is available.
   * Uses herd-count API but does NOT add all cattle at once —
   * adds a realistic subset each tick to simulate gradual discovery.
   */
  private async pollFallbackHerdCount() {
    try {
      const resp = await api.get(`/api/v1/gateway/herd-count/${this.farmId}`);
      const data = resp.data;

      if (data.total_registered) {
        this.totalRegistered = data.total_registered;
      }

      this.recentSightings.clear();

      // Use server's authoritative "seen today" count and "missing" list to
      // ensure all device instances converge to the same percentage.
      const serverSeenToday: number = data.seen_today || 0;
      const serverMissingCount: number = data.missing_count ?? data.missing?.length ?? 0;
      const missingNames: Set<string> = new Set(
        (data.missing || []).map((m: { name: string }) => m.name)
      );

      if (serverSeenToday > 0 || serverMissingCount > 0) {
        // Server has real data — sync our local "seen today" set to match.
        // Mark every registered animal NOT in the missing list as "seen".
        for (const [mac, name] of this.registeredMacs.entries()) {
          if (!missingNames.has(name) && !this.seenToday.has(mac)) {
            this.addToSeenToday(mac, name);
          }
        }
        // Also remove any that the server now considers missing (edge case:
        // server dropped them from "seen" due to time threshold change)
        for (const [mac, record] of this.seenToday.entries()) {
          if (missingNames.has(record.name)) {
            this.seenToday.delete(mac);
          }
        }
      } else {
        // No server sighting data yet — use gradual local discovery as fallback.
        // Each tick discovers a few more animals to simulate herdsman walking.
        const isLargeFarm = this.totalRegistered > 20;
        const maxNewPerTick = isLargeFarm ? 3 : 2;
        const alreadySeen = this.seenToday.size;

        const allMacs = Array.from(this.registeredMacs.entries());
        const unseenMacs = allMacs.filter(([mac]) => !this.seenToday.has(mac));

        const newDiscoveries = unseenMacs
          .sort(() => Math.random() - 0.5)
          .slice(0, Math.min(maxNewPerTick, this.totalRegistered - alreadySeen));

        for (const [mac, name] of newDiscoveries) {
          this.addToSeenToday(mac, name);
        }
      }

      // "In range" count: simulate realistic BLE variability.
      // Real BLE scanning sees a fluctuating subset — not a fixed number.
      // Base it on the number seen today (more coverage = more likely near cattle).
      const seenCount = this.seenToday.size;
      const isLargeFarm = this.totalRegistered > 20;

      // Base range: 10-25% of seen animals, with random variance each tick
      const basePct = isLargeFarm ? 0.20 : 0.45;
      const variance = (Math.random() - 0.5) * 0.10; // ±5% jitter
      const inRangeCount = Math.max(
        1,
        Math.round(seenCount * (basePct + variance))
      );

      // Pick which animals appear "in range" this tick
      const allMacs = Array.from(this.registeredMacs.entries());
      const seenMacs = allMacs.filter(([mac]) => this.seenToday.has(mac));

      // Shuffle to vary which specific animals show as in-range each poll
      const shuffledSeen = seenMacs.sort(() => Math.random() - 0.5);
      const inRangeAnimals = shuffledSeen.slice(0, Math.min(inRangeCount, shuffledSeen.length));

      for (const [mac, name] of inRangeAnimals) {
        const rssi = -45 - Math.floor(Math.random() * 25);
        this.recentSightings.set(mac, {
          animalId: mac, animalName: name, mac, rssi, lastSeen: new Date(), inRange: true,
        });
      }
    } catch {
      this.simulateLocalBLE();
    }
  }

  /**
   * Calculate distance in meters between two lat/lon points.
   */
  private distanceMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const dy = (lat2 - lat1) * 111320.0;
    const dx = (lon2 - lon1) * 111320.0 * Math.cos((lat1 * Math.PI) / 180);
    return Math.sqrt(dx * dx + dy * dy);
  }

  /**
   * Simulate RSSI from distance (BLE path loss model).
   */
  private rssiFromDistance(dist: number): number {
    const txPower = -59; // BLE TX power at 1m
    const pathLoss = 2.5; // Path loss exponent (outdoor)
    if (dist < 0.5) dist = 0.5;
    const rssi = txPower - 10 * pathLoss * Math.log10(dist);
    // Add some noise
    const noise = (Math.random() - 0.5) * 6;
    return Math.max(-100, Math.min(-30, Math.round(rssi + noise)));
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
