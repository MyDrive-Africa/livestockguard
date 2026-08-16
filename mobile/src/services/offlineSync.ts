/**
 * Offline Sync Manager — monitors connectivity and auto-flushes buffered BLE batches.
 *
 * Integrates the existing offlineBuffer with network state detection.
 * When connectivity returns, automatically sends any queued sightings to the API.
 */

import { AppState, AppStateStatus } from 'react-native';
import { api } from './api';
import { offlineBuffer } from './offlineBuffer';

const SYNC_CHECK_INTERVAL_MS = 30000; // Check every 30s
const CONNECTIVITY_CHECK_URL = '/health';

class OfflineSyncManager {
  private isOnline = true;
  private syncTimer: ReturnType<typeof setInterval> | null = null;
  private appStateListener: any = null;

  /**
   * Start monitoring connectivity and auto-syncing.
   * Call this once after login when the app is ready.
   */
  start() {
    this.checkConnectivity();

    // Periodic sync check
    this.syncTimer = setInterval(() => {
      this.checkAndSync();
    }, SYNC_CHECK_INTERVAL_MS);

    // Sync when app comes to foreground
    this.appStateListener = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'active') {
        this.checkAndSync();
      }
    });

    console.log('[OfflineSync] Started monitoring');
  }

  /**
   * Stop monitoring.
   */
  stop() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
    if (this.appStateListener) {
      this.appStateListener.remove();
      this.appStateListener = null;
    }
    console.log('[OfflineSync] Stopped');
  }

  /**
   * Check connectivity by hitting the API health endpoint.
   */
  private async checkConnectivity(): Promise<boolean> {
    try {
      await api.get(CONNECTIVITY_CHECK_URL, { timeout: 5000 });
      this.isOnline = true;
      return true;
    } catch {
      this.isOnline = false;
      return false;
    }
  }

  /**
   * Check connectivity and flush buffer if online.
   */
  async checkAndSync(): Promise<{ synced: number; pending: number }> {
    const online = await this.checkConnectivity();
    const pending = await offlineBuffer.pendingCount();

    if (online && pending > 0) {
      console.log(`[OfflineSync] Online with ${pending} buffered batches — flushing...`);
      const result = await offlineBuffer.flush();
      const remaining = await offlineBuffer.pendingCount();
      return { synced: result.sent, pending: remaining };
    }

    return { synced: 0, pending };
  }

  /**
   * Store a BLE batch — tries to send immediately, buffers if offline.
   */
  async sendOrBuffer(batch: {
    gateway_serial: string;
    latitude: number;
    longitude: number;
    speed: number;
    battery_pct: number;
    sightings: Array<{ mac_address: string; rssi: number }>;
  }): Promise<'sent' | 'buffered'> {
    if (this.isOnline) {
      try {
        await api.post('/api/v1/gateway/batch', batch);
        return 'sent';
      } catch {
        // Network failed — buffer it
        await offlineBuffer.store(batch);
        this.isOnline = false;
        return 'buffered';
      }
    } else {
      await offlineBuffer.store(batch);
      return 'buffered';
    }
  }

  /**
   * Get current sync status.
   */
  async getStatus(): Promise<{ online: boolean; pendingBatches: number }> {
    const pending = await offlineBuffer.pendingCount();
    return { online: this.isOnline, pendingBatches: pending };
  }

  /**
   * Force a sync attempt now.
   */
  async forceSync(): Promise<{ sent: number; failed: number }> {
    const online = await this.checkConnectivity();
    if (!online) {
      return { sent: 0, failed: 0 };
    }
    return offlineBuffer.flush();
  }

  /**
   * Whether we're currently online.
   */
  get online(): boolean {
    return this.isOnline;
  }
}

export const offlineSyncManager = new OfflineSyncManager();
