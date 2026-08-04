---
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# Python Backend Patterns

When working on Python files in this project, follow these patterns.

## Service Structure

Each Python service lives in `cloud/services/<name>/` with this layout:

```
cloud/services/<service_name>/
├── Dockerfile
├── requirements.txt
├── requirements-test.txt
├── pytest.ini
├── app/
│   ├── __init__.py
│   ├── main.py           # Entry point / FastAPI app
│   ├── config.py         # Settings from env vars
│   ├── db.py             # Database connection
│   ├── models.py         # SQLAlchemy models (if applicable)
│   ├── schemas.py        # Pydantic request/response schemas
│   └── routers/          # FastAPI route modules (api_gateway only)
└── tests/
    ├── __init__.py
    ├── conftest.py       # Shared fixtures
    └── test_*.py         # Test modules
```

## API Gateway Specifics

The API Gateway (`cloud/services/api_gateway/`) is the main REST service:

- **Framework**: FastAPI with async handlers
- **ORM**: SQLAlchemy 2.0 async (`AsyncSession`)
- **Auth**: JWT via `python-jose`, passwords via `passlib[bcrypt]`
- **Rate limiting**: `slowapi` backed by Redis
- **Spatial**: `geoalchemy2` + `shapely` for PostGIS geometry
- **Shared code**: `livestockguard_common` package (database engine, models)

### Router Pattern
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/")
async def list_items(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    ...
```

### Versioned Routes
- Primary: `/api/v1/<resource>`
- Deprecated: `/api/<resource>` (backward compat, `include_in_schema=False`)

## MQTT Writer Specifics

- Subscribes to EMQX topics: `lg/dev/+/pos`, `lg/dev/+/alert`, `lg/up/+/telemetry`
- Decodes binary protocol (struct.unpack) with CRC-16 verification
- Direct SQL via `asyncpg` (no ORM — performance critical)
- Publishes to Redis pub/sub for real-time WebSocket fan-out
- Detects theft (speed > 30 km/h) and geofence breaches (point-in-polygon)

## Alert Engine Specifics

- Subscribes to Redis channel `alerts:incoming`
- Uses dispatcher plugin pattern (`app/dispatchers/*.py`)
- Each dispatcher is a class with a `dispatch(event, ...)` method
- Dispatchers: `SESEmailDispatcher`, `FCMPushDispatcher`, `DashboardRedisDispatcher`, `WebhookDispatcher`, `AfricasTalkingSMSDispatcher`
- Cooldown: same device+alert_type won't re-fire within 300s

## Analytics Engine Specifics

- Uses APScheduler for periodic jobs
- Jobs in `app/jobs/` — each is a standalone async function
- Runs anomaly detection, daily reports, baseline calculations
- Config via env vars: `BASELINE_WINDOW_DAYS`, `ANOMALY_CHECK_INTERVAL_HOURS`, etc.

## Testing Pattern

```python
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_list_animals(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/animals", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
```

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.109.0 | Web framework |
| uvicorn | 0.27.0 | ASGI server |
| sqlalchemy[asyncio] | 2.0.25 | ORM (async) |
| asyncpg | 0.29.0 | PostgreSQL driver |
| pydantic | 2.5.3 | Data validation |
| python-jose | 3.3.0 | JWT tokens |
| passlib[bcrypt] | 1.7.4 | Password hashing |
| redis | 5.0.1 | Cache + pub/sub |
| geoalchemy2 | 0.14.3 | PostGIS integration |
| shapely | 2.0.2 | Geometry operations |
| boto3 | 1.34.25 | AWS SES |
| firebase-admin | 6.4.0 | FCM push |
| africastalking | 1.2.7 | SMS |
| paho-mqtt | 2.1.0 | MQTT client |

## Simulator Files

Simulators in `tools/simulator/` use:
- `paho-mqtt` for MQTT publishing
- `click` for CLI
- `struct.pack` for binary protocol encoding
- Farm presets: boschhoek, lochvaal, sibanyoni (with coordinates and device ID bases)
