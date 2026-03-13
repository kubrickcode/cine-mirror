"""이벤트 구독자 정의 및 UPSERT 로직."""

import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionFactory
from src.db.models import (
    director_cache,
    movie_cache,
    movie_director_cache,
    movie_search_cache,
)
from src.events.broker import broker
from src.events.schemas import (
    MovieEnrichedPayload,
    SearchIndexEntry,
    SearchIndexSyncedPayload,
)

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


async def upsert_movie_enriched(
    session: AsyncSession,
    payload: MovieEnrichedPayload,
) -> None:
    """movie_cache, director_cache, movie_director_cache UPSERT."""
    now = datetime.now(UTC)

    movie_stmt = insert(movie_cache).values(
        enriched_at=now,
        korean_title=payload.korean_title,
        original_title=payload.title,
        poster_path=payload.poster_path,
        synced_at=now,
        tmdb_id=payload.tmdb_id,
    )
    movie_stmt = movie_stmt.on_conflict_do_update(
        index_elements=["tmdb_id"],
        set_={
            "enriched_at": movie_stmt.excluded.enriched_at,
            "korean_title": movie_stmt.excluded.korean_title,
            "original_title": movie_stmt.excluded.original_title,
            "poster_path": movie_stmt.excluded.poster_path,
        },
    )
    await session.execute(movie_stmt)

    if payload.directors:
        director_stmt = insert(director_cache).values(
            [
                {
                    "name": d.name,
                    "synced_at": now,
                    "tmdb_person_id": d.tmdb_person_id,
                }
                for d in payload.directors
            ]
        )
        director_stmt = director_stmt.on_conflict_do_update(
            index_elements=["tmdb_person_id"],
            set_={"name": director_stmt.excluded.name},
        )
        await session.execute(director_stmt)

        link_stmt = insert(movie_director_cache).values(
            [
                {
                    "director_tmdb_person_id": d.tmdb_person_id,
                    "movie_tmdb_id": payload.tmdb_id,
                }
                for d in payload.directors
            ]
        )
        link_stmt = link_stmt.on_conflict_do_nothing()
        await session.execute(link_stmt)

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


@broker.subscriber("movie.enriched")
async def on_movie_enriched(payload: MovieEnrichedPayload) -> None:
    """movie.enriched 이벤트 수신 → movie_cache, director_cache UPSERT."""
    try:
        async with AsyncSessionFactory() as session:
            await upsert_movie_enriched(session, payload)
    except Exception as exc:
        logger.error(
            "movie.enriched UPSERT 실패 — tmdb_id=%d",
            payload.tmdb_id,
            exc_info=exc,
        )
        raise
