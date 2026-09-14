-- LivestockGuard Migration 013
-- Description: Robotic Herdsman Layer
--
-- Adds an autonomous herding robot device type plus the coordination tables the
-- Herding Orchestrator service uses to keep cattle inside their boundary.
--
-- A herding robot is a MOBILE, non-animal device (unlike collars/ear tags it is not
-- attached to an animal; unlike beam sensors it is not fixed). A small fleet (e.g. 4
-- per farm) patrols a paddock and, when an animal approaches or crosses the boundary,
-- the nearest available robot is dispatched to gently shepherd it back toward the herd
-- centre using presence and sound (non-contact) — the way a human herdsman would.
--
-- This layer ADDS ACTUATION to the existing sensing platform:
--   sense (positions/BLE) -> detect (containment) -> decide + dispatch robot -> act
--
-- Boundary shapes: the orchestrator supports square/rectangle (a polygon) and circle
-- (centre + radius). Rectangles/polygons reuse the existing geofences.geometry; circles
-- are stored as centre + radius on the geofence for a cheap distance-to-centre check.
-- A warning buffer band flags animals that are APPROACHING the edge before they breach.

-- ============================================================================
-- Allow 'herding_robot' as a device_type on the core devices table.
-- (Same ALTER pattern migration 007 used for 'herdsman_gateway' and 012 for
-- 'beam_sensor'. Keep every previously-allowed type.)
-- ============================================================================

ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_type_check;
ALTER TABLE devices ADD CONSTRAINT devices_device_type_check
    CHECK (device_type IN ('collar', 'eartag', 'herdsman_gateway', 'beam_sensor', 'herding_robot'));

-- ============================================================================
-- Boundary shape support on geofences.
-- A square/rectangle is just a polygon (existing geometry column). A circle is
-- cheaper and more accurate stored as centre + radius. buffer_m is the inner
-- warning band: an animal within buffer_m of the edge is APPROACHING (not yet
-- breached), which lets the orchestrator act early.
-- ============================================================================

ALTER TABLE geofences ADD COLUMN IF NOT EXISTS shape VARCHAR(20) NOT NULL DEFAULT 'polygon'
    CHECK (shape IN ('polygon', 'rectangle', 'circle'));
ALTER TABLE geofences ADD COLUMN IF NOT EXISTS center_latitude DOUBLE PRECISION;
ALTER TABLE geofences ADD COLUMN IF NOT EXISTS center_longitude DOUBLE PRECISION;
ALTER TABLE geofences ADD COLUMN IF NOT EXISTS radius_m REAL;
ALTER TABLE geofences ADD COLUMN IF NOT EXISTS buffer_m REAL NOT NULL DEFAULT 15.0;

-- ============================================================================
-- HERDING ROBOTS
-- Fleet registry. One row per robot (typically 4 per farm).
-- ============================================================================

CREATE TABLE herding_robots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,       -- e.g. "ROBO-LV-01" (the robot's marker)
    name VARCHAR(255) NOT NULL,                        -- e.g. "Herder 1"

    -- Body-agnostic: the orchestrator only needs presence + sound + mobility.
    model VARCHAR(50) NOT NULL DEFAULT 'wheeled'
        CHECK (model IN ('humanoid', 'wheeled', 'quadruped')),

    status VARCHAR(50) NOT NULL DEFAULT 'offline'
        CHECK (status IN ('idle', 'patrolling', 'enroute', 'shepherding',
                          'charging', 'fault', 'offline')),

    -- Live pose (updated from robot_telemetry / Redis live cache).
    last_latitude DOUBLE PRECISION,
    last_longitude DOUBLE PRECISION,
    heading_deg REAL,
    battery_pct INT,

    current_job_id UUID,                               -- FK added after herding_jobs exists

    -- Charging dock / home position the robot returns to when idle or low battery.
    home_latitude DOUBLE PRECISION,
    home_longitude DOUBLE PRECISION,

    max_speed_mps REAL NOT NULL DEFAULT 2.0,           -- for ETA / intercept planning
    capabilities JSONB NOT NULL DEFAULT '{"audio": true, "presence": true}',

    firmware_version VARCHAR(50),
    last_seen TIMESTAMPTZ,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_herding_robots_farm ON herding_robots(farm_id);
CREATE INDEX idx_herding_robots_serial ON herding_robots(serial_number);
CREATE INDEX idx_herding_robots_status ON herding_robots(status);

-- ============================================================================
-- HERDING JOBS
-- A unit of herding work the orchestrator created and assigned to a robot.
-- ============================================================================

CREATE TABLE herding_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    robot_id UUID REFERENCES herding_robots(id) ON DELETE SET NULL,  -- null until assigned

    job_type VARCHAR(30) NOT NULL DEFAULT 'intercept'
        CHECK (job_type IN ('intercept', 'shepherd', 'patrol',
                            'return_kraal', 'investigate')),

    target_animal_id UUID REFERENCES animals(id) ON DELETE SET NULL,  -- null for patrol
    target_latitude DOUBLE PRECISION,
    target_longitude DOUBLE PRECISION,

    priority INT NOT NULL DEFAULT 0,                   -- higher = more urgent (breach > approaching)

    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'assigned', 'active', 'completed', 'failed', 'cancelled')),

    reason VARCHAR(255),                               -- human-readable why (e.g. "LV-003 approaching N edge")
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_herding_jobs_farm ON herding_jobs(farm_id);
CREATE INDEX idx_herding_jobs_robot ON herding_jobs(robot_id);
CREATE INDEX idx_herding_jobs_status ON herding_jobs(status);
CREATE INDEX idx_herding_jobs_animal ON herding_jobs(target_animal_id);

-- Now that herding_jobs exists, wire the robot's current job FK.
ALTER TABLE herding_robots
    ADD CONSTRAINT fk_herding_robots_current_job
    FOREIGN KEY (current_job_id) REFERENCES herding_jobs(id) ON DELETE SET NULL;

-- ============================================================================
-- ROBOT TELEMETRY (TimescaleDB hypertable)
-- High-frequency robot pose/state stream. Same pattern as positions /
-- ble_sightings / beam_crossings.
-- ============================================================================

CREATE TABLE robot_telemetry (
    time TIMESTAMPTZ NOT NULL,
    robot_id UUID NOT NULL REFERENCES herding_robots(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    heading_deg REAL,
    speed_mps REAL,
    battery_pct INT,
    state VARCHAR(50),                                 -- robot's self-reported state
    job_id UUID REFERENCES herding_jobs(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'               -- sensors, obstacle/contact events
);

-- Convert to TimescaleDB hypertable for efficient time-series queries
SELECT create_hypertable('robot_telemetry', 'time');

CREATE INDEX idx_robot_telemetry_robot ON robot_telemetry(robot_id, time DESC);
CREATE INDEX idx_robot_telemetry_farm ON robot_telemetry(farm_id, time DESC);
CREATE INDEX idx_robot_telemetry_job ON robot_telemetry(job_id, time DESC);

-- Retain 90 days of raw telemetry (telemetry is high-volume; shorter than events)
SELECT add_retention_policy('robot_telemetry', INTERVAL '90 days');

-- ============================================================================

DO $$ BEGIN
    RAISE NOTICE 'Migration 013 applied: Robotic Herdsman Layer';
    RAISE NOTICE '  - devices.device_type now allows herding_robot';
    RAISE NOTICE '  - geofences gained shape/center/radius/buffer_m (circle + rectangle support)';
    RAISE NOTICE '  - herding_robots table (robot fleet registry)';
    RAISE NOTICE '  - herding_jobs table (assigned herding work units)';
    RAISE NOTICE '  - robot_telemetry hypertable (robot pose stream, 90d retention)';
END $$;
