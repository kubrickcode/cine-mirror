"""FastAPI 공통 의존성."""

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionFactory

_SEED_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """DB 세션 의존성 주입."""
    async with AsyncSessionFactory() as session:
        yield session


def get_current_user_id() -> UUID:
    """인증 stub — seed 사용자 ID 반환."""
    return _SEED_USER_ID
