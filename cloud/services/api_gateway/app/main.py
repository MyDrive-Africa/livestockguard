import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add shared lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))

from .routers import auth, devices, animals, geofences, alerts, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Startup: verify DB connectivity
    from livestockguard_common.database import engine
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("Database connected")
    yield
    # Shutdown
    await engine.dispose()


from sqlalchemy import text

app = FastAPI(
    title="LivestockGuard API",
    version="1.0.0",
    description="Backend API for LivestockGuard livestock monitoring platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.livestockguard.co.za"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(animals.router, prefix="/api/animals", tags=["animals"])
app.include_router(geofences.router, prefix="/api/geofences", tags=["geofences"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api_gateway", "version": "1.0.0"}
