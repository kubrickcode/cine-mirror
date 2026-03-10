"""movie.enrich_requested 이벤트 소비 및 처리 모듈."""

import logging
import os

from faststream import FastStream
from faststream.redis import StreamSub
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import AsyncSessionFactory
from src.events.broker import broker
from src.events.publisher import publish_movie_enriched
from src.events.schemas import EnrichRequestedEvent, MovieEnrichedEvent
from src.tmdb.client import TMDBClient
from src.tmdb.enricher import enrich_movie

# Constraint: 테스트에서는 _persist_enrichment가 mock되므로 빈 문자열 폴백이 안전하다.
# 실 서비스에서는 기동 전 TMDB_ACCESS_TOKEN 환경 변수 설정이 필수다.
_TMDB_ACCESS_TOKEN = os.environ.get("TMDB_ACCESS_TOKEN", "")

logger = logging.getLogger(__name__)

app = FastStream(broker)


@broker.subscriber(stream=StreamSub("movie.enrich_requested"))
async def consume_enrich_request(event: EnrichRequestedEvent) -> None:
    try:
        await _persist_enrichment(event.tmdb_id)
        movie_event = await _build_enriched_event(event.tmdb_id)
    except Exception:
        logger.exception("dead-letter: tmdb_id=%d enrichment 실패", event.tmdb_id)
        return

    if movie_event is not None:
        await publish_movie_enriched(movie_event)


async def _persist_enrichment(tmdb_id: int) -> None:
    # Side effect: TMDB API 호출 후 movie/director 테이블에 upsert한다.
    async with AsyncSessionFactory() as session:
        async with TMDBClient(access_token=_TMDB_ACCESS_TOKEN) as client:
            async with session.begin():
                await enrich_movie(tmdb_id, client, session)


async def _build_enriched_event(tmdb_id: int) -> MovieEnrichedEvent | None:
    async with AsyncSessionFactory() as session:
        return await _query_movie_enriched_event(tmdb_id, session)


async def _query_movie_enriched_event(
    tmdb_id: int,
    session: AsyncSession,
) -> MovieEnrichedEvent | None:
    result = await session.execute(
        text("""
            SELECT
                m.korean_title,
                m.poster_path,
                m.tmdb_metadata->>'title' AS title,
                d.name AS director
            FROM movie m
            LEFT JOIN movie_director md ON md.movie_id = m.id
            LEFT JOIN director d ON d.id = md.director_id
            WHERE m.tmdb_id = :tmdb_id AND m.is_not_found = FALSE
            LIMIT 1
        """),
        {"tmdb_id": tmdb_id},
    )
    row = result.one_or_none()
    if row is None or row.title is None:
        return None
    return MovieEnrichedEvent(
        director=row.director,
        korean_title=row.korean_title,
        poster_path=row.poster_path,
        title=row.title,
        tmdb_id=tmdb_id,
    )
