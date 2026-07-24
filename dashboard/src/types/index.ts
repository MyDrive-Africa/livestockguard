// Shared types for LivestockGuard dashboard

export interface Position {
  latitude: number;
  longitude: number;
  altitude?: number;
  speed?: number;
  heading?: number;
}

export interface AnimalPosition {
  animalId: string;
  animalName: string;
  position: Position;
  activityState?: string;
  batteryLevel?: number;
  lastSeen?: string;
}

export interface Alert {
  id: string;
  alert_type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status: 'active' | 'acknowledged' | 'resolved';
  message?: string;
  animal_name?: string;
  created_at: string;
}

export interface Animal {
  id: string;
  name: string;
  tag_id: string;
  species: string;
  breed?: string;
  device_serial?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_speed?: number;
  battery_level?: number;
}

export interface Geofence {
  id: string;
  name: string;
  farm_id: string;
  fence_type: 'inclusion' | 'exclusion';
  geometry: GeoJSON.Polygon;
  active: boolean;
  alert_on_breach: boolean;
  created_at: string;
}

export interface Device {
  id: string;
  serial_number: string;
  device_type: string;
  firmware_version?: string;
  status: string;
  battery_level?: number;
  last_seen?: string;
  animal_name?: string;
}

// WebSocket message types
export interface WsMessage {
  type: string;
  payload: Record<string, unknown>;
}

export interface PositionUpdatePayload {
  animalId: string;
  animalName: string;
  position: Position;
  activityState?: string;
  batteryLevel?: number;
}

export interface AlertCreatedPayload extends Alert {}
