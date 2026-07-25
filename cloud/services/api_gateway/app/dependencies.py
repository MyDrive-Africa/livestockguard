"""
FastAPI dependencies for database sessions and auth.
"""

import os
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from livestockguard_common.database import async_session_factory

# ─── Auth Configuration ───────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_in_production")
JWT_ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)


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

    Returns dict with keys: sub (user_id), email, role.
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
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_role(required_role: str):
    """Factory for role-based access control."""
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        role_hierarchy = {"admin": 3, "manager": 2, "viewer": 1}
        user_level = role_hierarchy.get(user["role"], 0)
        required_level = role_hierarchy.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher",
            )
        return user
    return checker
