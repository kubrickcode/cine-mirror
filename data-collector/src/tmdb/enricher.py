import calendar
import json
import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.tmdb.client import MovieNotFoundError, TMDBClient
from src.tmdb.config import CACHE_TTL_MONTHS

logger = logging.getLogger(__name__)


async def enrich_movie(tmdb_id: int, client: TMDBClient, session: AsyncSession) -> None:
    # Side effect: Does not commit — caller owns the transaction boundary.
    try:
        data = await client.request_json(
            method="GET",
            path=f"/movie/{tmdb_id}",
            params={"append_to_response": "credits,translations"},
        )
    except MovieNotFoundError:
        await _mark_not_found(tmdb_id, session)
        return

    now = datetime.now(tz=timezone.utc)
    expires_at = _add_months(now, CACHE_TTL_MONTHS)

    movie_id = await _upsert_movie(
        tmdb_id=tmdb_id,
        poster_path=data.get("poster_path"),
        korean_title=_extract_korean_title(data),
        enriched_at=now,
        expires_at=expires_at,
        tmdb_metadata=data,
        session=session,
    )

    for director_data in _extract_directors(data):
        director_id = await _upsert_director(director_data, session, tmdb_id=tmdb_id)
        await _link_movie_director(movie_id=movie_id, director_id=director_id, session=session)


async def enrich_batch(
    tmdb_ids: Sequence[int],
    client: TMDBClient,
    session: AsyncSession,
) -> None:
    # Side effect: Does not commit — caller owns the transaction boundary.
    # 개별 영화는 savepoint로 격리되므로 한 영화의 실패가 배치 전체를 중단시키지 않는다.
    for tmdb_id in tmdb_ids:
        try:
            async with session.begin_nested():
                await enrich_movie(tmdb_id, client, session)
        except Exception as err:
            logger.error("tmdb_id=%d enrichment 실패, 건너뜀: %s", tmdb_id, err)


def _extract_korean_title(data: dict[str, Any]) -> str | None:
    translations = data.get("translations", {}).get("translations", [])
    for translation in translations:
        if translation.get("iso_639_1") == "ko":
            return translation.get("data", {}).get("title") or None
    return None


def _extract_directors(data: dict[str, Any]) -> list[dict[str, Any]]:
    crew = data.get("credits", {}).get("crew", [])
    return [member for member in crew if member.get("job") == "Director"]


def _add_months(dt: datetime, months: int) -> datetime:
    # Constraint: calendar.monthrange로 월말 경계를 처리해야 한다 (예: 1월 31일 + 1달 → 2월 28일).
    total_month = dt.month + months
    year = dt.year + (total_month - 1) // 12
    month = (total_month - 1) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


async def _upsert_movie(
    *,
    tmdb_id: int,
    poster_path: str | None,
    korean_title: str | None,
    enriched_at: datetime,
    expires_at: datetime,
    tmdb_metadata: dict[str, Any],  # Any: TMDB API returns untyped response
    session: AsyncSession,
) -> uuid.UUID:
    result = await session.execute(
        text("""
            INSERT INTO movie (tmdb_id, poster_path, korean_title, enriched_at, expires_at, tmdb_metadata)
            VALUES (:tmdb_id, :poster_path, :korean_title, :enriched_at, :expires_at, CAST(:tmdb_metadata AS jsonb))
            ON CONFLICT (tmdb_id) DO UPDATE SET
                enriched_at = EXCLUDED.enriched_at,
                expires_at = EXCLUDED.expires_at,
                is_not_found = FALSE,
                korean_title = EXCLUDED.korean_title,
                poster_path = EXCLUDED.poster_path,
                tmdb_metadata = EXCLUDED.tmdb_metadata
            RETURNING id
        """),
        {
            "enriched_at": enriched_at,
            "expires_at": expires_at,
            "korean_title": korean_title,
            "poster_path": poster_path,
            "tmdb_id": tmdb_id,
            "tmdb_metadata": json.dumps(tmdb_metadata),
        },
    )
    return cast(uuid.UUID, result.scalar_one())


async def _mark_not_found(tmdb_id: int, session: AsyncSession) -> None:
    await session.execute(
        text("""
            INSERT INTO movie (tmdb_id, is_not_found)
            VALUES (:tmdb_id, TRUE)
            ON CONFLICT (tmdb_id) DO UPDATE SET is_not_found = TRUE
        """),
        {"tmdb_id": tmdb_id},
    )


async def _upsert_director(
    director_data: dict[str, Any],  # Any: TMDB API returns untyped response
    session: AsyncSession,
    *,
    tmdb_id: int,
) -> uuid.UUID:
    try:
        person_id: int = director_data["id"]
        name: str = director_data["name"]
    except KeyError as err:
        raise ValueError(f"Director data for tmdb_id={tmdb_id} is missing field {err}") from err

    result = await session.execute(
        text("""
            INSERT INTO director (tmdb_person_id, name)
            VALUES (:tmdb_person_id, :name)
            ON CONFLICT (tmdb_person_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """),
        {"name": name, "tmdb_person_id": person_id},
    )
    return cast(uuid.UUID, result.scalar_one())


async def _link_movie_director(
    *,
    movie_id: uuid.UUID,
    director_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    await session.execute(
        text("""
            INSERT INTO movie_director (movie_id, director_id)
            VALUES (:movie_id, :director_id)
            ON CONFLICT DO NOTHING
        """),
        {"director_id": director_id, "movie_id": movie_id},
    )
