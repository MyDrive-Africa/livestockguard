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
  gender?: 'male' | 'female';
  colour?: string;
  description?: string;
  photo_url?: string;
  weight_kg?: number;
  status: 'active' | 'sold' | 'deceased' | 'transferred';
  date_of_birth?: string;
  mother_id?: string;
  father_id?: string;
  device_serial?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_speed?: number;
  battery_level?: number;
}

export interface Farm {
  id: string;
  name: string;
  organisation_id: string;
  province?: string;
  district?: string;
  plot_number?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  area_hectares?: number;
  contact_name?: string;
  contact_phone?: string;
  timezone: string;
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
  // Boundary-shape support (migration 013). A circle stores centre + radius;
  // rectangle/polygon use `geometry`. `buffer_m` is the inner warning band.
  shape?: 'polygon' | 'rectangle' | 'circle';
  center_latitude?: number | null;
  center_longitude?: number | null;
  radius_m?: number | null;
  buffer_m?: number | null;
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

// Beam sensor perimeter layer
export interface BeamSensor {
  id: string;
  farm_id: string;
  geofence_id?: string | null;
  serial_number: string;
  name: string;
  beam_type: 'infrared' | 'microwave' | 'laser';
  latitude: number;
  longitude: number;
  span_start_latitude?: number | null;
  span_start_longitude?: number | null;
  span_end_latitude?: number | null;
  span_end_longitude?: number | null;
  orientation_deg?: number | null;
  span_length_m?: number | null;
  breach_severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  alert_on_crossing: boolean;
  status: 'active' | 'inactive' | 'maintenance' | 'fault';
  last_seen?: string | null;
  last_battery_pct?: number | null;
}

// Robotic herdsman layer
export type RobotStatus =
  | 'idle' | 'patrolling' | 'enroute' | 'shepherding' | 'charging' | 'fault' | 'offline';

export interface Robot {
  id: string;
  farm_id: string;
  serial_number: string;
  name: string;
  model: 'humanoid' | 'wheeled' | 'quadruped';
  status: RobotStatus;
  last_latitude?: number | null;
  last_longitude?: number | null;
  heading_deg?: number | null;
  battery_pct?: number | null;
  current_job_id?: string | null;
  home_latitude?: number | null;
  home_longitude?: number | null;
  max_speed_mps: number;
  last_seen?: string | null;
}

export interface HerdingJob {
  id: string;
  farm_id: string;
  robot_id?: string | null;
  job_type: 'intercept' | 'shepherd' | 'patrol' | 'return_kraal' | 'investigate';
  target_animal_id?: string | null;
  target_latitude?: number | null;
  target_longitude?: number | null;
  priority: number;
  status: 'pending' | 'assigned' | 'active' | 'completed' | 'failed' | 'cancelled';
  reason?: string | null;
  created_at?: string | null;
}

export interface HerdingStatus {
  farm_id: string;
  robots_total: number;
  robots_active: number;   // enroute or shepherding
  robots_charging: number;
  active_jobs: number;
}

/** Real-time robot telemetry payload (WS event `robot.update`). */
export interface RobotUpdatePayload {
  serial: string;
  position: { latitude: number; longitude: number; heading?: number; speed?: number };
  batteryLevel?: number;
  state?: RobotStatus;
  deterrent?: string | null;
}
