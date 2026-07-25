-- Activity classification records
-- Stores inferred activity state for each animal over time intervals

CREATE TABLE IF NOT EXISTS activity_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    animal_id UUID NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,

    -- Classification result
    activity VARCHAR(20) NOT NULL,  -- 'grazing', 'resting', 'walking', 'running'
    confidence FLOAT NOT NULL DEFAULT 0.0,  -- 0.0 - 1.0

    -- Time window
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,

    -- Metrics used for classification
    avg_speed FLOAT,          -- km/h
    max_speed FLOAT,          -- km/h
    distance_m FLOAT,         -- meters traveled in window
    heading_variance FLOAT,   -- degrees variance (high = grazing)

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_animal_time ON activity_records(animal_id, started_at DESC);
CREATE INDEX idx_activity_farm_time ON activity_records(farm_id, started_at DESC);
CREATE INDEX idx_activity_type ON activity_records(activity);
