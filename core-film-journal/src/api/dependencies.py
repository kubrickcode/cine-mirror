"""FastAPI 공통 의존성."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionFactory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """DB 세션 의존성 주입."""
    async with AsyncSessionFactory() as session:
        yield session
