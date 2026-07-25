-- LivestockGuard Migration 003
-- Description: Add detailed inventory fields to animals table
-- (gender, photo, description, colour, weight, status, lineage, lifecycle dates)

-- Gender
ALTER TABLE animals ADD COLUMN IF NOT EXISTS gender VARCHAR(10)
    CHECK (gender IN ('male', 'female'));

-- Physical description & identification
ALTER TABLE animals ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS colour VARCHAR(100);
ALTER TABLE animals ADD COLUMN IF NOT EXISTS weight_kg REAL;

-- Lifecycle status
ALTER TABLE animals ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'sold', 'deceased', 'transferred'));

-- Lineage (parent tracking for births)
ALTER TABLE animals ADD COLUMN IF NOT EXISTS mother_id UUID REFERENCES animals(id) ON DELETE SET NULL;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS father_id UUID REFERENCES animals(id) ON DELETE SET NULL;

-- Lifecycle dates
ALTER TABLE animals ADD COLUMN IF NOT EXISTS acquired_date DATE;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS removed_date DATE;
ALTER TABLE animals ADD COLUMN IF NOT EXISTS removal_reason TEXT;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_animals_status ON animals(status);
CREATE INDEX IF NOT EXISTS idx_animals_gender ON animals(gender);
CREATE INDEX IF NOT EXISTS idx_animals_mother ON animals(mother_id);
CREATE INDEX IF NOT EXISTS idx_animals_father ON animals(father_id);

-- Success
DO $$ BEGIN RAISE NOTICE 'Migration 003 applied: animal inventory fields added'; END $$;
