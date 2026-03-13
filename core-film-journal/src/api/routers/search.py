"""영화 검색 API 라우터."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_session
from src.search.query import find_movies

router = APIRouter(prefix="/api/movies", tags=["search"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class MovieSearchItem(BaseModel):
    """영화 검색 결과 항목."""

    korean_title: str | None
    original_title: str
    popularity: float
    tmdb_id: int


@router.get("/search", response_model=list[MovieSearchItem])
async def search_movies(
    q: Annotated[str, Query(description="검색어 (한글 또는 영문)")],
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MovieSearchItem]:
    """영화 제목으로 검색 (korean_title, original_title ILIKE, 인기도 내림차순)."""
    rows = await find_movies(session, q, limit=limit)
    return [MovieSearchItem(**row) for row in rows]
