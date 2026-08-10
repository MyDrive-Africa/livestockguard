-- LivestockGuard Seed Data: Sibanyoni Farm
-- Location: North West Province, near Lichtenburg, South Africa
-- Centre: lat -25.3580560, lon 25.3612750
-- Area: 50 hectares (~707m x 707m)
-- Run: docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../scripts/seed_sibanyoni.sql

-- ============================================================================
-- ORGANISATION 3: Sibanyoni Farming (North West Province)
-- ============================================================================

INSERT INTO organisations (id, name, plan, max_devices) VALUES
    ('cccc1111-cccc-cccc-cccc-cccc11111111', 'Sibanyoni Farming', 'premium', 100)
ON CONFLICT DO NOTHING;

-- Farm: Sibanyoni Farm (North West, Lichtenburg area)
INSERT INTO farms (id, organisation_id, name, timezone, province, district, latitude, longitude, area_hectares, contact_name) VALUES
    ('cccc2222-cccc-cccc-cccc-cccc22222222', 'cccc1111-cccc-cccc-cccc-cccc11111111',
     'Sibanyoni Farm', 'Africa/Johannesburg',
     'North West', 'Ngaka Modiri Molema',
     -25.3580560, 25.3612750, 50.0,
     'Sibanyoni Family')
ON CONFLICT DO NOTHING;

-- User (password: demo123 — same bcrypt hash)
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('cccc3333-cccc-cccc-cccc-cccc33333333', 'cccc1111-cccc-cccc-cccc-cccc11111111',
     'sibanyoni@livestockguard.co.za',
     '$2b$12$l472OVKCboo1drRoOuzkl.H1uouXRVH7TCHvNZOwxWHt84wTs0Btu',
     'Sibanyoni Manager', 'owner')
ON CONFLICT DO NOTHING;

-- Also allow the main demo user to access this farm
INSERT INTO users (id, organisation_id, email, password_hash, full_name, role) VALUES
    ('cccc3334-cccc-cccc-cccc-cccc33333334', 'cccc1111-cccc-cccc-cccc-cccc11111111',
     'africa.mydrive@gmail.com',
     '$2b$12$l472OVKCboo1drRoOuzkl.H1uouXRVH7TCHvNZOwxWHt84wTs0Btu',
     'Johan van der Merwe', 'owner')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- DEVICES: 50 BLE ear tags for Sibanyoni Farm
-- ============================================================================

INSERT INTO devices (id, serial_number, device_type, firmware_version, farm_id, status, battery_level) VALUES
    ('cccc4444-cccc-cccc-cccc-cccc44440001', '3001', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 92),
    ('cccc4444-cccc-cccc-cccc-cccc44440002', '3002', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 88),
    ('cccc4444-cccc-cccc-cccc-cccc44440003', '3003', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 85),
    ('cccc4444-cccc-cccc-cccc-cccc44440004', '3004', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 91),
    ('cccc4444-cccc-cccc-cccc-cccc44440005', '3005', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 79),
    ('cccc4444-cccc-cccc-cccc-cccc44440006', '3006', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 94),
    ('cccc4444-cccc-cccc-cccc-cccc44440007', '3007', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 83),
    ('cccc4444-cccc-cccc-cccc-cccc44440008', '3008', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 87),
    ('cccc4444-cccc-cccc-cccc-cccc44440009', '3009', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 90),
    ('cccc4444-cccc-cccc-cccc-cccc44440010', '3010', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 86),
    ('cccc4444-cccc-cccc-cccc-cccc44440011', '3011', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 93),
    ('cccc4444-cccc-cccc-cccc-cccc44440012', '3012', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 81),
    ('cccc4444-cccc-cccc-cccc-cccc44440013', '3013', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 77),
    ('cccc4444-cccc-cccc-cccc-cccc44440014', '3014', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 89),
    ('cccc4444-cccc-cccc-cccc-cccc44440015', '3015', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 84),
    ('cccc4444-cccc-cccc-cccc-cccc44440016', '3016', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 95),
    ('cccc4444-cccc-cccc-cccc-cccc44440017', '3017', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 78),
    ('cccc4444-cccc-cccc-cccc-cccc44440018', '3018', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 82),
    ('cccc4444-cccc-cccc-cccc-cccc44440019', '3019', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 91),
    ('cccc4444-cccc-cccc-cccc-cccc44440020', '3020', 'eartag', '1.0.0', 'cccc2222-cccc-cccc-cccc-cccc22222222', 'active', 88)
ON CONFLICT DO NOTHING;
