# LivestockGuard Dashboard Specification

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 (Vite build) |
| Language | TypeScript (strict mode) |
| Mapping | MapLibre GL JS (open-source, self-hosted tiles) |
| Styling | TailwindCSS + Headless UI |
| State | Zustand (global) + React Query (server) |
| Mobile | React Native + Expo |
| Testing | Vitest + React Testing Library + Playwright (e2e) |

## Pages & Features

### Live Map (`/map`)
- Real-time animal positions with movement trails
- Geofence polygon overlay with breach highlighting
- Cluster markers for dense areas, expand on zoom
- Satellite/terrain/hybrid base layer toggle
- Click animal → info panel (name, status, battery, last seen)

### Animals (`/animals`)
- Sortable/filterable table (species, breed, status, group)
- Individual animal detail: movement history, health timeline, alerts
- Bulk operations: assign geofence, update group, export CSV
- SAMIC ID integration for national traceability

### Geofences (`/geofences`)
- Draw polygon on map (vertex editing, snap-to-boundary)
- Configure: name, alert type (breach/entry), grace period, active hours
- View animals currently inside/outside each fence
- Geofence templates for common shapes (paddock, kraal)

### Alerts (`/alerts`)
- Real-time feed with severity badges (critical, warning, info)
- Filter by type: breach, low-battery, no-signal, health, panic
- Acknowledge / resolve workflow with notes
- Escalation status indicator

### Analytics (`/analytics`)
- Grazing pattern heatmaps (daily/weekly)
- Activity breakdown per animal/herd (pie + time-series charts)
- Battery life predictions and replacement scheduling
- Movement distance summaries and anomaly flags

### Devices (`/devices`)
- Fleet overview: online/offline/low-battery counts
- Individual device: firmware version, signal strength, diagnostics
- OTA update management: schedule, monitor rollout progress
- Provisioning wizard for new device onboarding

### Settings (`/settings`)
- Organisation profile, farm boundaries, timezone
- User management (invite, roles, permissions)
- Notification preferences (channels, quiet hours, escalation rules)
- Billing and subscription management

## State Management

- **Zustand stores**: auth, UI preferences, active filters, map viewport
- **React Query**: Server state with automatic refetch, optimistic updates
- **WebSocket integration**: Real-time updates merged into React Query cache
- **Persistence**: Critical state to localStorage for offline resilience

## Real-Time Updates

- WebSocket connection per farm with automatic reconnect
- Incoming events: position updates, new alerts, device status changes
- Optimistic UI with server reconciliation
- Connection status indicator in header

## Internationalisation (i18n)

- **Languages**: English (default), Afrikaans, Zulu, Xhosa
- **Implementation**: react-i18next with lazy-loaded language bundles
- **Formatting**: Locale-aware dates, numbers, distances (km)
- **RTL**: Not required for supported languages

## Accessibility (WCAG 2.1 AA)

- Semantic HTML, ARIA labels on interactive map elements
- Keyboard navigable: all features accessible without mouse
- Colour contrast ≥ 4.5:1, colour-blind safe palettes
- Screen reader support for alerts and notifications
- Focus management on modal/dialog interactions

## Offline Capability

- Service Worker for asset caching (Workbox)
- IndexedDB for recent animal/alert data
- Offline map tiles (configurable region download)
- Queue mutations for sync when connectivity returns
- Visual indicator for offline/degraded state

## Mobile App (React Native)

- Shared business logic with web via shared TypeScript packages
- Native map (MapLibre Native) with offline region packs
- Push notifications via FCM/APNs
- Biometric auth (fingerprint/face)
- Camera integration for animal photo capture
