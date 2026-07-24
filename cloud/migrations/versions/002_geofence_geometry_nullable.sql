-- LivestockGuard Migration 002
-- Make geofence geometry nullable to support ORM-first creation with subsequent geometry update

ALTER TABLE geofences ALTER COLUMN geometry DROP NOT NULL;
