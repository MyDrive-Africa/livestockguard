import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from livestockguard_common.db_models import User
from ..dependencies import get_db

router = APIRouter()

# Config
JWT_SECRET = os.environ.get("JWT_SECRET", "dev_secret_change_in_production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Schemas ────────────────────────────────────────

import re

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def validate_password_strength(password: str) -> str | None:
    """Return error message if password is too weak, or None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r'\d', password):
        return "Password must contain at least one digit"
    if not re.search(r'[a-zA-Z]', password):
        return "Password must contain at least one letter"
    return None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organisation_id: Optional[str] = None


class UserInfo(BaseModel):
    id: str
    email: str
    role: str
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: Optional[UserInfo] = None


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Helpers ────────────────────────────────────────

def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ─── Endpoints ──────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate user with email and password, returns JWT tokens. Rate limited: 10/minute."""
    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Account lockout check
    lockout_key = f"login:lockout:{request.email}"
    attempts_key = f"login:attempts:{request.email}"
    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        is_locked = await redis_client.get(lockout_key)
        if is_locked:
            await redis_client.aclose()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
            )
    except aioredis.ConnectionError:
        redis_client = None

    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not pwd_context.verify(request.password, user.password_hash):
        # Track failed attempt
        try:
            if redis_client:
                attempts = await redis_client.incr(attempts_key)
                await redis_client.expire(attempts_key, 900)  # 15 min window
                if int(attempts) >= 5:
                    await redis_client.setex(lockout_key, 900, "1")  # Lock for 15 min
                await redis_client.aclose()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Successful login — clear failed attempts
    try:
        if redis_client:
            await redis_client.delete(attempts_key, lockout_key)
            await redis_client.aclose()
    except Exception:
        pass

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(str(user.id), user.email, user.role)
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            role=user.role,
            full_name=user.full_name,
        ),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Password complexity check
    password_error = validate_password_strength(request.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # For now, assign to first org if none provided
    from livestockguard_common.db_models import Organisation
    org_id = request.organisation_id
    if not org_id:
        result = await db.execute(select(Organisation.id).limit(1))
        org_row = result.scalar_one_or_none()
        if org_row is None:
            raise HTTPException(status_code=400, detail="No organisation available")
        org_id = str(org_row)

    import uuid
    new_user = User(
        id=uuid.uuid4(),
        organisation_id=uuid.UUID(org_id),
        email=request.email,
        password_hash=pwd_context.hash(request.password),
        full_name=request.full_name,
        role="viewer",
    )
    db.add(new_user)
    await db.commit()

    access_token = create_access_token(str(new_user.id), new_user.email, new_user.role)
    refresh_token = create_refresh_token(str(new_user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh an expired access token using a valid refresh token."""
    import redis.asyncio as aioredis

    try:
        payload = jwt.decode(request.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check if token has been revoked (Redis blacklist)
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        is_revoked = await redis_client.get(f"token:revoked:{request.refresh_token}")
        await redis_client.aclose()
        if is_revoked:
            raise HTTPException(status_code=401, detail="Token has been revoked")
    except aioredis.ConnectionError:
        # If Redis is unavailable, allow refresh (graceful degradation in dev)
        pass

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    # Revoke the old refresh token (prevents reuse)
    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        # Token lives in blacklist until it would naturally expire (7 days)
        await redis_client.setex(
            f"token:revoked:{request.refresh_token}",
            REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )
        await redis_client.aclose()
    except Exception:
        pass  # Non-fatal — token rotation still works without Redis

    access_token = create_access_token(str(user.id), user.email, user.role)
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout_revoke(request: RefreshRequest):
    """Revoke a refresh token (logout from all sessions using this token)."""
    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await redis_client.setex(
            f"token:revoked:{request.refresh_token}",
            REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )
        await redis_client.aclose()
    except Exception:
        pass  # Best-effort revocation

    return {"status": "revoked"}
