import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .routers import auth, devices, animals, geofences, alerts, analytics, farms
from .routers.websocket import router as ws_router
from .routers.notifications import router as notifications_router
from .routers.gateway import router as gateway_router
from .routers.system import router as system_router
from .routers.users import router as users_router
from .routers.assignments import router as assignments_router
from .routers.insights import router as insights_router
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
    import logging

    logger = logging.getLogger("livestockguard.security")

    # JWT secret validation — refuse to start in production with the default secret
    jwt_secret = os.environ.get("JWT_SECRET", "dev_secret_change_in_production")
    environment = os.environ.get("ENVIRONMENT", "development").lower()

    if jwt_secret == "dev_secret_change_in_production":
        if environment in ("production", "staging"):
            logger.critical(
                "FATAL: JWT_SECRET is set to the default development value in a %s environment. "
                "Refusing to start. Set a strong, unique JWT_SECRET.",
                environment,
            )
            raise SystemExit(1)
        else:
            logger.warning(
                "JWT_SECRET is using the default development value. "
                "This is acceptable for local development but MUST be changed before deployment."
            )

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

# ─── CORS Configuration (env-based) ───────────────────

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()

# Origins: configurable via env, with sensible defaults per environment
_default_dev_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:8082",
]
_default_prod_origins = [
    "https://app.livestockguard.co.za",
    "https://livestockguard.co.za",
]

_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    CORS_ORIGINS = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
elif ENVIRONMENT in ("production", "staging"):
    CORS_ORIGINS = _default_prod_origins
else:
    CORS_ORIGINS = _default_dev_origins + _default_prod_origins

# Methods & headers: restricted in production, open in dev
if ENVIRONMENT in ("production", "staging"):
    CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["Authorization", "Content-Type", "X-Request-ID", "Accept"]
else:
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)


# ─── Security Headers Middleware ──────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"

        # Only add HSTS and CSP in production/staging
        environment = os.environ.get("ENVIRONMENT", "development").lower()
        if environment in ("production", "staging"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: https:; "
                "frame-ancestors 'none'"
            )

        return response


app.add_middleware(SecurityHeadersMiddleware)

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
app.include_router(assignments_router, prefix=f"/api/{API_VERSION}/assignments", tags=["assignments"])
app.include_router(insights_router, prefix=f"/api/{API_VERSION}/insights", tags=["insights"])

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
app.include_router(assignments_router, prefix="/api/assignments", tags=["assignments"], include_in_schema=False)
app.include_router(insights_router, prefix="/api/insights", tags=["insights"], include_in_schema=False)

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
