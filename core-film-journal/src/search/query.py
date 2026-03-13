"""movie_search_cache ILIKE 검색 쿼리."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import movie_search_cache

_LIKE_ESCAPE_CHAR = "\\"


def _escape_like_wildcards(term: str) -> str:
    """LIKE 패턴 와일드카드(%, _)를 이스케이프하여 리터럴 문자로 처리."""
    return (
        term.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{_LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{_LIKE_ESCAPE_CHAR}_")
    )


async def find_movies(
    session: AsyncSession,
    search_term: str,
    limit: int = 10,
) -> list[dict]:
    """korean_title 및 original_title ILIKE 검색, 인기도 내림차순 정렬."""
    if not search_term.strip():
        return []

    pattern = f"%{_escape_like_wildcards(search_term)}%"
    stmt = (
        select(movie_search_cache)
        .where(
            or_(
                movie_search_cache.c.korean_title.ilike(
                    pattern, escape=_LIKE_ESCAPE_CHAR
                ),
                movie_search_cache.c.original_title.ilike(
                    pattern, escape=_LIKE_ESCAPE_CHAR
                ),
            )
        )
        .order_by(movie_search_cache.c.popularity.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
