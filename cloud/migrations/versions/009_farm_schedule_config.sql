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

-- Seed default schedule for Loch Vaal
INSERT INTO farm_schedule (farm_id, kraal_open_time, exit_gate_time, return_start_time, kraal_settle_time)
VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '08:30', '09:20', '16:30', '17:45')
ON CONFLICT (farm_id) DO NOTHING;

DO $$ BEGIN RAISE NOTICE 'Migration 009: farm_schedule table created'; END $$;
