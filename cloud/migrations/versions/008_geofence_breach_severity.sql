-- LivestockGuard Migration 008
-- Add breach_severity to geofences for escalating alert levels per zone

ALTER TABLE geofences ADD COLUMN IF NOT EXISTS breach_severity VARCHAR(20) DEFAULT 'high'
    CHECK (breach_severity IN ('critical', 'high', 'medium', 'low', 'info'));

-- Set severity based on existing geofence names/purposes
-- Kraal at night = critical (potential theft)
-- Yard boundary = high (escaped property)
-- Range/area = medium (strayed far)
-- Dam exclusion = medium (safety concern)
UPDATE geofences SET breach_severity = 'critical' WHERE name ILIKE '%kraal%';
UPDATE geofences SET breach_severity = 'high' WHERE name ILIKE '%yard%' OR name ILIKE '%boundary%' OR name ILIKE '%border%';
UPDATE geofences SET breach_severity = 'medium' WHERE name ILIKE '%range%' OR name ILIKE '%area%' OR name ILIKE '%dam%';
UPDATE geofences SET breach_severity = 'high' WHERE name ILIKE '%entrance%' OR name ILIKE '%exit%';

DO $$ BEGIN RAISE NOTICE 'Migration 008: breach_severity added to geofences'; END $$;
