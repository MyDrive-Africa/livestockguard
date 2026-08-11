# Analytics Improvement Plan

## Current State Assessment

### Dashboard (`/analytics` page)

| What Exists | Status |
|-------------|--------|
| Movement distance chart (7-day line/area) | Hardcoded demo data |
| Activity breakdown donut (grazing/resting/walking/running) | Hardcoded demo data |
| Geofence breach bar chart | Hardcoded demo data |
| Battery trend line chart | Hardcoded demo data |
| Summary cards with sparklines | Hardcoded demo data |
| CSV export + Print/PDF | Works on demo data only |
| Date range picker (24h / 7d / 30d) | UI exists, no API integration |

### Backend (Fully Implemented)

| Component | Status |
|-----------|--------|
| Analytics Engine (APScheduler, 4 jobs) | Complete, running in Docker |
| Baseline Builder (nightly, 7-day window) | Complete |
| Anomaly Detector (every 2h, 4 detection types) | Complete |
| Suggestion Engine (actionable recs from anomalies) | Complete |
| Report Generator (daily 18:00, weekly Sunday 19:00) | Complete |
| Insights API (`/api/v1/insights/*`) — anomalies, suggestions, reports, baselines | Complete |
| Analytics API (`/api/v1/analytics/*`) — heatmap, activity, distance, compliance | Stub endpoints (return empty data) |
| Activity Classifier (`/api/v1/analytics/activity/classify/{id}`) | Complete with real DB query |

### Mobile App

| What Exists | Status |
|-------------|--------|
| AdminDashboard — stats grid + active alerts | Complete, but no analytics |
| MapScreen — animal positions | Complete |
| AnimalsScreen — animal list | Complete |
| HerdsmanScreen — BLE scanner + patrol | Complete |
| Analytics / Insights / Reports screen | Does not exist |

---

## Gap Analysis

### Critical Gaps

1. **Dashboard uses hardcoded data** — The analytics page doesn't call any API endpoint. The fully-implemented insights API goes unused.
2. **No Insights Panel on dashboard** — The spec calls for an active anomalies + suggestions panel. Not built.
3. **No Report Viewer on dashboard** — Daily/weekly intelligence reports are generated but never displayed.
4. **Analytics API stubs** — `/api/v1/analytics/heatmap`, `/activity`, `/distance`, `/compliance` return empty arrays.
5. **Zero mobile analytics** — No role gets any analytics, reports, or insights on mobile.

### Secondary Gaps

6. No animal-level baseline comparison chart (spec: "current vs normal")
7. No anomaly history on animal detail page
8. No trend arrows (improving/declining/stable) on the dashboard
9. No push notification integration for high-priority suggestions
10. No offline caching of reports for mobile viewing

---

## Improvement Plan

### Phase 1: Wire Dashboard to Real APIs

**Goal:** Replace hardcoded demo data with live API calls.

| Task | Details |
|------|---------|
| 1.1 Implement analytics API endpoints | Fill stub `/api/v1/analytics/heatmap`, `/activity`, `/distance`, `/compliance` with real TimescaleDB queries |
| 1.2 Create React hooks | `useHeatmap()`, `useActivity()`, `useDistance()`, `useCompliance()` using TanStack Query |
| 1.3 Wire AnalyticsPage to hooks | Replace hardcoded arrays with API data, handle loading/error states |
| 1.4 Respect date range picker | Pass `start`/`end` timestamps from the 24h/7d/30d selector to API calls |
| 1.5 Add farm selector | Analytics should be scoped to the active farm (from `mapStore` or new `farmStore`) |

### Phase 2: Add Insights Panel to Dashboard

**Goal:** Surface anomalies, suggestions, and reports in the web dashboard.

| Task | Details |
|------|---------|
| 2.1 Create `InsightsPage.tsx` (or panel) | New route `/insights` or sidebar panel on `/analytics` |
| 2.2 Active anomalies list | Severity badges, acknowledge/dismiss actions, evidence expandable |
| 2.3 Pending suggestions list | Priority badges, accept/dismiss, recommended action display |
| 2.4 Report viewer | Date-browsable daily/weekly reports, structured cards (herd status, patrol, anomalies, trends) |
| 2.5 Trend indicators | Up/down/flat arrows on summary cards using baseline comparison |
| 2.6 Animal detail enrichment | Baseline chart + anomaly history on the animal detail modal |

### Phase 3: Mobile Analytics for All Three Roles

**Goal:** Introduce an analytics/insights tab to the mobile app, role-tailored.

#### Navigation Change

Add a 5th tab: **"Insights"** (icon: 💡) — positioned between "Cattle" and "Scanner".

```
📊 Dashboard | 🗺️ Map | 🐄 Cattle | 💡 Insights | 📶 Scanner
```

For herdsman, replace "Insights" with a shift-relevant summary (no full analytics access per spec).

#### Role-Based Content

| Role | What They See on Insights Tab |
|------|-------------------------------|
| **Admin / Farm Owner** | Full insights: anomalies, suggestions, daily report summary, trend cards, animal health flags |
| **Viewer** | Read-only insights: anomalies (no dismiss), suggestions (no accept), reports |
| **Herdsman** | Simplified "Shift Summary": today's coverage %, missing cattle, patrol duration, any alerts for their farm |

#### Screens to Build

| Screen | File | Content |
|--------|------|---------|
| `InsightsScreen.tsx` | `mobile/src/screens/InsightsScreen.tsx` | Tab container with sub-sections |
| Anomalies section | Inline in InsightsScreen | Active anomalies with severity + description |
| Suggestions section | Inline in InsightsScreen | Pending suggestions with accept/dismiss (owner/admin only) |
| Report summary card | Inline in InsightsScreen | Latest daily report: herd %, patrol status, top anomaly |
| Trend indicators | Inline in InsightsScreen | Movement trend, coverage trend, battery trend |

#### Herdsman Shift Summary (Integrated into Scanner Tab)

Instead of a separate "Insights" tab, herdsman gets an expandable summary card at the top of their existing Scanner tab:

```
┌─── Today's Summary ─────────────────────┐
│ 📋 Coverage: 86% (43/50 unique tags)     │
│ 🕐 Patrol: 4h 22m active                │
│ ⚠️ 2 alerts on your farm today           │
│ → "SB-023 reduced movement"              │
│ → "West clearing not patrolled"          │
└──────────────────────────────────────────┘
```

### Phase 4: Complete the Analytics API

**Goal:** Make stub endpoints functional.

| Endpoint | Implementation |
|----------|---------------|
| `GET /analytics/heatmap` | Grid cell aggregation from `positions` hypertable with time bucketing |
| `GET /analytics/activity` | Classify positions per animal into grazing/resting/walking/running, aggregate by interval |
| `GET /analytics/distance` | Sum haversine distances between consecutive positions, grouped by day/hour |
| `GET /analytics/compliance` | Time inside vs outside geofence polygons using PostGIS `ST_Contains` |

### Phase 5: Polish & Production Readiness

| Task | Details |
|------|---------|
| Offline report caching (mobile) | Cache last 7 daily reports in AsyncStorage |
| Push notifications for suggestions | High-priority suggestions trigger FCM push to farm owner |
| Export from mobile | Share daily report as text/PDF via native share sheet |
| Dashboard dark mode for new insights panels | Ensure all new components respect `dark:` variants |
| Accessibility | ARIA labels on severity badges, keyboard navigation on dismiss/accept buttons |

---

## Priority Order (Recommended)

```
Phase 1 (Wire dashboard)     ← Immediate value, backend already done
Phase 3 (Mobile analytics)   ← Extends reach to field users
Phase 2 (Insights panel)     ← Rich dashboard experience
Phase 4 (API stubs)          ← Unlocks heatmap/distance/compliance charts
Phase 5 (Polish)             ← Production hardening
```

---

## Mobile Analytics — Detailed Design

### API Calls (Mobile)

```typescript
// Insights dashboard (combined)
GET /api/v1/insights/dashboard?farm_id={id}
→ { anomalies_active, anomalies_high, suggestions_pending, suggestions_high,
    latest_report_date, latest_report_summary, anomalies[], suggestions[] }

// Reports list
GET /api/v1/insights/reports?farm_id={id}&report_type=daily&limit=7

// Single report
GET /api/v1/insights/reports/{id}

// Accept/dismiss suggestion (owner/admin only)
PUT /api/v1/insights/suggestions/{id}/accept
PUT /api/v1/insights/suggestions/{id}/dismiss

// Acknowledge anomaly
PUT /api/v1/insights/anomalies/{id}/acknowledge
```

### Mobile Screen Wireframe (Owner/Admin)

```
┌─── Insights ─────────────────────────────────┐
│                                                │
│  Farm Intelligence                             │
│  [Loch Vaal Plot 30]                          │
│                                                │
│  ┌──────────┐  ┌──────────┐                  │
│  │ ⚠️ 3      │  │ 💡 5      │                  │
│  │ Anomalies │  │ Suggestions│                 │
│  │ (1 high)  │  │ (2 high)  │                  │
│  └──────────┘  └──────────┘                  │
│                                                │
│  📄 Latest Report: 10 Aug 2026               │
│  "All 10 cattle seen. 1 reduced movement      │
│   flagged. Patrol coverage 85%."              │
│  [View Full Report →]                         │
│                                                │
│  ─── Active Anomalies ───                     │
│  🔴 LV-001 — Night movement detected          │
│     02:30, moved 1.2km. Possible theft.        │
│     [Acknowledge]  [Dismiss]                   │
│                                                │
│  🟡 LV-005 — Reduced movement                 │
│     Today: 0.4km vs baseline 2.1km             │
│     [Acknowledge]  [Dismiss]                   │
│                                                │
│  ─── Suggestions ───                          │
│  🔴 HIGH: Schedule vet check for LV-005       │
│     "Movement declining 3 days in a row."      │
│     [Accept ✓]  [Dismiss ✗]                   │
│                                                │
│  🟡 MED: Visit north paddock tomorrow          │
│     "Not patrolled in 3 days."                 │
│     [Accept ✓]  [Dismiss ✗]                   │
│                                                │
└────────────────────────────────────────────────┘
```

### Herdsman View (Shift Summary — NOT a separate tab)

The herdsman does not get an "Insights" tab. Per the spec, herdsmen don't interact with the intelligence layer. Instead, relevant farm alerts are surfaced as a collapsible card on their existing Scanner tab.

```
┌─── Your Farm Today ───────────────────────────┐
│ ⚠️ 2 alerts active on Sibanyoni               │
│ • SB-023: Reduced movement (vet check needed) │
│ • West clearing: not visited in 3 days        │
│ [Tap to expand]                                │
└────────────────────────────────────────────────┘
```

This gives awareness without overwhelming the herdsman with analytics they can't action.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Dashboard analytics loads real data | 100% of charts connected to API |
| Time from anomaly detection to admin seeing it | < 5 minutes (real-time via WebSocket) |
| Mobile insights page load time | < 2 seconds on 3G |
| Suggestion accept/dismiss rate | > 60% actioned within 24h |
| Herdsman awareness of farm alerts | Card visible without extra taps |
| Report availability (mobile) | Last 7 daily reports cached offline |

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `mobile/src/screens/InsightsScreen.tsx` | Mobile insights tab (owner/admin/viewer) |
| `dashboard/src/pages/insights/InsightsPage.tsx` | Web dashboard insights page |
| `dashboard/src/hooks/useInsights.ts` | TanStack Query hooks for insights API |
| `dashboard/src/hooks/useAnalytics.ts` | TanStack Query hooks for analytics API |

### Modified Files

| File | Change |
|------|--------|
| `mobile/App.tsx` | Add 5th tab "Insights" (role-gated) |
| `mobile/src/screens/HerdsmanScreen.tsx` | Add collapsible "Your Farm Today" card |
| `dashboard/src/pages/analytics/AnalyticsPage.tsx` | Replace hardcoded data with API hooks |
| `dashboard/src/App.tsx` | Add `/insights` route |
| `cloud/services/api_gateway/app/routers/analytics.py` | Implement stub endpoints |
| `cloud/services/api_gateway/app/main.py` | Ensure insights router is mounted |
