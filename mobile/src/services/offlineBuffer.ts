/**
 * Offline buffer — stores BLE sightings locally when no internet.
 * Syncs to API when connection returns.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from './api';

const BUFFER_KEY = 'offline_sightings';
const MAX_BUFFER_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

interface BufferedBatch {
  timestamp: number;
  gateway_serial: string;
  latitude: number;
  longitude: number;
  speed: number;
  battery_pct: number;
  sightings: Array<{ mac_address: string; rssi: number }>;
}

class OfflineBuffer {
  /**
   * Store a batch for later sync.
   */
  async store(batch: Omit<BufferedBatch, 'timestamp'>) {
    const existing = await this.getAll();
    existing.push({ ...batch, timestamp: Date.now() });

    // Trim old entries (older than 24h)
    const cutoff = Date.now() - MAX_BUFFER_AGE_MS;
    const trimmed = existing.filter(b => b.timestamp > cutoff);

    await AsyncStorage.setItem(BUFFER_KEY, JSON.stringify(trimmed));
  }

  /**
   * Get all buffered batches.
   */
  async getAll(): Promise<BufferedBatch[]> {
    const raw = await AsyncStorage.getItem(BUFFER_KEY);
    if (!raw) return [];
    try {
      return JSON.parse(raw);
    } catch {
      return [];
    }
  }

  /**
   * Get count of pending batches.
   */
  async pendingCount(): Promise<number> {
    const all = await this.getAll();
    return all.length;
  }

  /**
   * Flush all buffered batches to the API.
   * Call this when internet connection is restored.
   */
  async flush(): Promise<{ sent: number; failed: number }> {
    const batches = await this.getAll();
    if (batches.length === 0) return { sent: 0, failed: 0 };

    let sent = 0;
    let failed = 0;
    const remaining: BufferedBatch[] = [];

    for (const batch of batches) {
      try {
        await api.post('/api/v1/gateway/batch', {
          gateway_serial: batch.gateway_serial,
          latitude: batch.latitude,
          longitude: batch.longitude,
          speed: batch.speed,
          battery_pct: batch.battery_pct,
          sightings: batch.sightings,
        });
        sent++;
      } catch {
        remaining.push(batch);
        failed++;
      }
    }

    await AsyncStorage.setItem(BUFFER_KEY, JSON.stringify(remaining));
    console.log(`[Offline] Flushed: ${sent} sent, ${failed} failed, ${remaining.length} remaining`);
    return { sent, failed };
  }

  /**
   * Clear all buffered data.
   */
  async clear() {
    await AsyncStorage.removeItem(BUFFER_KEY);
  }
}

export const offlineBuffer = new OfflineBuffer();
