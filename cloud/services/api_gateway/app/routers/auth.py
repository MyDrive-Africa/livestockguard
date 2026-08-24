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

from livestockguard_common.aws_config import load_jwt_secret
from livestockguard_common.db_models import User
from ..dependencies import get_db

router = APIRouter()

# Config
JWT_SECRET = load_jwt_secret()
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
    """
    Validate password against minimum complexity requirements.

    Args:
        password: The plaintext password to validate.

    Returns:
        Error message string if the password is too weak, or None if it passes.
        Requirements: min 8 chars, at least one digit, at least one letter.
    """
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
    """
    Generate a short-lived JWT access token.

    Args:
        user_id: UUID string identifying the authenticated user.
        email: User's email address (included in token claims for convenience).
        role: Organisation-level role ('admin', 'farm_owner', 'herdsman', 'viewer').

    Returns:
        Encoded JWT string with 'access' type claim, expiring in
        ACCESS_TOKEN_EXPIRE_MINUTES (default: 60 minutes).
    """
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
    """
    Generate a long-lived JWT refresh token for silent re-authentication.

    Args:
        user_id: UUID string of the user to issue the token for.

    Returns:
        Encoded JWT string with 'refresh' type claim, expiring in
        REFRESH_TOKEN_EXPIRE_DAYS (default: 7 days). Should be stored
        securely by the client and exchanged at POST /auth/refresh.
    """
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
    """
    Authenticate user with email and password, returns JWT tokens.

    Args:
        request: Login credentials (email + password).
        req: Raw FastAPI Request (used for rate-limit key extraction).
        db: Async database session (injected).

    Returns:
        TokenResponse with access_token, refresh_token, and user info.

    Raises:
        HTTPException 401: Invalid email or password.
        HTTPException 429: Account locked after 5 consecutive failed attempts (15-min lockout).

    Security:
        - Failed login attempts tracked in Redis (5 failures → 15-min lockout).
        - Successful login clears the failure counter.
        - Updates user.last_login timestamp on success.
    """
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
    """
    Register a new user account.

    Args:
        request: Registration payload (email, password, full_name, optional organisation_id).
        db: Async database session (injected).

    Returns:
        TokenResponse with freshly minted access and refresh tokens.

    Raises:
        HTTPException 400: Password too weak (min 8 chars, must have letter + digit).
        HTTPException 409: Email already registered.
        HTTPException 400: No organisation available for assignment.

    Notes:
        New users are assigned the 'viewer' role by default. If no organisation_id
        is provided, the user is assigned to the first available organisation.
    """
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
    """
    Refresh an expired access token using a valid refresh token.

    Args:
        request: Contains the refresh_token to exchange.
        db: Async database session (injected).

    Returns:
        TokenResponse with new access_token and a rotated refresh_token.

    Raises:
        HTTPException 401: Token is invalid, expired, wrong type, revoked, or user not found.

    Security:
        - Implements refresh token rotation: the old token is blacklisted in Redis
          (stored for its remaining TTL) so it cannot be reused.
        - If Redis is unavailable, refresh still works (graceful degradation for dev).
    """
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
    """
    Revoke a refresh token (logout from all sessions using this token).

    Args:
        request: Contains the refresh_token to revoke.

    Returns:
        {"status": "revoked"} on success.

    Notes:
        Best-effort operation — if Redis is unavailable, the token remains valid
        until its natural expiry (7 days). The client should discard its local
        copy regardless of the server response.
    """
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
