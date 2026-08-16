# LivestockGuard — Improvement Roadmap

> Last updated: 2026-08-13
> Notifications (SES, FCM, SMS) deferred until AWS IAM setup.

---

## Priority Matrix

| Priority | Category | Description |
|----------|----------|-------------|
| P0 | Security | Must fix before any production exposure |
| P1 | Reliability | Core functionality gaps that affect trust |
| P2 | Quality | Test coverage, CI, code hardening |
| P3 | Features | User-facing improvements |
| P4 | Polish | Nice-to-haves, DX improvements |

---

## P0 — Security (Fix Immediately)

### 1. Insights router missing auth
- **File:** `cloud/services/api_gateway/app/routers/insights.py`
- **Issue:** Endpoints accessible without authentication — no `Depends(get_current_user)` applied
- **Risk:** Anomaly data, reports, suggestions exposed publicly
- **Fix:** Add auth dependency to all endpoints (same pattern as other routers)

### 2. JWT secret not validated at startup
- **File:** `cloud/services/api_gateway/app/main.py` / `dependencies.py`
- **Issue:** `JWT_SECRET` defaults to `"dev_secret_change_in_production"` with no warning/failure if unchanged
- **Fix:** Log a warning or refuse to start if secret matches the default in non-dev environments

### 3. Security headers missing
- **Issue:** No `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`
- **Fix:** Add security headers middleware (or use a package like `starlette-security-headers`)

### 4. CORS too permissive for production
- **File:** `cloud/services/api_gateway/app/main.py`
- **Issue:** `allow_methods=["*"]`, `allow_headers=["*"]` — fine for dev, risky for prod
- **Fix:** Restrict to actual methods used (GET, POST, PUT, PATCH, DELETE) and specific headers

---

## P1 — Reliability (Core Gaps)

### 5. Device command delivery not implemented
- **File:** `cloud/services/api_gateway/app/routers/devices.py` (line ~148)
- **Issue:** `POST /devices/{id}/command` accepts commands but never delivers to hardware (TODO in code)
- **Impact:** Remote commands (reboot, update config, set interval) are dead letters
- **Fix:** Publish to MQTT topic `lg/cmd/{device_id}` via Redis → MQTT bridge

### 6. Analytics engine has zero tests
- **Files:** `cloud/services/analytics_engine/app/jobs/`
- **Impact:** 4 complex jobs (baseline, anomaly, suggestion, report) with significant logic untested
- **Fix:** Add pytest suite with mocked DB, covering edge cases (no data, stale baselines, dedup)

### 7. MQTT writer has no integration tests
- **File:** `cloud/services/mqtt_writer/tests/`
- **Issue:** Protocol decoding is tested but actual DB write path is not
- **Fix:** Add tests that mock asyncpg and verify INSERT statements, geofence breach detection, Redis pub

### 8. Token revocation mechanism
- **Issue:** Refresh tokens are stateless — no way to invalidate a session (e.g., password change, logout-all)
- **Fix:** Add Redis-backed token blacklist checked on `/auth/refresh`

---

## P2 — Quality (Test & CI Hardening)

### 9. 7 API routers have no tests
- **Missing:** `gateway.py`, `notifications.py`, `farms.py`, `users.py`, `assignments.py`, `insights.py`, `system.py`
- **Priority order:** gateway (high traffic) > assignments (RBAC critical) > farms > users > insights > system > notifications (deferred)

### 10. Mobile app not in CI
- **Issue:** No build/type-check for mobile in GitHub Actions
- **Fix:** Add job: `cd mobile && npx tsc --noEmit` (same pattern as dashboard)

### 11. E2E tests not in CI
- **Issue:** 6 Playwright spec files exist but never run in pipeline
- **Fix:** Add CI job with Docker Compose stack + seeded data + Playwright (can be nightly, not on every push)

### 12. Python linting/type-checking not in CI
- **Issue:** No ruff, flake8, or mypy
- **Fix:** Add ruff (fast, covers both linting and formatting) to all Python services

### 13. Dependency security scanning
- **Issue:** No `pip-audit`, `npm audit`, or Dependabot configured
- **Fix:** Add Dependabot config + `pip-audit` step in CI

---

## P3 — Features (User-Facing)

### 14. Mobile app — Alerts screen
- **Gap:** Dashboard has a full alerts page; mobile shows nothing for alerts
- **Impact:** Farm owners on mobile miss breach/theft notifications in-app
- **Scope:** List view with severity badges, acknowledge/resolve actions, pull-to-refresh

### 15. Mobile app — Devices screen
- **Gap:** No device management on mobile (battery, signal, last seen)
- **Impact:** Herdsman can't check collar status in the field
- **Scope:** Simple list with status indicators, tap for detail

### 16. Mobile app — Geofences view (read-only)
- **Gap:** No geofence visibility on mobile (except on map)
- **Scope:** List of geofences with status, animal count inside/outside. Drawing stays desktop-only.

### 17. Dashboard — Bulk animal import (CSV)
- **Gap:** Animals added one-by-one currently
- **Impact:** Onboarding a farm with 200+ cattle is painful
- **Scope:** CSV upload → preview → confirm → batch insert

### 18. Dashboard — User management page
- **Gap:** API supports user CRUD + farm assignments, but no UI exists
- **Impact:** Admin must use API directly to add users or change roles
- **Scope:** Users table, invite flow, role assignment per farm

### 19. Offline-first mobile (queue + sync)
- **Gap:** Mobile BLE batches fail silently if offline
- **Impact:** Herdsman in poor-signal areas loses scan data
- **Scope:** Local queue in AsyncStorage, background sync when connectivity returns

---

## P4 — Polish & DX

### 20. Remove deprecated unversioned routes
- **Issue:** `/api/animals` still works — no deprecation timeline
- **Fix:** Add `Deprecation` header, log usage, plan removal after dashboard/mobile fully on v1

### 21. API response envelope consistency
- **Issue:** Some endpoints return raw arrays, others use `{"data": [...], "meta": {...}}`
- **Fix:** Audit all responses, standardize on envelope pattern

### 22. Password complexity validation
- **Issue:** No minimum length/character requirements on registration
- **Fix:** Add Pydantic validator (min 8 chars, at least one digit)

### 23. Account lockout after failed logins
- **Issue:** No brute-force protection beyond rate limiting
- **Fix:** Track failed attempts per email in Redis, lock for 15min after 5 failures

### 24. Database connection pooling tuning
- **Issue:** Default SQLAlchemy pool settings may not handle 50+ concurrent gateway batches
- **Fix:** Set `pool_size=20`, `max_overflow=30`, `pool_timeout=30` based on expected load

### 25. Structured logging (JSON)
- **Issue:** Plain text logs — harder to parse in CloudWatch/ELK
- **Fix:** Switch to `structlog` or `python-json-logger` across all services

### 26. API documentation improvements
- **Issue:** Swagger UI works but descriptions are sparse on some endpoints
- **Fix:** Add OpenAPI descriptions, examples, and response schema documentation

---

## Suggested Sprint Order

### Sprint 1 — Security & Critical Fixes (1-2 days)
- [ ] #1 Fix insights auth
- [ ] #2 JWT secret validation
- [ ] #3 Security headers
- [ ] #4 CORS tightening (env-based)

### Sprint 2 — Test Coverage (3-4 days)
- [ ] #6 Analytics engine tests
- [ ] #9 Gateway router tests
- [ ] #9 Assignments router tests
- [ ] #9 Farms router tests
- [ ] #10 Mobile CI job

### Sprint 3 — Mobile Feature Parity (3-5 days)
- [ ] #14 Mobile alerts screen
- [ ] #15 Mobile devices screen
- [ ] #16 Mobile geofences list

### Sprint 4 — Reliability & CI (2-3 days)
- [ ] #5 Device command delivery
- [ ] #7 MQTT writer integration tests
- [ ] #8 Token revocation
- [ ] #12 Python linting in CI

### Sprint 5 — Admin UX (3-4 days)
- [ ] #17 CSV animal import
- [ ] #18 User management page
- [ ] #19 Offline mobile queue

### Sprint 6 — Production Hardening (2 days)
- [ ] #11 E2E in CI (nightly)
- [ ] #13 Dependency scanning
- [ ] #20-26 Polish items

---

## Notes

- **Notifications (SES, FCM, Africa's Talking SMS):** Implementation exists and is tested. Activation deferred until AWS IAM credentials are configured.
- **Rust services (ingestion, geofence_engine):** Both have solid test coverage via `cargo test`. No immediate action needed.
- **Firmware:** Out of scope for this roadmap (hardware-dependent development cycle).
- **Analytics engine:** The 4-job pipeline is well-designed and functional — it just needs test coverage to be production-trustworthy.
