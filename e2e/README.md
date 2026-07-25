# E2E Tests

End-to-end testing for the LivestockGuard platform.

## Category 6: Stack Integration

Validates that all infrastructure services (PostgreSQL, Redis, EMQX) start correctly and the database schema + seed data is applied.

```bash
./e2e/run-integration.sh
```

Requires: Docker Compose

## Category 7: Dashboard E2E (Playwright)

Browser-based tests for the React dashboard.

### Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

### Run

```bash
# With auto-started dev server
npm test

# Headed (visible browser)
npm run test:headed

# Interactive UI mode
npm run test:ui

# View last report
npm run report
```

### Test Coverage

| File | Tests |
|------|-------|
| `auth.spec.ts` | Login page render, invalid credentials, successful login, redirect, theme toggle |
| `dashboard.spec.ts` | Sidebar navigation to all 6 pages |
| `theme.spec.ts` | Dark/light toggle, persistence across reload, localStorage |
| `map.spec.ts` | Map render, toolbar, layer toggles, tile sources, draw fence, status bar |
| `analytics.spec.ts` | Summary cards, charts, date picker, compliance table, Recharts SVGs |

### Prerequisites

- Dashboard dev server running on port 5173 (auto-started by Playwright config)
- API Gateway running on port 8000 (for login to work with real credentials)
- Or: run with mocked API responses for pure frontend testing
