-- LivestockGuard — Robotic Herdsman demo seed
--
-- Registers a 4-robot herding fleet at Loch Vaal Plot 30 and gives the farm a
-- CIRCULAR containment boundary (centre + radius) so the Herding Orchestrator has
-- a shape to keep cattle inside. Safe to run repeatedly (ON CONFLICT DO NOTHING).
--
-- Prerequisite: migration 013 applied (herding_robots table + geofences.shape/
-- center_latitude/center_longitude/radius_m/buffer_m columns).
--
-- Loch Vaal farm_id: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb, centre (-26.719088, 27.709759)

-- ─── Circular containment boundary (200 m radius around the plot centre) ──────
-- A geometry is still required by the base schema (NOT NULL), so we store an
-- approximating square polygon AND the authoritative circle (shape/centre/radius).
-- The orchestrator uses the circle; the polygon is a fallback for older readers.
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach,
                       shape, center_latitude, center_longitude, radius_m, buffer_m) VALUES
    ('c1c1c1c1-0000-0000-0000-000000000001', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'Herding Boundary (200m circle)',
     ST_GeogFromText('POLYGON((27.70776 -26.72089, 27.71176 -26.72089, 27.71176 -26.71729, 27.70776 -26.71729, 27.70776 -26.72089))'),
     'inclusion', true, true,
     'circle', -26.719088, 27.709759, 200.0, 15.0)
ON CONFLICT (id) DO NOTHING;

-- ─── 4 herding robots, docked evenly around the boundary ──────────────────────
-- Home docks sit ~180 m from centre at N / E / S / W (0.9 * radius).
--   N: +180m lat  = -26.717471 ; E: +180m lon = 27.711566
--   S: -180m lat  = -26.720705 ; W: -180m lon = 27.707952
INSERT INTO herding_robots
    (id, farm_id, serial_number, name, model, status,
     last_latitude, last_longitude, home_latitude, home_longitude,
     battery_pct, max_speed_mps, capabilities) VALUES
    ('b0b07000-0000-0000-0000-000000000001', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'ROBO-LV-01', 'Herder 1', 'wheeled', 'patrolling',
     -26.717471, 27.709759, -26.717471, 27.709759, 100, 2.0, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-000000000002', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'ROBO-LV-02', 'Herder 2', 'wheeled', 'patrolling',
     -26.719088, 27.711566, -26.719088, 27.711566, 96, 2.0, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-000000000003', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'ROBO-LV-03', 'Herder 3', 'quadruped', 'patrolling',
     -26.720705, 27.709759, -26.720705, 27.709759, 91, 2.2, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-000000000004', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'ROBO-LV-04', 'Herder 4', 'wheeled', 'charging',
     -26.719088, 27.707952, -26.719088, 27.707952, 34, 2.0, '{"audio": true, "presence": true}')
ON CONFLICT (serial_number) DO NOTHING;

-- ═════════════════════════════════════════════════════════════════════════════
-- SIBANYONI FARM (North West) — 4-robot fleet + 400m circular boundary
-- ═════════════════════════════════════════════════════════════════════════════
-- Sibanyoni farm_id: dddddddd-1111-2222-3333-555555555555, centre (-25.358056, 25.361275)
-- Serials ROBO-SI-01..04 match robot_simulator.py's FARM_PRESETS["sibanyoni"]
-- (robot_prefix "SI"). The simulator uses --radius 400 for Sibanyoni, so the DB
-- boundary is a 400 m circle to match. Docks sit at 0.9*radius (360 m) from centre
-- at N / E / S / W, matching the simulator's even-bearing home layout.

-- ─── Circular containment boundary (400 m radius around the plot centre) ──────
INSERT INTO geofences (id, farm_id, name, geometry, fence_type, active, alert_on_breach,
                       shape, center_latitude, center_longitude, radius_m, buffer_m) VALUES
    ('c1c1c1c1-0000-0000-0000-000000000002', 'dddddddd-1111-2222-3333-555555555555',
     'Herding Boundary (400m circle)',
     ST_GeogFromText('POLYGON((25.35729 -25.36166, 25.36526 -25.36166, 25.36526 -25.35445, 25.35729 -25.35445, 25.35729 -25.36166))'),
     'inclusion', true, true,
     'circle', -25.358056, 25.361275, 400.0, 20.0)
ON CONFLICT (id) DO NOTHING;

-- ─── 4 herding robots, docked evenly (N/E/S/W) 360 m from centre ──────────────
--   N: +360m lat  = -25.354822 ; E: +360m lon = 25.364852
--   S: -360m lat  = -25.361290 ; W: -360m lon = 25.357698
INSERT INTO herding_robots
    (id, farm_id, serial_number, name, model, status,
     last_latitude, last_longitude, home_latitude, home_longitude,
     battery_pct, max_speed_mps, capabilities) VALUES
    ('b0b07000-0000-0000-0000-0000000000a1', 'dddddddd-1111-2222-3333-555555555555',
     'ROBO-SI-01', 'Herder 1', 'wheeled', 'patrolling',
     -25.354822, 25.361275, -25.354822, 25.361275, 100, 2.0, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-0000000000a2', 'dddddddd-1111-2222-3333-555555555555',
     'ROBO-SI-02', 'Herder 2', 'wheeled', 'patrolling',
     -25.358056, 25.364852, -25.358056, 25.364852, 94, 2.0, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-0000000000a3', 'dddddddd-1111-2222-3333-555555555555',
     'ROBO-SI-03', 'Herder 3', 'quadruped', 'patrolling',
     -25.361290, 25.361275, -25.361290, 25.361275, 88, 2.2, '{"audio": true, "presence": true}'),
    ('b0b07000-0000-0000-0000-0000000000a4', 'dddddddd-1111-2222-3333-555555555555',
     'ROBO-SI-04', 'Herder 4', 'wheeled', 'charging',
     -25.358056, 25.357698, -25.358056, 25.357698, 41, 2.0, '{"audio": true, "presence": true}')
ON CONFLICT (serial_number) DO NOTHING;

DO $$ BEGIN
    RAISE NOTICE 'Robotic herdsman seed loaded:';
    RAISE NOTICE '  Loch Vaal: 1 circular boundary (200m), 4 herding robots (ROBO-LV-01..04)';
    RAISE NOTICE '  Sibanyoni: 1 circular boundary (400m), 4 herding robots (ROBO-SI-01..04)';
END $$;
