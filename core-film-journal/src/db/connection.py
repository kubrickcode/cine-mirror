"""데이터베이스 연결 및 세션 팩토리."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

_engine = create_async_engine(settings.cfj_database_url, pool_pre_ping=True)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine,
    expire_on_commit=False,
)
