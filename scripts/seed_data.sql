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

-- Loch Vaal geofences — layered zones with escalating breach severity
-- Centre: -26.719088, 27.709759 (Plot 30)
--
-- Zone 1: KRAAL (night enclosure, ~50m radius) — breach = CRITICAL (theft)
-- Zone 2: YARD (2 hectare property boundary) — breach = HIGH (escaped yard)
-- Zone 3: RANGE (10km radius grazing area) — breach = MEDIUM (strayed far)
-- Outside Zone 3 = CRITICAL (likely stolen/lost)

-- Zone 1: Kraal (small enclosure near farmhouse, ~50m x 40m)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('ffffffff-ffff-ffff-ffff-fffffffffff1', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Kraal (Night Enclosure)',
     ST_GeogFromText('POLYGON((27.70926 -26.71879, 27.71026 -26.71879, 27.71026 -26.71939, 27.70926 -26.71939, 27.70926 -26.71879))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- Zone 2: Yard (2 hectare property — ~140m x 140m around centre)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('ffffffff-ffff-ffff-ffff-fffffffffff2', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Yard Boundary (2ha)',
     ST_GeogFromText('POLYGON((27.70876 -26.71809, 27.71076 -26.71809, 27.71076 -26.72009, 27.70876 -26.72009, 27.70876 -26.71809))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- Zone 3: Range (100km radius from Loch Vaal — covers surrounding districts)
-- 100km ≈ 0.9° latitude, 1.1° longitude at this latitude
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('ffffffff-ffff-ffff-ffff-fffffffffff3', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Loch Vaal Area (100km)',
     ST_GeogFromText('POLYGON((26.610 -25.819, 28.810 -25.819, 28.810 -27.619, 26.610 -27.619, 26.610 -25.819))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- Dam exclusion zone (within the yard — cattle should not enter)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('ffffffff-ffff-ffff-ffff-fffffffffff4', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Dam (Exclusion Zone)',
     ST_GeogFromText('POLYGON((27.70940 -26.71940, 27.70990 -26.71940, 27.70990 -26.71980, 27.70940 -26.71980, 27.70940 -26.71940))'),
     'exclusion', true, true)
ON CONFLICT DO NOTHING;

-- User-drawn geofences (Loch Vaal — exported from live database)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('e26eba79-9887-414e-891f-048eb6a52f9b', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Border',
     ST_GeogFromText('POLYGON((27.616674666767068 -26.68485012503193, 27.623865971464056 -26.756118718320025, 27.805703247375646 -26.755660050396564, 27.803819810430923 -26.683779226666736, 27.616674666767068 -26.68485012503193))'),
     'inclusion', true, true),
    ('07bc663a-7cfb-4ab3-8e19-bd70b8765e32', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Entrance/Exit',
     ST_GeogFromText('POLYGON((27.709901157106685 -26.718896335310276, 27.709978941168572 -26.718932272471996, 27.709981623377843 -26.718923887135972, 27.709911885942915 -26.718896335310276, 27.709901157106685 -26.718896335310276))'),
     'inclusion', true, true),
    ('2dd38843-68a5-4a7b-a128-77cf8ffa2936', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Loch Vaal Plot 30_2.1hct',
     ST_GeogFromText('POLYGON((27.7083816856547 -26.71826264148735, 27.70805445615528 -26.718856804420533, 27.710742029587465 -26.72005470412943, 27.71107998792405 -26.719417423053137, 27.7083816856547 -26.71826264148735))'),
     'inclusion', true, true),
    ('31050f97-a33e-47e8-9864-027983d421a3', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'TheKraal',
     ST_GeogFromText('POLYGON((27.708636602771236 -26.719099715517586, 27.70886226782764 -26.718845654442312, 27.70902446458703 -26.71890654516536, 27.708824656985968 -26.719194200897803, 27.708636602771236 -26.719099715517586))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- HERDSMAN GATEWAY & BLE TAGS (Loch Vaal)
-- ============================================================================

-- Gateway device (Teboho's phone)
INSERT INTO gateway_devices (id, farm_id, serial_number, name, device_type, herdsman_name, herdsman_phone, status) VALUES
    ('77777777-7777-7777-7777-777777777701', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'GW-LV-001', 'Teboho Phone', 'phone', 'Teboho Mpeki', '+27 82 555 1234', 'active')
ON CONFLICT DO NOTHING;

-- BLE ear tags linked to Loch Vaal animals
INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('88888888-8888-8888-8888-888888888801', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', 'A1:B2:C3:D4:E5:01', 'Tag-LV-001', 'active'),
    ('88888888-8888-8888-8888-888888888802', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02', 'A1:B2:C3:D4:E5:02', 'Tag-LV-002', 'active'),
    ('88888888-8888-8888-8888-888888888803', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03', 'A1:B2:C3:D4:E5:03', 'Tag-LV-003', 'active'),
    ('88888888-8888-8888-8888-888888888804', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', 'A1:B2:C3:D4:E5:04', 'Tag-LV-004', 'active'),
    ('88888888-8888-8888-8888-888888888805', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05', 'A1:B2:C3:D4:E5:05', 'Tag-LV-005', 'active'),
    ('88888888-8888-8888-8888-888888888806', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06', 'A1:B2:C3:D4:E5:06', 'Tag-LV-006', 'active'),
    ('88888888-8888-8888-8888-888888888807', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee07', 'A1:B2:C3:D4:E5:07', 'Tag-LV-007', 'active'),
    ('88888888-8888-8888-8888-888888888808', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee08', 'A1:B2:C3:D4:E5:08', 'Tag-LV-008', 'active'),
    ('88888888-8888-8888-8888-888888888809', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee09', 'A1:B2:C3:D4:E5:09', 'Tag-LV-009', 'active'),
    ('88888888-8888-8888-8888-888888888810', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee10', 'A1:B2:C3:D4:E5:10', 'Tag-LV-010', 'active')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Summary
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Seed data loaded:';
RAISE NOTICE '  Organisation 1: Boschhoek Farming (Free State) — 5 animals, 5 devices, 3 geofences';
RAISE NOTICE '  Organisation 2: Loch Vaal Livestock (Gauteng) — 10 animals, 10 devices, 4 geofences (kraal/yard/range/dam)';
RAISE NOTICE '  Total: 2 orgs, 2 farms, 2 users, 15 devices, 15 animals, 7 geofences';
END $$;

-- ============================================================================
-- ORGANISATION 3: Sibanyoni Farming (North West — Lichtenburg area)
-- ============================================================================

INSERT INTO organisations (id, name, plan, max_devices) VALUES
    ('dddddddd-1111-2222-3333-444444444444', 'Sibanyoni Farming', 'premium', 200)
ON CONFLICT DO NOTHING;

-- Farm: Sibanyoni Farm (North West Province, near Lichtenburg)
INSERT INTO farms (id, organisation_id, name, timezone, province, district, latitude, longitude, area_hectares, contact_name) VALUES
    ('dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-444444444444',
     'Sibanyoni Farm', 'Africa/Johannesburg',
     'North West', 'Ngaka Modiri Molema',
     -25.3580560, 25.3612750, 50.0,
     'Sibanyoni Family')
ON CONFLICT DO NOTHING;

-- Sibanyoni user (password: demo123 — same bcrypt hash for dev)
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('dddddddd-1111-2222-3333-666666666666', 'dddddddd-1111-2222-3333-444444444444',
     'sibanyoni@livestockguard.co.za',
     '$2b$12$l472OVKCboo1drRoOuzkl.H1uouXRVH7TCHvNZOwxWHt84wTs0Btu',
     'Sibanyoni Farm Manager', 'owner')
ON CONFLICT DO NOTHING;

-- Sibanyoni devices (50 ear tags, serial 3000-3049)
INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-1111-2222-3333-770000000001', '3000', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 90),
    ('dddddddd-1111-2222-3333-770000000002', '3001', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 88),
    ('dddddddd-1111-2222-3333-770000000003', '3002', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 85),
    ('dddddddd-1111-2222-3333-770000000004', '3003', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 92),
    ('dddddddd-1111-2222-3333-770000000005', '3004', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 87),
    ('dddddddd-1111-2222-3333-770000000006', '3005', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 91),
    ('dddddddd-1111-2222-3333-770000000007', '3006', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 83),
    ('dddddddd-1111-2222-3333-770000000008', '3007', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 79),
    ('dddddddd-1111-2222-3333-770000000009', '3008', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 94),
    ('dddddddd-1111-2222-3333-770000000010', '3009', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 86)
ON CONFLICT DO NOTHING;

INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-1111-2222-3333-770000000011', '3010', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 82),
    ('dddddddd-1111-2222-3333-770000000012', '3011', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 95),
    ('dddddddd-1111-2222-3333-770000000013', '3012', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 77),
    ('dddddddd-1111-2222-3333-770000000014', '3013', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 89),
    ('dddddddd-1111-2222-3333-770000000015', '3014', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 93),
    ('dddddddd-1111-2222-3333-770000000016', '3015', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 81),
    ('dddddddd-1111-2222-3333-770000000017', '3016', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 88),
    ('dddddddd-1111-2222-3333-770000000018', '3017', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 76),
    ('dddddddd-1111-2222-3333-770000000019', '3018', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 91),
    ('dddddddd-1111-2222-3333-770000000020', '3019', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 84)
ON CONFLICT DO NOTHING;

INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-1111-2222-3333-770000000021', '3020', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 90),
    ('dddddddd-1111-2222-3333-770000000022', '3021', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 87),
    ('dddddddd-1111-2222-3333-770000000023', '3022', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 92),
    ('dddddddd-1111-2222-3333-770000000024', '3023', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 78),
    ('dddddddd-1111-2222-3333-770000000025', '3024', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 85),
    ('dddddddd-1111-2222-3333-770000000026', '3025', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 93),
    ('dddddddd-1111-2222-3333-770000000027', '3026', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 80),
    ('dddddddd-1111-2222-3333-770000000028', '3027', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 86),
    ('dddddddd-1111-2222-3333-770000000029', '3028', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 91),
    ('dddddddd-1111-2222-3333-770000000030', '3029', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 88)
ON CONFLICT DO NOTHING;

INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-1111-2222-3333-770000000031', '3030', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 82),
    ('dddddddd-1111-2222-3333-770000000032', '3031', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 94),
    ('dddddddd-1111-2222-3333-770000000033', '3032', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 79),
    ('dddddddd-1111-2222-3333-770000000034', '3033', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 87),
    ('dddddddd-1111-2222-3333-770000000035', '3034', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 90),
    ('dddddddd-1111-2222-3333-770000000036', '3035', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 83),
    ('dddddddd-1111-2222-3333-770000000037', '3036', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 95),
    ('dddddddd-1111-2222-3333-770000000038', '3037', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 76),
    ('dddddddd-1111-2222-3333-770000000039', '3038', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 89),
    ('dddddddd-1111-2222-3333-770000000040', '3039', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 85)
ON CONFLICT DO NOTHING;

INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('dddddddd-1111-2222-3333-770000000041', '3040', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 91),
    ('dddddddd-1111-2222-3333-770000000042', '3041', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 84),
    ('dddddddd-1111-2222-3333-770000000043', '3042', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 88),
    ('dddddddd-1111-2222-3333-770000000044', '3043', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 77),
    ('dddddddd-1111-2222-3333-770000000045', '3044', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 93),
    ('dddddddd-1111-2222-3333-770000000046', '3045', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 80),
    ('dddddddd-1111-2222-3333-770000000047', '3046', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 86),
    ('dddddddd-1111-2222-3333-770000000048', '3047', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 92),
    ('dddddddd-1111-2222-3333-770000000049', '3048', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 81),
    ('dddddddd-1111-2222-3333-770000000050', '3049', 'eartag', '1.0.0', 'dddddddd-1111-2222-3333-555555555555', 'active', 87)
ON CONFLICT DO NOTHING;

-- Sibanyoni animals (50 cattle — mix of Nguni, Bonsmara, Brahman)
INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('dddddddd-1111-2222-3333-880000000001', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000001', 'SB-001', 'SB-2025-001', 'cattle', 'Nguni', 'female', 'Brown speckled', 'Nguni cow, mature, good condition', '2019-03-10', 410.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000002', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000002', 'SB-002', 'SB-2025-002', 'cattle', 'Nguni', 'female', 'Black and white', 'Nguni cow, piebald markings', '2020-06-22', 395.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000003', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000003', 'SB-003', 'SB-2025-003', 'cattle', 'Bonsmara', 'female', 'Red-brown', 'Bonsmara cow, solid build', '2021-01-15', 440.0, 'active', '2022-03-01'),
    ('dddddddd-1111-2222-3333-880000000004', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000004', 'SB-004', 'SB-2025-004', 'cattle', 'Brahman', 'male', 'White-grey', 'Brahman bull, breeding stock', '2018-09-05', 750.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000005', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000005', 'SB-005', 'SB-2025-005', 'cattle', 'Nguni', 'female', 'Dun with dark points', 'Nguni cow, lean build', '2020-04-18', 380.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000006', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000006', 'SB-006', 'SB-2025-006', 'cattle', 'Bonsmara', 'female', 'Light red', 'Bonsmara cow, calm temperament', '2021-07-20', 425.0, 'active', '2022-06-01'),
    ('dddddddd-1111-2222-3333-880000000007', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000007', 'SB-007', 'SB-2025-007', 'cattle', 'Nguni', 'female', 'Tricolour', 'Nguni cow, distinctive face markings', '2019-11-12', 400.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000008', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000008', 'SB-008', 'SB-2025-008', 'cattle', 'Brahman', 'female', 'Light grey', 'Brahman cow, good maternal traits', '2020-02-28', 490.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000009', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000009', 'SB-009', 'SB-2025-009', 'cattle', 'Nguni', 'male', 'Red with white spots', 'Young Nguni bull, growing well', '2022-05-10', 360.0, 'active', '2023-01-15'),
    ('dddddddd-1111-2222-3333-880000000010', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000010', 'SB-010', 'SB-2025-010', 'cattle', 'Bonsmara', 'female', 'Dark red', 'Bonsmara cow, herd leader', '2019-08-14', 460.0, 'active', '2022-01-15')
ON CONFLICT DO NOTHING;

INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('dddddddd-1111-2222-3333-880000000011', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000011', 'SB-011', 'SB-2025-011', 'cattle', 'Nguni', 'female', 'White with brown patches', 'Nguni cow, quiet disposition', '2020-01-20', 405.0, 'active', '2022-04-01'),
    ('dddddddd-1111-2222-3333-880000000012', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000012', 'SB-012', 'SB-2025-012', 'cattle', 'Bonsmara', 'female', 'Red', 'Bonsmara cow, excellent condition', '2021-03-08', 435.0, 'active', '2022-06-15'),
    ('dddddddd-1111-2222-3333-880000000013', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000013', 'SB-013', 'SB-2025-013', 'cattle', 'Brahman', 'male', 'Dark grey', 'Brahman bull, secondary breeding stock', '2019-12-01', 700.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000014', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000014', 'SB-014', 'SB-2025-014', 'cattle', 'Nguni', 'female', 'Black', 'Nguni cow, solid black coat', '2020-08-30', 390.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000015', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000015', 'SB-015', 'SB-2025-015', 'cattle', 'Nguni', 'female', 'Red-brown dappled', 'Nguni cow, distinctive dappled pattern', '2021-05-14', 385.0, 'active', '2022-08-01'),
    ('dddddddd-1111-2222-3333-880000000016', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000016', 'SB-016', 'SB-2025-016', 'cattle', 'Bonsmara', 'female', 'Medium red', 'Bonsmara cow, stocky build', '2019-06-22', 450.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000017', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000017', 'SB-017', 'SB-2025-017', 'cattle', 'Nguni', 'female', 'Cream and brown', 'Nguni cow, calm nature', '2020-10-10', 375.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000018', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000018', 'SB-018', 'SB-2025-018', 'cattle', 'Brahman', 'female', 'White', 'Brahman cow, large frame', '2020-04-05', 510.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000019', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000019', 'SB-019', 'SB-2025-019', 'cattle', 'Nguni', 'male', 'Black with white belly', 'Young Nguni bull, growing', '2022-02-18', 350.0, 'active', '2023-03-01'),
    ('dddddddd-1111-2222-3333-880000000020', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000020', 'SB-020', 'SB-2025-020', 'cattle', 'Bonsmara', 'female', 'Cherry red', 'Bonsmara cow, productive breeder', '2019-09-28', 445.0, 'active', '2022-01-15')
ON CONFLICT DO NOTHING;

INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('dddddddd-1111-2222-3333-880000000021', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000021', 'SB-021', 'SB-2025-021', 'cattle', 'Nguni', 'female', 'Spotted brown and cream', 'Nguni cow, good forager', '2020-07-15', 395.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000022', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000022', 'SB-022', 'SB-2025-022', 'cattle', 'Bonsmara', 'female', 'Russet', 'Bonsmara cow, heavy build', '2021-02-10', 470.0, 'active', '2022-05-01'),
    ('dddddddd-1111-2222-3333-880000000023', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000023', 'SB-023', 'SB-2025-023', 'cattle', 'Nguni', 'female', 'Grey speckled', 'Nguni cow, experienced mother', '2018-11-20', 420.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000024', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000024', 'SB-024', 'SB-2025-024', 'cattle', 'Nguni', 'female', 'Tan', 'Nguni cow, light tan coat', '2020-12-05', 380.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000025', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000025', 'SB-025', 'SB-2025-025', 'cattle', 'Brahman', 'female', 'Silver', 'Brahman cow, silver coat, gentle', '2019-05-30', 500.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000026', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000026', 'SB-026', 'SB-2025-026', 'cattle', 'Bonsmara', 'male', 'Deep red', 'Bonsmara bull, young breeding prospect', '2022-01-22', 520.0, 'active', '2023-06-01'),
    ('dddddddd-1111-2222-3333-880000000027', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000027', 'SB-027', 'SB-2025-027', 'cattle', 'Nguni', 'female', 'White with red ears', 'Nguni cow, white body, red ears', '2021-08-11', 370.0, 'active', '2022-10-01'),
    ('dddddddd-1111-2222-3333-880000000028', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000028', 'SB-028', 'SB-2025-028', 'cattle', 'Nguni', 'female', 'Brindle', 'Nguni cow, brindle pattern', '2020-03-25', 400.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000029', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000029', 'SB-029', 'SB-2025-029', 'cattle', 'Bonsmara', 'female', 'Auburn', 'Bonsmara cow, auburn coat', '2019-10-18', 440.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000030', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000030', 'SB-030', 'SB-2025-030', 'cattle', 'Nguni', 'female', 'Chocolate brown', 'Nguni cow, solid chocolate coat', '2021-04-07', 385.0, 'active', '2022-07-01')
ON CONFLICT DO NOTHING;

INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('dddddddd-1111-2222-3333-880000000031', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000031', 'SB-031', 'SB-2025-031', 'cattle', 'Nguni', 'female', 'Roan', 'Nguni cow, roan colouring', '2020-05-12', 395.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000032', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000032', 'SB-032', 'SB-2025-032', 'cattle', 'Brahman', 'female', 'Pale grey', 'Brahman cow, docile', '2019-07-28', 485.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000033', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000033', 'SB-033', 'SB-2025-033', 'cattle', 'Bonsmara', 'female', 'Copper', 'Bonsmara cow, copper sheen coat', '2021-09-03', 430.0, 'active', '2022-11-01'),
    ('dddddddd-1111-2222-3333-880000000034', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000034', 'SB-034', 'SB-2025-034', 'cattle', 'Nguni', 'female', 'Fawn and white', 'Nguni cow, fawn patches on white', '2020-11-16', 375.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000035', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000035', 'SB-035', 'SB-2025-035', 'cattle', 'Nguni', 'female', 'Red and white', 'Nguni cow, red-white piebald', '2019-02-14', 410.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000036', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000036', 'SB-036', 'SB-2025-036', 'cattle', 'Bonsmara', 'female', 'Brick red', 'Bonsmara cow, solid frame', '2021-06-29', 455.0, 'active', '2022-09-01'),
    ('dddddddd-1111-2222-3333-880000000037', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000037', 'SB-037', 'SB-2025-037', 'cattle', 'Nguni', 'female', 'Ivory', 'Nguni cow, near-white ivory coat', '2020-09-08', 365.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000038', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000038', 'SB-038', 'SB-2025-038', 'cattle', 'Nguni', 'male', 'Black with white face', 'Nguni bull, young, black body white face', '2022-04-20', 340.0, 'active', '2023-05-01'),
    ('dddddddd-1111-2222-3333-880000000039', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000039', 'SB-039', 'SB-2025-039', 'cattle', 'Brahman', 'female', 'Cream', 'Brahman cow, cream coat, large', '2019-04-15', 505.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000040', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000040', 'SB-040', 'SB-2025-040', 'cattle', 'Bonsmara', 'female', 'Tawny', 'Bonsmara cow, tawny coat, productive', '2020-01-30', 445.0, 'active', '2022-01-15')
ON CONFLICT DO NOTHING;

INSERT INTO animals (id, farm_id, device_id, name, tag_id, species, breed, gender, colour, description, date_of_birth, weight_kg, status, acquired_date) VALUES
    ('dddddddd-1111-2222-3333-880000000041', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000041', 'SB-041', 'SB-2025-041', 'cattle', 'Nguni', 'female', 'Mahogany', 'Nguni cow, deep mahogany colour', '2021-01-25', 390.0, 'active', '2022-04-01'),
    ('dddddddd-1111-2222-3333-880000000042', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000042', 'SB-042', 'SB-2025-042', 'cattle', 'Nguni', 'female', 'Smoky blue-grey', 'Nguni cow, unusual smoky colouring', '2020-06-10', 380.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000043', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000043', 'SB-043', 'SB-2025-043', 'cattle', 'Bonsmara', 'female', 'Sienna', 'Bonsmara cow, sienna-toned', '2019-08-22', 460.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000044', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000044', 'SB-044', 'SB-2025-044', 'cattle', 'Nguni', 'female', 'Golden brown', 'Nguni cow, golden coat in sunlight', '2021-10-14', 370.0, 'active', '2023-01-15'),
    ('dddddddd-1111-2222-3333-880000000045', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000045', 'SB-045', 'SB-2025-045', 'cattle', 'Brahman', 'female', 'Off-white', 'Brahman cow, off-white, hardy', '2020-03-17', 495.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000046', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000046', 'SB-046', 'SB-2025-046', 'cattle', 'Nguni', 'female', 'Patchy black-brown', 'Nguni cow, irregular patches', '2019-12-20', 400.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000047', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000047', 'SB-047', 'SB-2025-047', 'cattle', 'Bonsmara', 'female', 'Rust', 'Bonsmara cow, rusty red coat', '2021-08-05', 435.0, 'active', '2022-10-15'),
    ('dddddddd-1111-2222-3333-880000000048', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000048', 'SB-048', 'SB-2025-048', 'cattle', 'Nguni', 'female', 'Honey', 'Nguni cow, honey-coloured, sweet natured', '2020-07-30', 385.0, 'active', '2022-01-15'),
    ('dddddddd-1111-2222-3333-880000000049', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000049', 'SB-049', 'SB-2025-049', 'cattle', 'Nguni', 'male', 'Red roan', 'Nguni bull, red roan, strong build', '2022-06-12', 380.0, 'active', '2023-08-01'),
    ('dddddddd-1111-2222-3333-880000000050', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-770000000050', 'SB-050', 'SB-2025-050', 'cattle', 'Bonsmara', 'female', 'Terracotta', 'Bonsmara cow, terracotta coat, oldest in herd', '2017-11-30', 470.0, 'active', '2022-01-15')
ON CONFLICT DO NOTHING;

-- Sibanyoni geofences
-- Centre: -25.3580560, 25.3612750
-- 50ha ≈ 707m x 707m. At lat -25.36: 1° lat ≈ 110574m, 1° lon ≈ 100023m
-- Half-side lat: 0.0032, Half-side lon: 0.00354

-- Main property boundary (starter ~50ha rectangle — redraw on satellite)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('dddddddd-1111-2222-3333-990000000001', 'dddddddd-1111-2222-3333-555555555555',
     'Sibanyoni Farm Boundary (50ha)',
     ST_GeogFromText('POLYGON((25.35774 -25.35486, 25.36481 -25.35486, 25.36481 -25.36125, 25.35774 -25.36125, 25.35774 -25.35486))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- Kraal (night enclosure, ~60m x 50m near centre)
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('dddddddd-1111-2222-3333-990000000002', 'dddddddd-1111-2222-3333-555555555555',
     'Kraal (Night Enclosure)',
     ST_GeogFromText('POLYGON((25.36097 -25.35783, 25.36157 -25.35783, 25.36157 -25.35828, 25.36097 -25.35828, 25.36097 -25.35783))'),
     'inclusion', true, true)
ON CONFLICT DO NOTHING;

-- Dam exclusion zone
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach) VALUES
    ('dddddddd-1111-2222-3333-990000000003', 'dddddddd-1111-2222-3333-555555555555',
     'Dam (Exclusion Zone)',
     ST_GeogFromText('POLYGON((25.35900 -25.35900, 25.35980 -25.35900, 25.35980 -25.35960, 25.35900 -25.35960, 25.35900 -25.35900))'),
     'exclusion', true, true)
ON CONFLICT DO NOTHING;

-- Herdsman gateway (Sibanyoni)
INSERT INTO gateway_devices (id, farm_id, serial_number, name, device_type, herdsman_name, herdsman_phone, status) VALUES
    ('dddddddd-1111-2222-3333-aa0000000001', 'dddddddd-1111-2222-3333-555555555555',
     'GW-SB-001', 'Sibanyoni Phone', 'phone', 'Sibanyoni Herdsman', '+27 72 555 5678', 'active')
ON CONFLICT DO NOTHING;

-- Sibanyoni BLE ear tags (50 tags, MAC B1:C2:D3:E4:F5:01 through F5:50)
INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('dddddddd-1111-2222-3333-bb0000000001', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000001', 'B1:C2:D3:E4:F5:01', 'Tag-SB-001', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000002', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000002', 'B1:C2:D3:E4:F5:02', 'Tag-SB-002', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000003', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000003', 'B1:C2:D3:E4:F5:03', 'Tag-SB-003', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000004', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000004', 'B1:C2:D3:E4:F5:04', 'Tag-SB-004', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000005', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000005', 'B1:C2:D3:E4:F5:05', 'Tag-SB-005', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000006', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000006', 'B1:C2:D3:E4:F5:06', 'Tag-SB-006', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000007', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000007', 'B1:C2:D3:E4:F5:07', 'Tag-SB-007', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000008', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000008', 'B1:C2:D3:E4:F5:08', 'Tag-SB-008', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000009', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000009', 'B1:C2:D3:E4:F5:09', 'Tag-SB-009', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000010', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000010', 'B1:C2:D3:E4:F5:10', 'Tag-SB-010', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('dddddddd-1111-2222-3333-bb0000000011', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000011', 'B1:C2:D3:E4:F5:11', 'Tag-SB-011', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000012', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000012', 'B1:C2:D3:E4:F5:12', 'Tag-SB-012', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000013', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000013', 'B1:C2:D3:E4:F5:13', 'Tag-SB-013', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000014', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000014', 'B1:C2:D3:E4:F5:14', 'Tag-SB-014', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000015', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000015', 'B1:C2:D3:E4:F5:15', 'Tag-SB-015', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000016', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000016', 'B1:C2:D3:E4:F5:16', 'Tag-SB-016', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000017', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000017', 'B1:C2:D3:E4:F5:17', 'Tag-SB-017', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000018', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000018', 'B1:C2:D3:E4:F5:18', 'Tag-SB-018', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000019', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000019', 'B1:C2:D3:E4:F5:19', 'Tag-SB-019', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000020', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000020', 'B1:C2:D3:E4:F5:20', 'Tag-SB-020', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('dddddddd-1111-2222-3333-bb0000000021', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000021', 'B1:C2:D3:E4:F5:21', 'Tag-SB-021', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000022', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000022', 'B1:C2:D3:E4:F5:22', 'Tag-SB-022', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000023', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000023', 'B1:C2:D3:E4:F5:23', 'Tag-SB-023', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000024', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000024', 'B1:C2:D3:E4:F5:24', 'Tag-SB-024', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000025', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000025', 'B1:C2:D3:E4:F5:25', 'Tag-SB-025', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000026', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000026', 'B1:C2:D3:E4:F5:26', 'Tag-SB-026', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000027', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000027', 'B1:C2:D3:E4:F5:27', 'Tag-SB-027', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000028', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000028', 'B1:C2:D3:E4:F5:28', 'Tag-SB-028', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000029', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000029', 'B1:C2:D3:E4:F5:29', 'Tag-SB-029', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000030', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000030', 'B1:C2:D3:E4:F5:30', 'Tag-SB-030', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('dddddddd-1111-2222-3333-bb0000000031', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000031', 'B1:C2:D3:E4:F5:31', 'Tag-SB-031', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000032', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000032', 'B1:C2:D3:E4:F5:32', 'Tag-SB-032', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000033', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000033', 'B1:C2:D3:E4:F5:33', 'Tag-SB-033', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000034', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000034', 'B1:C2:D3:E4:F5:34', 'Tag-SB-034', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000035', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000035', 'B1:C2:D3:E4:F5:35', 'Tag-SB-035', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000036', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000036', 'B1:C2:D3:E4:F5:36', 'Tag-SB-036', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000037', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000037', 'B1:C2:D3:E4:F5:37', 'Tag-SB-037', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000038', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000038', 'B1:C2:D3:E4:F5:38', 'Tag-SB-038', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000039', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000039', 'B1:C2:D3:E4:F5:39', 'Tag-SB-039', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000040', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000040', 'B1:C2:D3:E4:F5:40', 'Tag-SB-040', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO ble_ear_tags (id, farm_id, animal_id, mac_address, tag_name, status) VALUES
    ('dddddddd-1111-2222-3333-bb0000000041', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000041', 'B1:C2:D3:E4:F5:41', 'Tag-SB-041', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000042', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000042', 'B1:C2:D3:E4:F5:42', 'Tag-SB-042', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000043', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000043', 'B1:C2:D3:E4:F5:43', 'Tag-SB-043', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000044', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000044', 'B1:C2:D3:E4:F5:44', 'Tag-SB-044', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000045', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000045', 'B1:C2:D3:E4:F5:45', 'Tag-SB-045', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000046', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000046', 'B1:C2:D3:E4:F5:46', 'Tag-SB-046', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000047', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000047', 'B1:C2:D3:E4:F5:47', 'Tag-SB-047', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000048', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000048', 'B1:C2:D3:E4:F5:48', 'Tag-SB-048', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000049', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000049', 'B1:C2:D3:E4:F5:49', 'Tag-SB-049', 'active'),
    ('dddddddd-1111-2222-3333-bb0000000050', 'dddddddd-1111-2222-3333-555555555555', 'dddddddd-1111-2222-3333-880000000050', 'B1:C2:D3:E4:F5:50', 'Tag-SB-050', 'active')
ON CONFLICT DO NOTHING;

-- Update summary
DO $$ BEGIN RAISE NOTICE 'Sibanyoni Farm seed data loaded:';
RAISE NOTICE '  Organisation 3: Sibanyoni Farming (North West) — 50 animals, 50 devices, 3 geofences, 1 gateway';
RAISE NOTICE '  Login: sibanyoni@livestockguard.co.za / demo123';
RAISE NOTICE '  Farm ID: dddddddd-1111-2222-3333-555555555555';
RAISE NOTICE '  Gateway: GW-SB-001';
RAISE NOTICE '  BLE MACs: B1:C2:D3:E4:F5:01 through F5:50';
END $$;


-- ═══════════════════════════════════════════════════════════════════
-- USER-FARM ASSIGNMENTS
-- Links users to specific farms for the farm picker / RBAC system
-- ═══════════════════════════════════════════════════════════════════

-- Main demo user (africa.mydrive@gmail.com) gets access to all 3 farms
INSERT INTO user_farm_assignments (user_id, farm_id, role_at_farm) VALUES
    ('33333333-3333-3333-3333-333333333333', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'farm_owner'),
    ('33333333-3333-3333-3333-333333333333', 'dddddddd-1111-2222-3333-555555555555', 'farm_owner'),
    ('33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'farm_owner')
ON CONFLICT (user_id, farm_id) DO NOTHING;

-- Loch Vaal user — assigned to Loch Vaal Plot 30
INSERT INTO user_farm_assignments (user_id, farm_id, role_at_farm) VALUES
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'farm_owner')
ON CONFLICT (user_id, farm_id) DO NOTHING;

-- Sibanyoni user — assigned to Sibanyoni Farm
INSERT INTO user_farm_assignments (user_id, farm_id, role_at_farm) VALUES
    ('dddddddd-1111-2222-3333-666666666666', 'dddddddd-1111-2222-3333-555555555555', 'farm_owner')
ON CONFLICT (user_id, farm_id) DO NOTHING;
