-- User-Farm Assignments: role-based access control per farm
-- Version: 010
-- Description: Creates user_farm_assignments table linking users to specific farms
--              with a role_at_farm column. Supports the new role model:
--              - admin: org-level, sees all farms (no assignment needed)
--              - farm_owner: assigned to specific farm(s), full control within farm
--              - herdsman: assigned to a single farm, locked to BLE scanning
--              - viewer: read-only access to assigned farms

CREATE TABLE IF NOT EXISTS user_farm_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    role_at_farm VARCHAR(50) NOT NULL CHECK (role_at_farm IN ('farm_owner', 'herdsman', 'viewer')),
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,  -- NULL means active assignment
    UNIQUE(user_id, farm_id)
);

CREATE INDEX idx_user_farm_assign_user ON user_farm_assignments(user_id);
CREATE INDEX idx_user_farm_assign_farm ON user_farm_assignments(farm_id);
CREATE INDEX idx_user_farm_assign_active ON user_farm_assignments(user_id, farm_id) WHERE revoked_at IS NULL;

-- Update the users.role column to reflect new role set
-- Note: This is additive — existing 'owner' maps to 'admin', 'manager' maps to 'farm_owner'
-- Run data migration if needed:
--   UPDATE users SET role = 'admin' WHERE role = 'owner';
--   UPDATE users SET role = 'farm_owner' WHERE role = 'manager';

COMMENT ON TABLE user_farm_assignments IS 'Links users to specific farms with scoped roles. Admin users bypass this table and see all farms.';
COMMENT ON COLUMN user_farm_assignments.role_at_farm IS 'Role within this farm: farm_owner (full control), herdsman (BLE scanning only), viewer (read-only)';
COMMENT ON COLUMN user_farm_assignments.revoked_at IS 'When set, the assignment is inactive. NULL = currently active.';
