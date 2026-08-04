---
inclusion: fileMatch
fileMatchPattern: "**/*.{ts,tsx}"
---

# TypeScript / React Patterns

When working on TypeScript files in this project, follow these patterns.

## Dashboard Structure (`dashboard/`)

```
dashboard/
├── package.json          # React 18, Vite 5, TypeScript 5.3
├── tsconfig.json         # strict: true
├── tailwind.config.js    # darkMode: 'class'
├── vite.config.ts
└── src/
    ├── main.tsx          # App entry, React Router setup
    ├── App.tsx           # Route definitions, layout wrapper
    ├── pages/            # Page components (one per route)
    │   ├── MapPage.tsx
    │   ├── AnimalsPage.tsx
    │   ├── AlertsPage.tsx
    │   ├── AnalyticsPage.tsx
    │   ├── DevicesPage.tsx
    │   ├── GeofencesPage.tsx
    │   └── GatewayPage.tsx
    ├── components/       # Shared UI components
    ├── stores/           # Zustand state stores
    │   ├── authStore.ts
    │   ├── mapStore.ts
    │   ├── realtimeStore.ts
    │   └── themeStore.ts
    ├── hooks/            # Custom React hooks
    │   └── useWebSocket.ts
    ├── api/              # Axios API client
    │   └── client.ts
    └── types/            # TypeScript interfaces
        └── index.ts
```

## State Management (Zustand)

```typescript
import { create } from 'zustand';

interface AuthState {
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  login: async (email, password) => { ... },
  logout: () => set({ token: null, user: null }),
}));
```

## Data Fetching (TanStack Query)

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function useAnimals(farmId: string) {
  return useQuery({
    queryKey: ['animals', farmId],
    queryFn: () => api.get(`/api/v1/animals?farm_id=${farmId}`).then(r => r.data),
    staleTime: 30_000,
  });
}
```

## Map (MapLibre GL JS)

- Use `maplibregl.Map` (not Leaflet)
- Tile sources: OpenStreetMap (street), Satellite, Terrain
- Animal markers as custom DOM elements or GeoJSON source + symbol layer
- Geofence polygons as fill + line layers
- Movement trails as line layers with date-based filtering

## Styling (TailwindCSS)

- Use utility classes directly in JSX
- Dark mode: always include `dark:` variants for colours
- No CSS modules or styled-components
- Framer Motion for animations (not CSS transitions for complex motion)

## Component Pattern

```tsx
import { motion } from 'framer-motion';

interface AnimalCardProps {
  animal: Animal;
  onClick?: () => void;
}

export function AnimalCard({ animal, onClick }: AnimalCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm"
      onClick={onClick}
    >
      <h3 className="font-medium text-gray-900 dark:text-white">
        {animal.name}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {animal.species} · {animal.status}
      </p>
    </motion.div>
  );
}
```

## API Client

```typescript
import axios from 'axios';

export const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

// Interceptor adds JWT token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

## WebSocket (Real-time)

- Connects to `ws://localhost:8000/ws` with JWT token as query param
- Receives: position updates, new alerts, device status changes
- Updates Zustand `realtimeStore` which triggers map marker re-renders

## Key Dependencies

| Package | Purpose |
|---------|---------|
| react 18 | UI framework |
| vite 5 | Build tool + dev server |
| typescript 5.3 | Type safety |
| tailwindcss 3.4 | Utility-first CSS |
| maplibre-gl 4 | Maps (open-source Mapbox fork) |
| zustand 4.5 | State management |
| @tanstack/react-query 5 | Server state + caching |
| recharts 2.10 | Charts (area, line, bar, donut) |
| framer-motion 11 | Animations |
| axios 1.6 | HTTP client |
| react-router-dom 6 | Client-side routing |
| clsx | Conditional classnames |

## E2E Tests (Playwright)

Located in `e2e/`:
- Config: `playwright.config.ts`
- Tests: `tests/features.spec.ts`
- Run: `cd e2e && npx playwright test`
- Requires dashboard + cloud stack running
