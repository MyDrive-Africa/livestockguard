-- LivestockGuard Migration 004
-- Description: Add address/province/plot details to farms table for multi-location support

-- Physical address fields
ALTER TABLE farms ADD COLUMN IF NOT EXISTS province VARCHAR(100);
ALTER TABLE farms ADD COLUMN IF NOT EXISTS district VARCHAR(255);
ALTER TABLE farms ADD COLUMN IF NOT EXISTS plot_number VARCHAR(50);
ALTER TABLE farms ADD COLUMN IF NOT EXISTS address TEXT;

-- Farm coordinates (lat/lon as explicit columns for easy API access)
ALTER TABLE farms ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE farms ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

-- Farm size / area
ALTER TABLE farms ADD COLUMN IF NOT EXISTS area_hectares REAL;

-- Contact info for the farm manager on-site
ALTER TABLE farms ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255);
ALTER TABLE farms ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);

-- Index on province for regional queries
CREATE INDEX IF NOT EXISTS idx_farms_province ON farms(province);

-- Success
DO $$ BEGIN RAISE NOTICE 'Migration 004 applied: farm location details added'; END $$;
