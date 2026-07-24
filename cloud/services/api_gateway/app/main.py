from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, devices, animals, geofences, alerts, analytics

app = FastAPI(
    title="LivestockGuard API",
    version="1.0.0",
    description="Backend API for LivestockGuard livestock monitoring platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {"status": "healthy", "service": "api_gateway"}
