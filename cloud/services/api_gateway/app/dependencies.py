"""
FastAPI dependencies for database sessions and auth.

Role model:
  - admin: Org-level superuser, sees all farms, manages everything
  - farm_owner: Full control within assigned farm(s)
  - herdsman: Locked to assigned farm, BLE scanning only
  - viewer: Read-only access to assigned farms
"""

import os
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from livestockguard_common.database import async_session_factory
from livestockguard_common.db_models import Farm, User, UserFarmAssignment

# ─── Auth Configuration ───────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_in_production")
JWT_ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)

# Role hierarchy: higher number = more privileges at org level
ROLE_HIERARCHY = {
    "admin": 4,
    "farm_owner": 3,
    "herdsman": 2,
    "viewer": 1,
}


# ─── Database Dependency ──────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Auth Dependency ──────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate JWT Bearer token and return the user payload.

    Returns dict with keys: user_id, email, role, organisation_id.
    Raises 401 if token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "viewer"),
            "organisation_id": payload.get("organisation_id"),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Role-Based Access Control ────────────────────────

def require_role(required_role: str):
    """
    Dependency factory: require the user's org-level role to be at or above
    the required level. Use for org-wide actions (e.g. create farm, manage users).
    """
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(user["role"], 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher",
            )
        return user
    return checker


# ─── Farm-Scoped Access Control ───────────────────────

async def get_user_farms(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Return the list of farms this user can access.

    - admin: all farms in their organisation
    - farm_owner / herdsman / viewer: only farms with active assignment
    """
    user_id = user["user_id"]
    role = user["role"]

    if role == "admin":
        # Admin sees all farms in their org — look up org from user record
        user_record = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        db_user = user_record.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        result = await db.execute(
            select(Farm).where(Farm.organisation_id == db_user.organisation_id)
        )
        farms = result.scalars().all()
        return [
            {"farm_id": str(f.id), "farm_name": f.name, "role_at_farm": "admin"}
            for f in farms
        ]
    else:
        # Non-admin: only assigned farms
        result = await db.execute(
            select(UserFarmAssignment, Farm)
            .join(Farm, UserFarmAssignment.farm_id == Farm.id)
            .where(
                UserFarmAssignment.user_id == UUID(user_id),
                UserFarmAssignment.revoked_at.is_(None),
            )
        )
        rows = result.all()
        return [
            {"farm_id": str(assignment.farm_id), "farm_name": farm.name, "role_at_farm": assignment.role_at_farm}
            for assignment, farm in rows
        ]


def require_farm_access(min_role: str = "viewer"):
    """
    Dependency factory: verify the user has access to a specific farm_id
    (passed as a path/query parameter) with at least the minimum role.

    Usage in a router:
        @router.get("/farms/{farm_id}/animals")
        async def list_animals(
            farm_id: UUID,
            access: dict = Depends(require_farm_access("viewer")),
        ):
            ...

    Returns dict with: user_id, email, role, farm_id, role_at_farm.
    """
    min_level = ROLE_HIERARCHY.get(min_role, 0)

    async def checker(
        farm_id: UUID,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        # Admin bypasses farm-level checks
        if user["role"] == "admin":
            return {**user, "farm_id": str(farm_id), "role_at_farm": "admin"}

        # Check for active assignment to this farm
        result = await db.execute(
            select(UserFarmAssignment).where(
                UserFarmAssignment.user_id == UUID(user["user_id"]),
                UserFarmAssignment.farm_id == farm_id,
                UserFarmAssignment.revoked_at.is_(None),
            )
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this farm",
            )

        # Check role level at farm
        user_farm_level = ROLE_HIERARCHY.get(assignment.role_at_farm, 0)
        if user_farm_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} access to this farm",
            )

        return {**user, "farm_id": str(farm_id), "role_at_farm": assignment.role_at_farm}

    return checker
