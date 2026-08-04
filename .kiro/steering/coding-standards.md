# Coding Standards & Conventions

## Python (Backend Services)

### General
- **Version**: Python 3.12
- **Type hints**: Always use type annotations on function signatures
- **Docstrings**: Module-level and class-level docstrings explaining purpose
- **Imports**: stdlib → third-party → local (separated by blank lines)
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants

### FastAPI Patterns
- Use `async def` for all route handlers (asyncpg requires it)
- Use Pydantic models for request/response schemas
- Use dependency injection (`Depends()`) for auth, DB sessions, rate limiting
- Route files live in `app/routers/` — one file per domain (animals.py, alerts.py, etc.)
- Use `HTTPException` with appropriate status codes
- API responses follow consistent envelope: `{"data": ..., "meta": {...}}`

### SQLAlchemy
- Use SQLAlchemy 2.0 async style (`AsyncSession`, `select()`, `async with`)
- Models define `__tablename__` and use mapped columns
- Use `asyncpg` driver for PostgreSQL (connection string: `postgresql+asyncpg://...`)

### Testing
- Framework: pytest with `pytest-asyncio`
- Use in-memory SQLite for unit tests (no Docker dependency)
- Test files: `tests/test_*.py`
- Fixtures in `conftest.py`
- Run: `cd cloud/services/<service> && pytest -v`

### Alert Engine
- Dispatcher plugin pattern: each channel is a separate class in `app/dispatchers/`
- Alert events use dataclass `AlertEvent` with severity enum
- Cooldown mechanism prevents alert fatigue (default 300s per device+type)

## TypeScript / React (Dashboard)

### General
- **Strict mode**: `"strict": true` in tsconfig
- **No `any`**: Avoid `any` type — define proper interfaces in `src/types/`
- **File naming**: PascalCase for components (`MapPage.tsx`), camelCase for utilities (`useWebSocket.ts`)
- **Exports**: Named exports preferred over default exports

### React Patterns
- **State**: Zustand stores in `src/stores/` (not Redux, not Context for global state)
- **Data fetching**: TanStack React Query hooks in `src/hooks/`
- **API layer**: Axios client in `src/api/` — all endpoints centralized
- **Styling**: TailwindCSS utility classes, no CSS modules
- **Animations**: Framer Motion for page transitions and interactive elements
- **Maps**: MapLibre GL JS — use `maplibregl.Map`, not Leaflet
- **Routing**: React Router v6 with lazy loading

### Component Structure
```tsx
// Imports
import { motion } from 'framer-motion';
import { useAnimalStore } from '../stores/animalStore';

// Types (or import from types/)
interface Props { ... }

// Component
export function AnimalCard({ animal }: Props) {
  // hooks first
  // derived state
  // handlers
  // render
}
```

### Dark Mode
- Tailwind `darkMode: 'class'` — toggle via `themeStore`
- Always provide dark variants for custom colours

## Rust (Ingestion & Geofence Engine)

### General
- **Edition**: 2021
- **Async runtime**: Tokio (multi-threaded)
- **Error handling**: `anyhow` for applications, `thiserror` for libraries
- **Serialization**: serde + serde_json
- **Naming**: snake_case functions, PascalCase types, SCREAMING_SNAKE constants

### Patterns
- Use `#[tokio::main]` for async entry points
- Binary protocol decoding uses `byteorder` crate or manual byte slicing
- Geofence engine uses `rstar` R-tree for spatial indexing
- Tests: `#[cfg(test)] mod tests { ... }` inline, run with `cargo test`

## Firmware (C11 / Zephyr)

### General
- **Standard**: C11
- **Build**: CMake + nRF Connect SDK (Zephyr RTOS)
- **HAL**: Hardware Abstraction Layer in `hal/include/` — platform-independent interfaces
- **Naming**: `lg_` prefix for all public functions, snake_case

### Patterns
- State machine architecture (sleep → fix → transmit → sleep)
- Ring buffer for store-and-forward when offline
- CRC-16 CCITT for message integrity
- On-device geofencing via winding-number point-in-polygon

## Git Conventions

- **Branch naming**: `feature/<name>`, `fix/<name>`, `chore/<name>`
- **Commit messages**: Imperative mood, max 72 chars subject, body if needed
- **PR**: Always to `main`, squash-merge preferred
- **CI gate**: All jobs must pass before merge (api-gateway-tests, alert-engine-tests, mqtt-writer-tests, rust-tests, dashboard-build)
