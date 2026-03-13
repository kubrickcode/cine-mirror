"""이벤트 구독자 정의 및 UPSERT 로직."""

import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionFactory
from src.db.models import movie_search_cache
from src.events.broker import broker
from src.events.schemas import SearchIndexEntry, SearchIndexSyncedPayload

logger = logging.getLogger(__name__)


async def upsert_search_index(
    session: AsyncSession,
    entries: list[SearchIndexEntry],
) -> None:
    """movie_search_cache에 검색 인덱스 배치 UPSERT."""
    if not entries:
        return

    now = datetime.now(UTC)
    values = [
        {
            "korean_title": entry.korean_title,
            "original_title": entry.original_title,
            "popularity": entry.popularity,
            "synced_at": now,
            "tmdb_id": entry.tmdb_id,
        }
        for entry in entries
    ]

    stmt = insert(movie_search_cache).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tmdb_id"],
        set_={
            "korean_title": stmt.excluded.korean_title,
            "original_title": stmt.excluded.original_title,
            "popularity": stmt.excluded.popularity,
            "synced_at": stmt.excluded.synced_at,
        },
    )
    await session.execute(stmt)
    await session.commit()


@broker.subscriber("search_index.synced")
async def on_search_index_synced(payload: SearchIndexSyncedPayload) -> None:
    """search_index.synced 이벤트 수신 → movie_search_cache UPSERT."""
    try:
        async with AsyncSessionFactory() as session:
            await upsert_search_index(session, payload.entries)
    except Exception as exc:
        logger.error(
            "search_index.synced UPSERT 실패 — 배치 손실 위험",
            exc_info=exc,
            extra={
                "batch_index": payload.batch_index,
                "batch_total": payload.batch_total,
                "synced_at": payload.synced_at.isoformat(),
                "entry_count": len(payload.entries),
            },
        )
        raise
