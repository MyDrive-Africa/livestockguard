-- LivestockGuard Migration 012
-- Description: Physical Beam Sensor Perimeter Layer
--
-- Adds an infrared/microwave break-beam sensor device type. A beam sensor is a
-- FIXED-LOCATION device (like a herdsman gateway, unlike collars/ear tags it is
-- NOT attached to an animal) mounted at a chokepoint along a farm border: a gate,
-- a fence gap, a drainage line, or a known theft path.
--
-- Unlike a virtual geofence — which is a POLYGON containment check — a beam sensor
-- detects a LINE-CROSSING event. It fires the instant something passes between its
-- transmitter and receiver posts. This complements the existing GPS/BLE virtual
-- geofence: the polygon watches the whole area, the beams watch the gaps.
--
-- Phased rollout intent (e.g. the 50ha Sibanyoni border): beams act as interim
-- "border sentinels" over the virtual geofence while a physical fence/wall is built
-- section by section. A beam may optionally be linked to the geofence whose border
-- it guards, and stores the line segment it protects so the dashboard can draw the
-- guarded spans on top of the geofence polygon.

-- ============================================================================
-- Allow 'beam_sensor' as a device_type on the core devices table.
-- (Mirrors the ALTER pattern migration 007 used to add 'herdsman_gateway'.)
-- ============================================================================

ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_type_check;
ALTER TABLE devices ADD CONSTRAINT devices_device_type_check
    CHECK (device_type IN ('collar', 'eartag', 'herdsman_gateway', 'beam_sensor'));

-- ============================================================================
-- BEAM SENSORS
-- Fixed perimeter break-beam sensor. Represents one guarded crossing line.
-- ============================================================================

CREATE TABLE beam_sensors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    -- Optional: the geofence whose border this beam guards (for map overlay).
    geofence_id UUID REFERENCES geofences(id) ON DELETE SET NULL,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,                       -- e.g. "Main Gate Beam", "North Fence Gap"
    beam_type VARCHAR(50) NOT NULL DEFAULT 'infrared' -- 'infrared' | 'microwave' | 'laser'
        CHECK (beam_type IN ('infrared', 'microwave', 'laser')),

    -- Mount location: the sensor post (transmitter side / primary mount).
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,

    -- The guarded crossing line: from the transmitter post to the receiver post.
    -- Stored both as explicit endpoints (simple to read/edit) and as a PostGIS
    -- LINESTRING geography (for spatial queries / map rendering).
    span_start_latitude DOUBLE PRECISION,
    span_start_longitude DOUBLE PRECISION,
    span_end_latitude DOUBLE PRECISION,
    span_end_longitude DOUBLE PRECISION,
    span GEOGRAPHY(LINESTRING, 4326),                 -- Optional; the physical beam line

    orientation_deg REAL,                             -- Compass bearing the beam faces (0-360)
    span_length_m REAL,                               -- Distance between the two posts

    -- Escalation: a beam crossing is a strong theft signal at a border. Default high.
    breach_severity VARCHAR(20) NOT NULL DEFAULT 'high'
        CHECK (breach_severity IN ('critical', 'high', 'medium', 'low', 'info')),
    alert_on_crossing BOOLEAN NOT NULL DEFAULT TRUE,

    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance', 'fault')),
    firmware_version VARCHAR(50),
    last_seen TIMESTAMPTZ,
    last_battery_pct INT,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_beam_sensors_farm ON beam_sensors(farm_id);
CREATE INDEX idx_beam_sensors_geofence ON beam_sensors(geofence_id);
CREATE INDEX idx_beam_sensors_serial ON beam_sensors(serial_number);
CREATE INDEX idx_beam_sensors_status ON beam_sensors(status);
CREATE INDEX idx_beam_sensors_span ON beam_sensors USING GIST(span);

-- ============================================================================
-- BEAM CROSSINGS (TimescaleDB hypertable)
-- Each row = one crossing event detected by a beam sensor.
-- The beam usually does NOT know WHICH animal crossed (it just sees a break),
-- so animal_id is nullable. Correlating the crossing with a nearby GPS/BLE
-- position (to attribute an animal) is done downstream, not here.
-- ============================================================================

CREATE TABLE beam_crossings (
    time TIMESTAMPTZ NOT NULL,
    beam_sensor_id UUID NOT NULL REFERENCES beam_sensors(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    direction VARCHAR(10) NOT NULL DEFAULT 'unknown'  -- 'in' | 'out' | 'unknown'
        CHECK (direction IN ('in', 'out', 'unknown')),
    confidence REAL,                                  -- 0.0-1.0 detection confidence
    animal_id UUID REFERENCES animals(id) ON DELETE SET NULL,  -- if later attributed
    beam_battery_pct INT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

-- Convert to TimescaleDB hypertable for efficient time-series queries
SELECT create_hypertable('beam_crossings', 'time');

CREATE INDEX idx_beam_crossings_sensor ON beam_crossings(beam_sensor_id, time DESC);
CREATE INDEX idx_beam_crossings_farm ON beam_crossings(farm_id, time DESC);
CREATE INDEX idx_beam_crossings_animal ON beam_crossings(animal_id, time DESC);

-- Retain 1 year of raw crossings (matches ble_sightings policy)
SELECT add_retention_policy('beam_crossings', INTERVAL '1 year');

-- ============================================================================

DO $$ BEGIN
    RAISE NOTICE 'Migration 012 applied: Beam Sensor Perimeter Layer';
    RAISE NOTICE '  - devices.device_type now allows beam_sensor';
    RAISE NOTICE '  - beam_sensors table (fixed perimeter break-beam devices)';
    RAISE NOTICE '  - beam_crossings hypertable (line-crossing events, 1y retention)';
END $$;
