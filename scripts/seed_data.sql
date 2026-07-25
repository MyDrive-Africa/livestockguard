-- LivestockGuard Seed Data
-- Creates demo farms with animals and devices for local testing
-- Run: make db-seed (or manually via psql)

-- ============================================================================
-- ORGANISATION 1: Boschhoek Farming (Free State — existing demo)
-- ============================================================================

INSERT INTO organisations (id, name, plan, max_devices) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Boschhoek Farming', 'premium', 200)
ON CONFLICT DO NOTHING;

-- Farm: Boschhoek Farm (Free State, South Africa)
INSERT INTO farms (id, organisation_id, name, timezone, province, district, latitude, longitude, area_hectares) VALUES
    ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111',
     'Boschhoek Farm', 'Africa/Johannesburg',
     'Free State', 'Lejweleputswa', -29.12, 26.21, 450.0)
ON CONFLICT (id) DO UPDATE SET
    province = EXCLUDED.province,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    area_hectares = EXCLUDED.area_hectares;

-- Demo user (password: demo123 — bcrypt hash)
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
     'africa.mydrive@gmail.com',
     '$2b$12$l472OVKCboo1drRoOuzkl.H1uouXRVH7TCHvNZOwxWHt84wTs0Btu',
     'Johan van der Merwe', 'owner')
ON CONFLICT DO NOTHING;

-- Boschhoek devices (matching simulator device IDs 0x1000-0x1004)
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

-- Boschhoek animals (enhanced with gender, colour, descriptions)
INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('55555555-5555-5555-5555-555555555501', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444401', 'Bella', 'SA-2024-0042', 'cattle', 'Nguni',
     'female', 'Brown and white patterned', 'Mature Nguni cow, dominant in herd, distinctive brown-white patches on flanks',
     '2019-08-15', 420.0, 'active', '2021-03-01'),
    ('55555555-5555-5555-5555-555555555502', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444402', 'Storm', 'SA-2024-0043', 'cattle', 'Brahman',
     'male', 'Silver-grey', 'Large Brahman bull, hump prominent, silver-grey coat with darker head',
     '2018-04-22', 680.0, 'active', '2020-06-15'),
    ('55555555-5555-5555-5555-555555555503', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444403', 'Thunder', 'SA-2024-0044', 'cattle', 'Bonsmara',
     'male', 'Deep red', 'Young Bonsmara bull, solid deep red colour, muscular build',
     '2021-11-03', 550.0, 'active', '2022-01-10'),
    ('55555555-5555-5555-5555-555555555504', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444404', 'Daisy', 'SA-2024-0045', 'cattle', 'Nguni',
     'female', 'Black with white face', 'Nguni cow, black body with distinctive white face blaze, calm temperament',
     '2020-02-28', 380.0, 'active', '2021-03-01'),
    ('55555555-5555-5555-5555-555555555505', '22222222-2222-2222-2222-222222222222',
     '44444444-4444-4444-4444-444444444405', 'Rosie', 'SA-2024-0089', 'cattle', 'Jersey',
     'female', 'Fawn', 'Jersey dairy cow, small frame, fawn coat, dark muzzle, good milk production',
     '2019-12-10', 350.0, 'active', '2021-05-20')
ON CONFLICT (id) DO UPDATE SET
    gender = EXCLUDED.gender,
    colour = EXCLUDED.colour,
    description = EXCLUDED.description,
    date_of_birth = EXCLUDED.date_of_birth,
    weight_kg = EXCLUDED.weight_kg,
    status = EXCLUDED.status,
    acquired_date = EXCLUDED.acquired_date;

-- Link devices back to animals
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555501' WHERE id = '44444444-4444-4444-4444-444444444401';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555502' WHERE id = '44444444-4444-4444-4444-444444444402';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555503' WHERE id = '44444444-4444-4444-4444-444444444403';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555504' WHERE id = '44444444-4444-4444-4444-444444444404';
UPDATE devices SET animal_id = '55555555-5555-5555-5555-555555555505' WHERE id = '44444444-4444-4444-4444-444444444405';

-- Boschhoek geofences (polygon around farm centre: -29.12, 26.21)
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

-- ============================================================================
-- ORGANISATION 2: Loch Vaal Livestock (Vanderbijlpark, Gauteng)
-- ============================================================================

INSERT INTO organisations (id, name, plan, max_devices) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Loch Vaal Livestock', 'premium', 100)
ON CONFLICT DO NOTHING;

-- Farm: Plot 30, Loch Vaal, Vanderbijlpark
INSERT INTO farms (id, organisation_id, name, timezone, province, district, plot_number, address, latitude, longitude, area_hectares, contact_name, contact_phone) VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'Loch Vaal Plot 30', 'Africa/Johannesburg',
     'Gauteng', 'Sedibeng', '30',
     'Plot 30, Loch Vaal, Vanderbijlpark',
     -26.719088, 27.709759, 25.0,
     NULL, NULL)
ON CONFLICT DO NOTHING;

-- Loch Vaal user (password: demo123 — same bcrypt hash for dev)
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'lochvaal@livestockguard.co.za',
     '$2b$12$l472OVKCboo1drRoOuzkl.H1uouXRVH7TCHvNZOwxWHt84wTs0Btu',
     'Loch Vaal Manager', 'owner')
ON CONFLICT DO NOTHING;

-- Loch Vaal devices (device IDs 0x2000-0x2009 for 10 initial animals)
INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-dddd-dddd-dddd-dddddddddd01', '2000', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 90),
    ('dddddddd-dddd-dddd-dddd-dddddddddd02', '2001', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 88),
    ('dddddddd-dddd-dddd-dddd-dddddddddd03', '2002', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 85),
    ('dddddddd-dddd-dddd-dddd-dddddddddd04', '2003', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 92),
    ('dddddddd-dddd-dddd-dddd-dddddddddd05', '2004', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 87),
    ('dddddddd-dddd-dddd-dddd-dddddddddd06', '2005', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 91),
    ('dddddddd-dddd-dddd-dddd-dddddddddd07', '2006', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 83),
    ('dddddddd-dddd-dddd-dddd-dddddddddd08', '2007', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 79),
    ('dddddddd-dddd-dddd-dddd-dddddddddd09', '2008', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 94),
    ('dddddddd-dddd-dddd-dddd-dddddddddd10', '2009', 'eartag', '1.0.0', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'active', 86)
ON CONFLICT DO NOTHING;

-- Loch Vaal animals (10 initial cows — placeholder names until real inventory provided)
-- These represent the first 10 of ~50 cattle. Owner to provide real photos & descriptions.
INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd01', 'LV-001', 'LV-2025-001', 'cattle', 'Nguni',
     'female', 'Brown speckled', 'Nguni cow, brown speckled markings across body, medium frame',
     '2020-03-12', 400.0, 'active', '2023-01-15'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd02', 'LV-002', 'LV-2025-002', 'cattle', 'Nguni',
     'female', 'Black and white', 'Nguni cow, black and white piebald pattern, stocky build',
     '2019-07-20', 420.0, 'active', '2023-01-15'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd03', 'LV-003', 'LV-2025-003', 'cattle', 'Bonsmara',
     'female', 'Red-brown', 'Bonsmara cow, solid red-brown coat, good body condition',
     '2021-01-08', 450.0, 'active', '2023-02-01'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd04', 'LV-004', 'LV-2025-004', 'cattle', 'Brahman',
     'male', 'White-grey', 'Brahman bull, white-grey coat, large hump, used for breeding',
     '2018-11-25', 720.0, 'active', '2023-01-15'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd05', 'LV-005', 'LV-2025-005', 'cattle', 'Nguni',
     'female', 'Dun with black points', 'Nguni cow, dun coat with black legs and muzzle, lean build',
     '2020-09-14', 370.0, 'active', '2023-01-15'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd06', 'LV-006', 'LV-2025-006', 'cattle', 'Bonsmara',
     'female', 'Light red', 'Bonsmara cow, light red coat, white underbelly, calm temperament',
     '2021-05-30', 430.0, 'active', '2023-03-10'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee07', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd07', 'LV-007', 'LV-2025-007', 'cattle', 'Nguni',
     'female', 'Tricolour (black, white, brown)', 'Nguni cow, tricolour patterning, distinctive face markings',
     '2019-12-03', 390.0, 'active', '2023-01-15'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee08', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd08', 'LV-008', 'LV-2025-008', 'cattle', 'Brahman',
     'female', 'Light grey', 'Brahman cow, light grey coat, large ears, good maternal traits',
     '2020-06-17', 480.0, 'active', '2023-02-01'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee09', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd09', 'LV-009', 'LV-2025-009', 'cattle', 'Nguni',
     'male', 'Red with white spots', 'Young Nguni bull, red base coat with white spots, growing well',
     '2022-08-20', 380.0, 'active', '2023-06-01'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee10', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'dddddddd-dddd-dddd-dddd-dddddddddd10', 'LV-010', 'LV-2025-010', 'cattle', 'Bonsmara',
     'female', 'Dark red', 'Bonsmara cow, dark red coat, muscular, one of the herd leaders',
     '2019-04-10', 460.0, 'active', '2023-01-15')
ON CONFLICT DO NOTHING;

-- Link Loch Vaal devices to animals
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd01';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd02';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd03';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd04';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd05';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd06';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee07' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd07';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee08' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd08';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee09' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd09';
UPDATE devices SET animal_id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee10' WHERE id = 'dddddddd-dddd-dddd-dddd-dddddddddd10';

-- Loch Vaal geofence (boundary around Plot 30, ~500m radius from centre)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active) VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffffff', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Plot 30 Boundary',
     ST_GeogFromText('POLYGON((27.704 -26.715, 27.716 -26.715, 27.716 -26.723, 27.704 -26.723, 27.704 -26.715))'),
     'inclusion', true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Summary
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Seed data loaded:';
RAISE NOTICE '  Organisation 1: Boschhoek Farming (Free State) — 5 animals, 5 devices, 3 geofences';
RAISE NOTICE '  Organisation 2: Loch Vaal Livestock (Gauteng) — 10 animals, 10 devices, 1 geofence';
RAISE NOTICE '  Total: 2 orgs, 2 farms, 2 users, 15 devices, 15 animals, 4 geofences';
END $$;
