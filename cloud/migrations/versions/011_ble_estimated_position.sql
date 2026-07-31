-- Migration 011: Add estimated animal position to BLE sightings
-- When the gateway/simulator can compute an individual position for each animal
-- (via triangulation, RSSI bearing estimation, or direct simulation), store it
-- separately from the gateway's own GPS coordinates.

ALTER TABLE ble_sightings
    ADD COLUMN estimated_latitude DOUBLE PRECISION,
    ADD COLUMN estimated_longitude DOUBLE PRECISION;

COMMENT ON COLUMN ble_sightings.estimated_latitude IS 'Estimated animal latitude (from RSSI trilateration or simulator). Falls back to gateway position if NULL.';
COMMENT ON COLUMN ble_sightings.estimated_longitude IS 'Estimated animal longitude (from RSSI trilateration or simulator). Falls back to gateway position if NULL.';
