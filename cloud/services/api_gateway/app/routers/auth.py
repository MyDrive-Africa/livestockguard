from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organisation_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user with email and password, returns JWT tokens."""
    # TODO: Validate credentials against database
    # Placeholder implementation
    return TokenResponse(
        access_token="placeholder_access_token",
        refresh_token="placeholder_refresh_token",
        expires_in=3600,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """Register a new user account."""
    # TODO: Create user in database, hash password
    return TokenResponse(
        access_token="placeholder_access_token",
        refresh_token="placeholder_refresh_token",
        expires_in=3600,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """Refresh an expired access token using a valid refresh token."""
    # TODO: Validate refresh token and issue new tokens
    return TokenResponse(
        access_token="new_placeholder_access_token",
        refresh_token="new_placeholder_refresh_token",
        expires_in=3600,
    )
