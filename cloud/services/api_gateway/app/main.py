import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from .routers import auth, devices, animals, geofences, alerts, analytics, farms
from .routers.websocket import router as ws_router
from .routers.notifications import router as notifications_router
from .routers.gateway import router as gateway_router
from .routers.system import router as system_router
from .routers.users import router as users_router
from .metrics import metrics, add_metrics_middleware

# ─── Rate Limiter ─────────────────────────────────────

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT_STORAGE = os.environ.get("RATE_LIMIT_STORAGE", f"redis://{REDIS_URL}")

# Use in-memory storage if Redis is not available (dev mode)
try:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute", "50/second"],
        storage_uri=REDIS_URL,
    )
except Exception:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute", "50/second"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    from livestockguard_common.database import engine
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("Database connected")
    yield
    await engine.dispose()


# ─── App Setup ────────────────────────────────────────

API_VERSION = "v1"

app = FastAPI(
    title="LivestockGuard API",
    version="1.0.0",
    description="Backend API for LivestockGuard livestock monitoring platform",
    lifespan=lifespan,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8082",
        "https://app.livestockguard.co.za",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API v1 Routes (preferred) ────────────────────────

app.include_router(auth.router, prefix=f"/api/{API_VERSION}/auth", tags=["auth"])
app.include_router(farms.router, prefix=f"/api/{API_VERSION}/farms", tags=["farms"])
app.include_router(devices.router, prefix=f"/api/{API_VERSION}/devices", tags=["devices"])
app.include_router(animals.router, prefix=f"/api/{API_VERSION}/animals", tags=["animals"])
app.include_router(geofences.router, prefix=f"/api/{API_VERSION}/geofences", tags=["geofences"])
app.include_router(alerts.router, prefix=f"/api/{API_VERSION}/alerts", tags=["alerts"])
app.include_router(analytics.router, prefix=f"/api/{API_VERSION}/analytics", tags=["analytics"])
app.include_router(notifications_router, prefix=f"/api/{API_VERSION}/notifications", tags=["notifications"])
app.include_router(gateway_router, prefix=f"/api/{API_VERSION}/gateway", tags=["gateway"])
app.include_router(system_router, prefix=f"/api/{API_VERSION}/system", tags=["system"])
app.include_router(users_router, prefix=f"/api/{API_VERSION}/users", tags=["users"])

# ─── Backward-compatible unversioned routes (deprecated) ─

app.include_router(auth.router, prefix="/api/auth", tags=["auth"], include_in_schema=False)
app.include_router(farms.router, prefix="/api/farms", tags=["farms"], include_in_schema=False)
app.include_router(devices.router, prefix="/api/devices", tags=["devices"], include_in_schema=False)
app.include_router(animals.router, prefix="/api/animals", tags=["animals"], include_in_schema=False)
app.include_router(geofences.router, prefix="/api/geofences", tags=["geofences"], include_in_schema=False)
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"], include_in_schema=False)
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"], include_in_schema=False)
app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"], include_in_schema=False)
app.include_router(gateway_router, prefix="/api/gateway", tags=["gateway"], include_in_schema=False)
app.include_router(system_router, prefix="/api/system", tags=["system"], include_in_schema=False)
app.include_router(users_router, prefix="/api/users", tags=["users"], include_in_schema=False)

# WebSocket (unversioned — real-time endpoint)
app.include_router(ws_router, tags=["websocket"])


# ─── Public Endpoints ─────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api_gateway", "version": "1.0.0", "api_version": API_VERSION}


@app.get("/api/version")
async def api_version():
    """Return current API version and deprecation info."""
    return {
        "current_version": API_VERSION,
        "supported_versions": ["v1"],
        "deprecated_versions": [],
        "base_url": f"/api/{API_VERSION}",
        "note": "Unversioned /api/* routes are deprecated. Migrate to /api/v1/*.",
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return metrics.to_prometheus()


# Add metrics middleware (after routes so /metrics itself is excluded)
add_metrics_middleware(app)
