-- Notification preferences per user per farm
-- Controls which alert channels each user receives notifications on

CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,

    -- Channel toggles
    push_enabled BOOLEAN NOT NULL DEFAULT true,
    email_enabled BOOLEAN NOT NULL DEFAULT true,
    sms_enabled BOOLEAN NOT NULL DEFAULT false,
    webhook_enabled BOOLEAN NOT NULL DEFAULT false,

    -- Severity filter: minimum severity to notify (alerts below this are silent)
    -- Options: 'critical', 'high', 'medium', 'low', 'info'
    min_severity VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Quiet hours (no push/SMS during these hours, email still sends)
    quiet_start TIME,           -- e.g. '22:00'
    quiet_end TIME,             -- e.g. '06:00'

    -- Contact details (override user defaults)
    sms_phone VARCHAR(20),      -- E.164 format: +27821234567
    webhook_url TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, farm_id)
);

CREATE INDEX idx_notif_prefs_farm ON notification_preferences(farm_id);
CREATE INDEX idx_notif_prefs_user ON notification_preferences(user_id);
