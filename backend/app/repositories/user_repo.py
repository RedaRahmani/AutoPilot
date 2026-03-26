from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import normalize_email
from app.models.user import User


async def get_by_id(db: AsyncSession, user_id: UUID | str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    normalized_email = normalize_email(email)
    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()