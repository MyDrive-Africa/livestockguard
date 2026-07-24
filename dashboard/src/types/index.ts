export interface Position {
  latitude: number;
  longitude: number;
  altitude?: number;
  hdop?: number;
  timestamp: string;
}

export interface Farm {
  id: string;
  name: string;
  organisationId: string;
  location?: Position;
  timezone: string;
}

export interface Animal {
  id: string;
  name: string;
  tagId: string;
  species: string;
  breed?: string;
  farmId: string;
  deviceId?: string;
  dateOfBirth?: string;
  lastPosition?: Position;
  activityState?: 'grazing' | 'resting' | 'walking' | 'running';
  batteryLevel?: number;
}

export interface Device {
  id: string;
  serialNumber: string;
  deviceType: 'collar' | 'eartag';
  firmwareVersion?: string;
  farmId?: string;
  animalId?: string;
  status: 'active' | 'inactive' | 'offline' | 'maintenance';
  lastSeen?: string;
  batteryLevel?: number;
  signalStrength?: number;
}

export interface Geofence {
  id: string;
  name: string;
  farmId: string;
  geometry: GeoJSON.Polygon;
  fenceType: 'inclusion' | 'exclusion';
  active: boolean;
  alertOnBreach: boolean;
}

export interface Alert {
  id: string;
  farmId: string;
  deviceId?: string;
  animalId?: string;
  geofenceId?: string;
  alertType: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status: 'active' | 'acknowledged' | 'resolved';
  message: string;
  location?: Position;
  createdAt: string;
  acknowledgedAt?: string;
  resolvedAt?: string;
}

export interface AnimalPosition {
  animalId: string;
  animalName: string;
  position: Position;
  activityState: string;
  batteryLevel: number;
}
