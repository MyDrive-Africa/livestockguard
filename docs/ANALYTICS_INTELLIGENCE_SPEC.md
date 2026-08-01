# Analytics Intelligence — Self-Monitoring, Learning & Reporting

## Overview

An analytics intelligence layer that continuously processes livestock tracking data, learns normal behaviour patterns, detects anomalies, and surfaces actionable insights and suggestions to the farm admin via the dashboard and notifications.

This is **not** a real-time alerting system (that already exists for theft/breach). This is a **pattern recognition and reporting engine** that runs on accumulated data — think daily/weekly farm health reports with specific, actionable suggestions.

---

## Target User

**Farm Admin** (dashboard + push notifications). The herdsman in the field does not interact with this system — they just walk and scan. The admin gets:

- Daily/weekly intelligence reports
- Anomaly flags with context ("why this matters")
- Prioritised suggestions with recommended actions
- Trend visualisation on the dashboard

---

## Core Capabilities

### 1. Behaviour Baselining (Learning)

Build a profile for each animal and the herd as a whole by observing patterns over time.

| What We Learn | Data Source | Baseline Period |
|---------------|-------------|-----------------|
| Normal grazing zones per animal | `ble_sightings` + `positions` | 7-14 days |
| Typical daily movement distance | `ble_sightings` (gateway GPS trail) | 7 days |
| Herd cohesion (who moves with whom) | Co-occurrence in BLE scans | 7 days |
| Time-of-day patterns (morning/afternoon zones) | Sighting timestamps + positions | 7 days |
| Watering point visit frequency | Proximity to known landmarks | 7 days |
| Herdsman patrol coverage and timing | `herdsman_sessions` | 7 days |

**Storage:** Baselines stored in a `behaviour_baselines` table, updated daily by a scheduled job.

### 2. Anomaly Detection

Compare current behaviour against learned baselines. Generate insights when deviations exceed configurable thresholds.

| Anomaly | Detection Logic | Severity | Possible Meaning |
|---------|----------------|----------|------------------|
| Animal isolated from herd | Not co-sighted with usual companions for >4h | Medium | Sick, injured, stuck in fence, calving |
| Reduced movement | Daily distance < 30% of baseline | Medium | Lameness, illness, late-stage pregnancy |
| Unusual location | Animal in zone never visited before (outside personal baseline) | Low-Medium | Exploring, fence gap, being pushed out |
| Missed watering | No proximity to water point in 24h (for animals that normally visit daily) | Medium | Blockage, dominance issue, illness |
| Herd split | Main herd fragmented into 3+ groups for >2h | Low | Normal grazing spread OR predator scatter |
| Night movement | Significant position change between 22:00-04:00 | High | Predator, theft attempt, fence break |
| Patrol gap | Herdsman didn't cover a farm zone in 3+ days | Low | Coverage blind spot |
| Gateway degradation | Fewer animals detected per patrol (declining trend) | Low | Tag battery dying, gateway BLE issue |

### 3. Reporting

#### Daily Farm Report (generated at configurable time, default 18:00)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SIBANYONI FARM — Daily Intelligence Report
 Wednesday 30 July 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 HERD STATUS
 ✓ 50/50 animals seen today (100% coverage)
 ✓ All animals within normal grazing zones
 ✓ Herd cohesion: normal (2 main groups, as usual)

 PATROL COVERAGE
 ✓ 1 patrol session (06:12 → 14:28, 8h16m)
 ✓ Coverage: North field ✓, East riverside ✓, South pasture ✓
 ⚠ West clearing: not visited in 2 days

 ANOMALIES DETECTED
 ⚠ SB-023 — Reduced movement (40% below baseline)
   Last 3 days: 1.2km, 0.9km, 0.8km (baseline: 2.1km/day)
   Suggestion: Check for lameness or illness

 ⚠ SB-041 — Isolated from herd for 5h (13:00-18:00)
   Usually moves with SB-038, SB-042, SB-044
   Suggestion: May be calving — confirm pregnancy status

 TRENDS (7-day)
 ↗ Average daily distance increasing (+12%) — seasonal grazing expansion
 → Watering visits stable (avg 2.1x per animal per day)
 ↘ Gateway battery declining (99% → 85%) — charge phone tonight

 SUGGESTIONS
 1. Schedule vet check for SB-023 (3-day declining movement)
 2. Visit west clearing tomorrow (coverage gap)
 3. Charge gateway device (battery trend)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Weekly Summary Report (generated Sunday evening)

- Week-over-week trends
- Animals that triggered anomalies (recurring vs one-off)
- Patrol efficiency (km walked per animal seen)
- Tag health (any tags with declining signal quality)
- Suggestions for the coming week

### 4. Suggestions Engine

Each suggestion has:
- **Priority**: high / medium / low
- **Category**: health, security, operational, maintenance
- **Action**: what the admin should do
- **Evidence**: data backing the suggestion
- **Expiry**: when the suggestion becomes stale

| Category | Example Suggestion | Priority |
|----------|-------------------|----------|
| Health | "SB-023 movement declining 3 days in a row. Schedule vet check." | High |
| Health | "SB-041 isolated 5h. Possible calving — verify pregnancy record." | Medium |
| Security | "Night movement detected for SB-007 at 02:30. Check CCTV/fence." | High |
| Operational | "West clearing not patrolled in 3 days. Route herdsman there." | Medium |
| Operational | "Morning patrol starting 45min later than last week. Discuss with herdsman." | Low |
| Maintenance | "Gateway battery declining — averaging 2%/day drain. Charge or replace." | Low |
| Maintenance | "SB-012 tag signal quality dropping (avg RSSI down 8dB over 2 weeks). Tag battery may be low." | Low |

---

## Architecture

### New Service: `analytics_engine`

A Python service that runs scheduled analysis jobs on the existing database. Not a real-time stream processor — it queries accumulated data.

```
cloud/services/analytics_engine/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py              # Scheduler entry point (APScheduler or cron-based)
│   ├── config.py            # Thresholds, schedule times, feature flags
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── baseline_builder.py    # Nightly: compute/update behaviour baselines
│   │   ├── anomaly_detector.py    # Hourly: compare current state to baselines
│   │   ├── report_generator.py    # Daily/weekly: build reports
│   │   └── suggestion_engine.py   # After anomaly detection: create actionable suggestions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baseline.py            # Behaviour baseline data models
│   │   ├── anomaly.py             # Anomaly event models
│   │   ├── insight.py             # Insight/suggestion models
│   │   └── report.py              # Report structure models
│   └── utils/
│       ├── stats.py               # Statistical helpers (z-score, moving average, std dev)
│       ├── spatial.py             # Clustering, co-occurrence, zone detection
│       └── time_patterns.py       # Time-of-day pattern analysis
└── tests/
    ├── __init__.py
    ├── test_baseline_builder.py
    ├── test_anomaly_detector.py
    └── test_suggestion_engine.py
```

### Scheduling

| Job | Frequency | Description |
|-----|-----------|-------------|
| `baseline_builder` | Nightly (02:00) | Recompute 7-day baselines for all animals |
| `anomaly_detector` | Every 2 hours | Check current state against baselines, flag deviations |
| `report_generator` | Daily (18:00), Weekly (Sunday 19:00) | Compile reports from anomalies + stats |
| `suggestion_engine` | After each anomaly detection run | Convert anomalies into prioritised suggestions |

### Database Additions

```sql
-- Migration 010: Analytics Intelligence

-- Behaviour baselines (updated nightly)
CREATE TABLE behaviour_baselines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    animal_id UUID REFERENCES animals(id) ON DELETE CASCADE,  -- NULL = herd-level baseline
    metric_name VARCHAR(100) NOT NULL,     -- 'daily_distance', 'herd_cohesion', 'watering_frequency', etc.
    baseline_value JSONB NOT NULL,          -- {mean, std_dev, min, max, percentiles, time_pattern}
    window_days INT NOT NULL DEFAULT 7,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(farm_id, animal_id, metric_name)
);

-- Detected anomalies
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    animal_id UUID REFERENCES animals(id) ON DELETE CASCADE,
    anomaly_type VARCHAR(100) NOT NULL,     -- 'isolated', 'reduced_movement', 'night_movement', etc.
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',  -- low, medium, high
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, acknowledged, resolved, dismissed
    description TEXT NOT NULL,
    evidence JSONB NOT NULL,                -- Supporting data (values, thresholds, comparisons)
    metadata JSONB,                         -- Extra context
    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high'))
);
CREATE INDEX idx_anomalies_farm_status ON anomalies(farm_id, status);
CREATE INDEX idx_anomalies_animal ON anomalies(animal_id);

-- Actionable suggestions
CREATE TABLE suggestions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    anomaly_id UUID REFERENCES anomalies(id),  -- Source anomaly (nullable for operational suggestions)
    category VARCHAR(50) NOT NULL,          -- health, security, operational, maintenance
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    evidence JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, accepted, dismissed, expired
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,                 -- Auto-expire stale suggestions
    actioned_at TIMESTAMPTZ,
    actioned_by UUID REFERENCES users(id),
    CONSTRAINT valid_priority CHECK (priority IN ('low', 'medium', 'high')),
    CONSTRAINT valid_category CHECK (category IN ('health', 'security', 'operational', 'maintenance'))
);
CREATE INDEX idx_suggestions_farm_status ON suggestions(farm_id, status);

-- Intelligence reports (daily/weekly)
CREATE TABLE intelligence_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    report_type VARCHAR(20) NOT NULL,       -- 'daily', 'weekly'
    report_date DATE NOT NULL,
    content JSONB NOT NULL,                 -- Full structured report data
    summary TEXT NOT NULL,                  -- Human-readable summary
    anomaly_count INT NOT NULL DEFAULT 0,
    suggestion_count INT NOT NULL DEFAULT 0,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(farm_id, report_type, report_date)
);
```

### API Endpoints (New)

Added to the API gateway:

```
GET    /api/analytics/insights?farm_id=...           # Active anomalies + suggestions
GET    /api/analytics/insights/{id}                  # Insight detail with evidence
PUT    /api/analytics/insights/{id}/acknowledge      # Mark as seen
PUT    /api/analytics/insights/{id}/dismiss          # Dismiss false positive

GET    /api/analytics/suggestions?farm_id=...        # Pending suggestions
PUT    /api/analytics/suggestions/{id}/accept        # Mark as actioned
PUT    /api/analytics/suggestions/{id}/dismiss       # Dismiss

GET    /api/analytics/reports?farm_id=...&type=daily # List reports
GET    /api/analytics/reports/{id}                   # Full report content
GET    /api/analytics/reports/latest?farm_id=...     # Most recent report

GET    /api/analytics/baselines?farm_id=...&animal_id=...  # View baselines (debug/transparency)
```

### Dashboard Integration

New sections in the admin dashboard:

1. **Insights Panel** (sidebar or dedicated page)
   - Active anomalies with severity badges
   - Pending suggestions with accept/dismiss actions
   - Trend arrows (improving/declining/stable)

2. **Daily Report View**
   - Structured report card (herd status, patrol coverage, anomalies, trends, suggestions)
   - Historical reports browsable by date

3. **Animal Detail Enhancement**
   - Baseline comparison chart (current vs normal)
   - Anomaly history for that animal
   - Health timeline

### Notification Integration

Intelligence reports and high-priority suggestions get dispatched through the existing alert engine channels:

| Priority | Channels |
|----------|----------|
| High (security, health) | Push + Email + Dashboard |
| Medium (operational) | Dashboard + Daily Report |
| Low (maintenance) | Daily Report only |

---

## Algorithm Details

### Daily Distance Calculation

```python
# Sum of distances between consecutive BLE sightings for an animal in a day
# Uses gateway GPS at time of each sighting as animal position
daily_distance = sum(
    haversine(sighting[i].gateway_lat, sighting[i].gateway_lon,
              sighting[i+1].gateway_lat, sighting[i+1].gateway_lon)
    for i in range(len(sightings) - 1)
    if time_diff(sighting[i], sighting[i+1]) < 2h  # Skip large gaps
)
```

### Herd Cohesion (Co-occurrence)

```python
# For each pair of animals, count how often they appear in the same
# gateway batch (within same 30s window) — high co-occurrence = companions
cohesion_matrix[animal_a][animal_b] = (
    count_co_sightings(animal_a, animal_b, window=60s) /
    min(total_sightings(animal_a), total_sightings(animal_b))
)
# Score 0.0 = never seen together, 1.0 = always together
```

### Isolation Detection

```python
# Animal is isolated if:
# 1. It was sighted (so we know where it is)
# 2. Its usual companions (cohesion > 0.6) were NOT sighted in same batch
# 3. This persists for > threshold hours (default: 4h)
```

### Movement Anomaly (Z-score)

```python
z_score = (today_distance - baseline_mean) / baseline_std_dev
if z_score < -2.0:  # More than 2 std devs below normal
    flag_anomaly("reduced_movement", severity="medium")
```

---

## Configuration

All thresholds configurable per farm (stored in `farm_settings` or a new config table):

```python
DEFAULTS = {
    "baseline_window_days": 7,
    "anomaly_check_interval_hours": 2,
    "daily_report_time": "18:00",
    "weekly_report_day": "sunday",
    "weekly_report_time": "19:00",

    # Anomaly thresholds
    "isolation_hours_threshold": 4,
    "reduced_movement_z_threshold": -2.0,
    "night_movement_start": "22:00",
    "night_movement_end": "04:00",
    "patrol_gap_days_threshold": 3,
    "watering_miss_hours": 24,

    # Herd cohesion
    "cohesion_companion_threshold": 0.6,  # Co-occurrence score to be "companions"
    "herd_split_min_groups": 3,
    "herd_split_duration_hours": 2,

    # Suggestions
    "suggestion_expiry_days": 7,
}
```

---

## Data Requirements

For meaningful baselines, the system needs:
- **Minimum 7 days** of BLE sighting data (at least 1 patrol/day)
- **Registered BLE tags** linked to animals (MAC resolution working)
- **Gateway operational** daily

The system should gracefully degrade:
- < 7 days data: report raw stats only, no anomaly detection
- < 3 days data: "Insufficient data for intelligence. Keep patrolling."
- Missed patrol day: note the gap, don't flag animals as anomalous

---

## Rollout Plan

### Phase 1: Foundation (prototype)
- Database migration (010)
- `baseline_builder` job (daily distance, basic stats)
- `anomaly_detector` (reduced movement only — simplest case)
- API endpoint: `GET /api/analytics/insights`
- Dashboard: basic insights panel

### Phase 2: Herd Intelligence
- Herd cohesion calculation
- Isolation detection
- Night movement detection
- Co-occurrence matrix
- Suggestions engine

### Phase 3: Full Reporting
- Daily report generator
- Weekly summary
- Report history view on dashboard
- Email dispatch of daily reports
- Trend visualisation (sparklines, period comparisons)

### Phase 4: Advanced
- Predictive health scoring (combine movement + isolation + watering)
- Calving prediction (isolation + reduced movement + known pregnancy)
- Optimal patrol route suggestion (based on coverage gaps)
- Tag battery prediction from RSSI degradation trends
- Seasonal pattern adjustment (winter vs summer baselines)

---

## Dependencies

- Existing `ble_sightings` hypertable (primary data source)
- Existing `herdsman_sessions` table (patrol data)
- Existing `positions` table (GPS collar data, if available)
- Existing alert engine (for dispatching high-priority suggestions)
- APScheduler or similar for job scheduling (lightweight, no Celery needed)
- NumPy/SciPy for statistical calculations (z-scores, std dev, clustering)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time to detect sick animal (vs manual observation) | Detect 1-2 days earlier |
| False positive rate on anomalies | < 20% after 30 days of learning |
| Admin engagement with suggestions | > 50% acknowledged or actioned |
| Coverage gaps identified | Reduce uncovered zones by 80% |
| Report usefulness (qualitative) | Admin finds report actionable |
