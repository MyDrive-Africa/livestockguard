-- LivestockGuard Migration 007
-- Description: Herdsman Gateway Architecture
-- A herdsman carries a gateway device (phone/dedicated hardware) that collects
-- BLE advertisement pings from passive cattle ear tags and relays them via cellular.

-- ============================================================================
-- GATEWAY DEVICES
-- Represents the physical gateway device carried by a herdsman.
-- Unlike collar/eartag devices, a gateway is NOT attached to an animal.
-- ============================================================================

CREATE TABLE gateway_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,                      -- e.g. "Sipho's Phone", "Gateway Unit A"
    device_type VARCHAR(50) NOT NULL DEFAULT 'phone' -- 'phone' | 'dedicated_hardware'
        CHECK (device_type IN ('phone', 'dedicated_hardware')),
    herdsman_name VARCHAR(255),                      -- Who carries this device
    herdsman_phone VARCHAR(50),                      -- Contact number
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance', 'lost')),
    firmware_version VARCHAR(50),
    last_seen TIMESTAMPTZ,
    last_latitude DOUBLE PRECISION,
    last_longitude DOUBLE PRECISION,
    last_battery_pct INT,
    ble_scan_interval_ms INT NOT NULL DEFAULT 5000,  -- How often gateway scans for BLE tags
    report_interval_sec INT NOT NULL DEFAULT 30,     -- How often gateway sends batch to cloud
    max_ble_range_m INT NOT NULL DEFAULT 100,        -- Expected BLE range (for UI display)
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_gateway_devices_farm ON gateway_devices(farm_id);
CREATE INDEX idx_gateway_devices_status ON gateway_devices(status);
CREATE INDEX idx_gateway_devices_serial ON gateway_devices(serial_number);

-- ============================================================================
-- BLE EAR TAGS
-- Passive BLE beacons attached to cattle. Cheap (~R50), long battery (2-5 years).
-- They broadcast a unique MAC/UUID. The gateway resolves this to an animal.
-- ============================================================================

CREATE TABLE ble_ear_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    animal_id UUID REFERENCES animals(id) ON DELETE SET NULL,
    mac_address VARCHAR(17) NOT NULL UNIQUE,          -- BLE MAC e.g. "AA:BB:CC:DD:EE:FF"
    tag_name VARCHAR(100),                            -- Human label e.g. "Tag-042"
    manufacturer VARCHAR(100),                        -- Tag hardware manufacturer
    battery_type VARCHAR(50) DEFAULT 'CR2032',
    estimated_battery_months INT DEFAULT 36,          -- Expected lifespan
    installed_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'lost', 'replaced')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ble_ear_tags_farm ON ble_ear_tags(farm_id);
CREATE INDEX idx_ble_ear_tags_animal ON ble_ear_tags(animal_id);
CREATE INDEX idx_ble_ear_tags_mac ON ble_ear_tags(mac_address);
CREATE INDEX idx_ble_ear_tags_status ON ble_ear_tags(status);

-- ============================================================================
-- BLE SIGHTINGS (TimescaleDB hypertable)
-- Each row = one BLE advertisement received by a gateway.
-- Gateway GPS is used as the animal's approximate position.
-- ============================================================================

CREATE TABLE ble_sightings (
    time TIMESTAMPTZ NOT NULL,
    gateway_id UUID NOT NULL REFERENCES gateway_devices(id) ON DELETE CASCADE,
    ble_tag_id UUID REFERENCES ble_ear_tags(id) ON DELETE SET NULL,
    mac_address VARCHAR(17) NOT NULL,                 -- Raw MAC from scan
    animal_id UUID REFERENCES animals(id) ON DELETE SET NULL,
    rssi INT NOT NULL,                                -- Signal strength (dBm, e.g. -65)
    estimated_distance_m REAL,                        -- Calculated from RSSI + calibration
    gateway_latitude DOUBLE PRECISION NOT NULL,       -- Gateway GPS at time of scan
    gateway_longitude DOUBLE PRECISION NOT NULL,
    gateway_altitude REAL,
    gateway_speed REAL,                               -- Herdsman walking speed
    gateway_battery_pct INT
);

-- Convert to TimescaleDB hypertable for efficient time-series queries
SELECT create_hypertable('ble_sightings', 'time');

CREATE INDEX idx_ble_sightings_gateway ON ble_sightings(gateway_id, time DESC);
CREATE INDEX idx_ble_sightings_animal ON ble_sightings(animal_id, time DESC);
CREATE INDEX idx_ble_sightings_mac ON ble_sightings(mac_address, time DESC);
CREATE INDEX idx_ble_sightings_tag ON ble_sightings(ble_tag_id, time DESC);

-- Retain 1 year of raw sightings (aggregated data kept longer)
SELECT add_retention_policy('ble_sightings', INTERVAL '1 year');

-- ============================================================================
-- HERDSMAN SESSIONS
-- Tracks when a herdsman starts/ends a patrol shift.
-- Useful for: attendance, coverage reports, anomaly detection.
-- ============================================================================

CREATE TABLE herdsman_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gateway_id UUID NOT NULL REFERENCES gateway_devices(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    herdsman_name VARCHAR(255),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    start_latitude DOUBLE PRECISION,
    start_longitude DOUBLE PRECISION,
    end_latitude DOUBLE PRECISION,
    end_longitude DOUBLE PRECISION,
    animals_seen INT DEFAULT 0,                       -- Count of unique animals detected
    total_sightings INT DEFAULT 0,                    -- Total BLE pings received
    distance_walked_m REAL,                           -- GPS track distance
    notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'abandoned'))
);

CREATE INDEX idx_herdsman_sessions_gateway ON herdsman_sessions(gateway_id, started_at DESC);
CREATE INDEX idx_herdsman_sessions_farm ON herdsman_sessions(farm_id, started_at DESC);
CREATE INDEX idx_herdsman_sessions_status ON herdsman_sessions(status);

-- ============================================================================
-- Update devices table to allow 'herdsman_gateway' type
-- ============================================================================

ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_type_check;
ALTER TABLE devices ADD CONSTRAINT devices_device_type_check
    CHECK (device_type IN ('collar', 'eartag', 'herdsman_gateway'));

-- ============================================================================
-- Continuous aggregate: animal last-seen summary (materialized view)
-- Provides fast lookup: "when/where was each animal last detected by any gateway?"
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS animal_last_seen AS
SELECT DISTINCT ON (animal_id)
    animal_id,
    gateway_id,
    time AS last_seen_at,
    gateway_latitude AS latitude,
    gateway_longitude AS longitude,
    rssi,
    estimated_distance_m
FROM ble_sightings
WHERE animal_id IS NOT NULL
ORDER BY animal_id, time DESC;

CREATE UNIQUE INDEX idx_animal_last_seen_animal ON animal_last_seen(animal_id);

-- Function to refresh the materialized view (call periodically or after batch insert)
CREATE OR REPLACE FUNCTION refresh_animal_last_seen()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY animal_last_seen;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================

DO $$ BEGIN
RAISE NOTICE 'Migration 007 applied: Herdsman Gateway Architecture';
RAISE NOTICE '  - gateway_devices table (gateway registration)';
RAISE NOTICE '  - ble_ear_tags table (passive BLE tag registry)';
RAISE NOTICE '  - ble_sightings hypertable (time-series BLE pings)';
RAISE NOTICE '  - herdsman_sessions table (patrol tracking)';
RAISE NOTICE '  - animal_last_seen materialized view';
END $$;
