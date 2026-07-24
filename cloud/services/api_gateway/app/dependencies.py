"""
FastAPI dependencies for database sessions and auth.
"""

import os
import sys
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# Add shared lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))

from livestockguard_common.database import async_session_factory


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
