-- LivestockGuard Seed Data
-- Creates a demo farm with animals and devices for local testing
-- Run: make db-seed (or manually via psql)

-- Demo organisation
INSERT INTO organisations (id, name, plan, max_devices) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Boschhoek Farming', 'premium', 200)
ON CONFLICT DO NOTHING;

-- Demo farm (Free State, South Africa)
INSERT INTO farms (id, organisation_id, name, timezone) VALUES
    ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111',
     'Boschhoek Farm', 'Africa/Johannesburg')
ON CONFLICT DO NOTHING;

-- Demo user (password: demo123 — bcrypt hash)
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
     'johan@boschhoek.co.za',
     '$2b$12$LQv3c1yqBo9SkvXS7QTJPeJh0n6RSbGHfFQTRz3Pp8e/X5xKqYqHe',
     'Johan van der Merwe', 'owner')
ON CONFLICT DO NOTHING;

-- Demo devices (matching simulator device IDs 0x1000-0x1004)
INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('44444444-4444-4444-4444-444444444401', '1000', 'collar', '1.0.0',
     '22222222-2222-2222-2222-222222222222', 'active', 85),
    ('44444444-4444-4444-4444-444444444402', '1001', 'collar', '1.0.0',
     '22222222-2222-2222-2222-222222222222', 'active', 92),
    ('44444444-4444-4444-4444-444444444403', '1002', 'eartag', '1.0.0',
     '22222222-2222-2222-2222-222222222222', 'active', 78),
    ('44444444-4444-4444-4444-444444444404', '1003', 'eartag', '1.0.0',
     '22222222-2222-2222-2222-222222222222', 'active', 65),
    ('44444444-4444-4444-4444-444444444405', '1004', 'collar', '1.0.0',
     '22222222-2222-2222-2222-222222222222', 'active', 45)
ON CONFLICT DO NOTHING;

-- Demo animals
INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed) VALUES
    ('55555555-5555-5555-5555-555555555501', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444401', 'Bella', 'SA-2024-0042', 'cattle', 'Nguni'),
    ('55555555-5555-5555-5555-555555555502', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444402', 'Storm', 'SA-2024-0043', 'cattle', 'Brahman'),
    ('55555555-5555-5555-5555-555555555503', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444403', 'Thunder', 'SA-2024-0044', 'cattle', 'Bonsmara'),
    ('55555555-5555-5555-5555-555555555504', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444404', 'Daisy', 'SA-2024-0045', 'cattle', 'Nguni'),
    ('55555555-5555-5555-5555-555555555505', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444405', 'Rosie', 'SA-2024-0089', 'cattle', 'Jersey')
ON CONFLICT DO NOTHING;

-- Link devices back to animals
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555501' WHERE id = '44444444-4444-4444-4444-444444444401';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555502' WHERE id = '44444444-4444-4444-4444-444444444402';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555503' WHERE id = '44444444-4444-4444-4444-444444444403';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555504' WHERE id = '44444444-4444-4444-4444-444444444404';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555505' WHERE id = '44444444-4444-4444-4444-444444444405';

-- Demo geofence (polygon around farm centre: -29.12, 26.21)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active) VALUES
    ('66666666-6666-6666-6666-666666666601', '22222222-2222-2222-2222-222222222222',
     'Paddock North',
     ST_GeogFromText('POLYGON((26.200 -29.110, 26.220 -29.110, 26.220 -29.125, 26.200 -29.125, 26.200 -29.110))'),
     'inclusion', true),
    ('66666666-6666-6666-6666-666666666602', '22222222-2222-2222-2222-222222222222',
     'Paddock South',
     ST_GeogFromText('POLYGON((26.200 -29.125, 26.220 -29.125, 26.220 -29.140, 26.200 -29.140, 26.200 -29.125))'),
     'inclusion', true),
    ('66666666-6666-6666-6666-666666666603', '22222222-2222-2222-2222-222222222222',
     'Exclusion Zone (Dam)',
     ST_GeogFromText('POLYGON((26.208 -29.118, 26.212 -29.118, 26.212 -29.122, 26.208 -29.122, 26.208 -29.118))'),
     'exclusion', true)
ON CONFLICT DO NOTHING;

-- Success message
DO $$ BEGIN RAISE NOTICE 'Seed data loaded: 1 org, 1 farm, 1 user, 5 devices, 5 animals, 3 geofences'; END $$;
