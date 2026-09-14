-- LivestockGuard Migration 009
-- Farm schedule configuration (admin-configurable daily routine times)

CREATE TABLE IF NOT EXISTS farm_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    -- Morning routine
    kraal_open_time TIME NOT NULL DEFAULT '08:30',
    feeding_duration_min INT NOT NULL DEFAULT 50,      -- Minutes at feeding area
    exit_gate_time TIME NOT NULL DEFAULT '09:20',
    -- Evening routine
    return_start_time TIME NOT NULL DEFAULT '16:30',
    gate_enter_time TIME NOT NULL DEFAULT '17:00',
    water_stop_duration_min INT NOT NULL DEFAULT 20,
    kraal_settle_time TIME NOT NULL DEFAULT '17:45',
    -- Overnight
    night_mode VARCHAR(20) NOT NULL DEFAULT 'dry'      -- 'dry' (kraal) or 'wet' (yard)
        CHECK (night_mode IN ('dry', 'wet', 'auto')),
    -- Metadata
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(farm_id)
);

-- Seed default schedule for Loch Vaal — ONLY if that farm already exists.
-- Guard prevents this migration from aborting on a fresh database where farms
-- are not seeded until scripts/seed_data.sql runs later. (Without the guard the
-- FK violation halts the docker-entrypoint-initdb.d chain and later migrations
-- 010-013 never apply.) On a seeded DB, re-running seed_data.sql inserts the row.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM farms WHERE id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb') THEN
        INSERT INTO farm_schedule (farm_id, kraal_open_time, exit_gate_time, return_start_time, kraal_settle_time)
        VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '08:30', '09:20', '16:30', '17:45')
        ON CONFLICT (farm_id) DO NOTHING;
    END IF;
END $$;

DO $$ BEGIN RAISE NOTICE 'Migration 009: farm_schedule table created'; END $$;
