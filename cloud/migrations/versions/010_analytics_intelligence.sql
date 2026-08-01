-- LivestockGuard Migration 010
-- Description: Analytics Intelligence — self-monitoring, learning & reporting
-- Tables: behaviour_baselines, anomalies, suggestions, intelligence_reports

-- ============================================================================
-- BEHAVIOUR BASELINES (updated nightly by analytics engine)
-- ============================================================================

CREATE TABLE IF NOT EXISTS behaviour_baselines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    animal_id UUID REFERENCES animals(id) ON DELETE CASCADE,  -- NULL = herd-level baseline
    metric_name VARCHAR(100) NOT NULL,
    baseline_value JSONB NOT NULL,
    window_days INT NOT NULL DEFAULT 7,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(farm_id, animal_id, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_baselines_farm ON behaviour_baselines(farm_id);
CREATE INDEX IF NOT EXISTS idx_baselines_animal ON behaviour_baselines(animal_id);

-- ============================================================================
-- ANOMALIES (detected by analytics engine)
-- ============================================================================

CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    animal_id UUID REFERENCES animals(id) ON DELETE CASCADE,
    anomaly_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    description TEXT NOT NULL,
    evidence JSONB NOT NULL,
    metadata JSONB,
    CONSTRAINT anomalies_valid_severity CHECK (severity IN ('low', 'medium', 'high')),
    CONSTRAINT anomalies_valid_status CHECK (status IN ('active', 'acknowledged', 'resolved', 'dismissed'))
);

CREATE INDEX IF NOT EXISTS idx_anomalies_farm_status ON anomalies(farm_id, status);
CREATE INDEX IF NOT EXISTS idx_anomalies_animal ON anomalies(animal_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected ON anomalies(detected_at DESC);

-- ============================================================================
-- SUGGESTIONS (actionable recommendations for farm admin)
-- ============================================================================

CREATE TABLE IF NOT EXISTS suggestions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    anomaly_id UUID REFERENCES anomalies(id) ON DELETE SET NULL,
    category VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    evidence JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    actioned_at TIMESTAMPTZ,
    actioned_by UUID REFERENCES users(id),
    CONSTRAINT suggestions_valid_priority CHECK (priority IN ('low', 'medium', 'high')),
    CONSTRAINT suggestions_valid_category CHECK (category IN ('health', 'security', 'operational', 'maintenance')),
    CONSTRAINT suggestions_valid_status CHECK (status IN ('pending', 'accepted', 'dismissed', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_suggestions_farm_status ON suggestions(farm_id, status);
CREATE INDEX IF NOT EXISTS idx_suggestions_priority ON suggestions(farm_id, priority, status);

-- ============================================================================
-- INTELLIGENCE REPORTS (daily/weekly compiled reports)
-- ============================================================================

CREATE TABLE IF NOT EXISTS intelligence_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    report_type VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    content JSONB NOT NULL,
    summary TEXT NOT NULL,
    anomaly_count INT NOT NULL DEFAULT 0,
    suggestion_count INT NOT NULL DEFAULT 0,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(farm_id, report_type, report_date),
    CONSTRAINT reports_valid_type CHECK (report_type IN ('daily', 'weekly'))
);

CREATE INDEX IF NOT EXISTS idx_reports_farm_date ON intelligence_reports(farm_id, report_date DESC);
