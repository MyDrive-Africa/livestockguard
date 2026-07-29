/**
 * BLE Scanner Service — Background BLE scanning for cattle ear tags.
 *
 * Runs as a foreground service (Android) or background mode (iOS).
 * Detects BLE advertisements from registered ear tags and buffers sightings.
 */

import { BleManager, Device } from 'react-native-ble-plx';
import * as Location from 'expo-location';
import { api } from './api';
import { offlineBuffer } from './offlineBuffer';

const SCAN_INTERVAL_MS = 5000;
const BATCH_INTERVAL_MS = 25000;
const BLE_SERVICE_UUID = null; // Scan for all devices (filter by MAC later)

class BLEScanner {
  private manager: BleManager;
  private isScanning = false;
  private registeredMacs: Set<string> = new Set();
  private sightingBuffer: Array<{ mac_address: string; rssi: number }> = [];
  private gatewaySerial: string = '';
  private batchTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.manager = new BleManager();
  }

  /**
   * Initialize scanner with registered MACs from the API.
   */
  async init(gatewaySerial: string, farmId: string) {
    this.gatewaySerial = gatewaySerial;

    // Fetch registered BLE tags for this farm
    try {
      const resp = await api.get(`/api/gateway/tags?farm_id=${farmId}`);
      const tags = resp.data;
      this.registeredMacs = new Set(tags.map((t: any) => t.mac_address.toUpperCase()));
      console.log(`[BLE] Loaded ${this.registeredMacs.size} registered MACs`);
    } catch (err) {
      console.warn('[BLE] Failed to load MACs, will scan all devices');
    }
  }

  /**
   * Start continuous BLE scanning.
   */
  async start() {
    if (this.isScanning) return;
    this.isScanning = true;

    // Request BLE permissions
    const state = await this.manager.state();
    if (state !== 'PoweredOn') {
      console.warn('[BLE] Bluetooth not powered on:', state);
      return;
    }

    console.log('[BLE] Starting scan...');
    this.scan();

    // Send batches to API at intervals
    this.batchTimer = setInterval(() => this.sendBatch(), BATCH_INTERVAL_MS);
  }

  /**
   * Stop scanning.
   */
  stop() {
    this.isScanning = false;
    this.manager.stopDeviceScan();
    if (this.batchTimer) {
      clearInterval(this.batchTimer);
      this.batchTimer = null;
    }
    console.log('[BLE] Stopped');
  }

  /**
   * Perform a single BLE scan cycle.
   */
  private scan() {
    if (!this.isScanning) return;

    this.manager.startDeviceScan(
      null, // Scan all service UUIDs
      { allowDuplicates: true },
      (error, device) => {
        if (error) {
          console.warn('[BLE] Scan error:', error.message);
          return;
        }
        if (!device || !device.id) return;

        const mac = device.id.toUpperCase();

        // Only record known registered ear tags
        if (this.registeredMacs.size > 0 && !this.registeredMacs.has(mac)) {
          return;
        }

        this.sightingBuffer.push({
          mac_address: mac,
          rssi: device.rssi || -100,
        });
      }
    );

    // Stop and restart scan every interval (saves battery)
    setTimeout(() => {
      this.manager.stopDeviceScan();
      if (this.isScanning) {
        setTimeout(() => this.scan(), 1000); // Brief pause
      }
    }, SCAN_INTERVAL_MS - 1000);
  }

  /**
   * Send buffered sightings to the API (or store offline).
   */
  private async sendBatch() {
    if (this.sightingBuffer.length === 0) return;

    // Get current GPS position
    let latitude = 0, longitude = 0, speed = 0;
    try {
      const loc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      latitude = loc.coords.latitude;
      longitude = loc.coords.longitude;
      speed = (loc.coords.speed || 0) * 3.6; // m/s to km/h
    } catch {
      console.warn('[BLE] Location unavailable');
    }

    const batch = {
      gateway_serial: this.gatewaySerial,
      latitude,
      longitude,
      speed,
      battery_pct: 100, // TODO: read actual battery level
      sightings: [...this.sightingBuffer],
    };

    this.sightingBuffer = [];

    try {
      await api.post('/api/gateway/batch', batch);
      console.log(`[BLE] Sent ${batch.sightings.length} sightings`);
    } catch {
      // Offline — buffer locally
      offlineBuffer.store(batch);
      console.log(`[BLE] Offline — buffered ${batch.sightings.length} sightings`);
    }
  }

  /**
   * Get current cattle count (how many registered MACs detected recently).
   */
  getCattleInRange(): number {
    const recentMacs = new Set(this.sightingBuffer.map(s => s.mac_address));
    return recentMacs.size;
  }

  getTotalRegistered(): number {
    return this.registeredMacs.size;
  }
}

export const bleScanner = new BLEScanner();
