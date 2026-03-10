"""Tests for TMDB movie enrichment pipeline."""

import os
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.metadata import metadata
from src.db.models import director, movie, movie_director
from src.tmdb.client import TMDBClient
from src.tmdb.enricher import enrich_batch, enrich_movie


def _build_tmdb_response(
    tmdb_id: int,
    *,
    poster_path: str = "/poster.jpg",
    directors: list[dict[str, Any]] | None = None,
    korean_title: str | None = "한국어 제목",
) -> dict[str, Any]:
    """Mock TMDB movie detail 응답을 생성한다 (credits + translations 포함)."""
    if directors is None:
        directors = [{"id": 1001, "job": "Director", "name": "Test Director"}]

    translations: list[dict[str, Any]] = []
    if korean_title is not None:
        translations.append({"iso_639_1": "ko", "data": {"title": korean_title, "overview": ""}})
    translations.append({"iso_639_1": "en", "data": {"title": "English Title", "overview": ""}})

    return {
        "id": tmdb_id,
        "title": "Test Movie",
        "poster_path": poster_path,
        "credits": {
            "crew": [*directors, {"id": 9999, "job": "Producer", "name": "Some Producer"}],
        },
        "translations": {"translations": translations},
    }


def _create_mock_client(responses: dict[int, dict[str, Any]]) -> TMDBClient:
    """httpx.MockTransport 기반 TMDBClient를 생성한다."""

    async def handler(request: httpx.Request) -> httpx.Response:
        # /movie/{tmdb_id} 경로에서 tmdb_id 추출
        tmdb_id = int(request.url.path.rstrip("/").rsplit("/", maxsplit=1)[-1])
        if tmdb_id in responses:
            return httpx.Response(200, json=responses[tmdb_id])
        return httpx.Response(404, json={"status_message": "Not Found"})

    return TMDBClient(
        api_key="test-key",
        client=httpx.AsyncClient(
            base_url="https://example.test/3",
            transport=httpx.MockTransport(handler),
        ),
    )


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url is None:
        pytest.skip("DATABASE_URL not set — integration test requires PostgreSQL")
    return url


@pytest_asyncio.fixture
async def session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False,
    )
    async with session_factory() as db_session:
        yield db_session
        await db_session.execute(text("DELETE FROM movie_director"))
        await db_session.execute(text("DELETE FROM director"))
        await db_session.execute(text("DELETE FROM movie"))
        await db_session.commit()

    await engine.dispose()


class TestEnrichMovie:
    @pytest.mark.asyncio
    async def test_saves_enriched_at_and_expires_at(self, session: AsyncSession) -> None:
        # Given
        tmdb_id = 238
        client = _create_mock_client({tmdb_id: _build_tmdb_response(tmdb_id)})

        # When
        await enrich_movie(tmdb_id, client, session)
        await session.commit()
        await client.aclose()

        # Then
        result = await session.execute(
            select(movie.c.enriched_at, movie.c.expires_at).where(movie.c.tmdb_id == tmdb_id),
        )
        row = result.one()
        assert row.enriched_at is not None
        assert row.expires_at is not None
        # expires_at은 enriched_at 이후여야 한다 (약 6개월 후).
        assert row.expires_at > row.enriched_at

    @pytest.mark.asyncio
    async def test_saves_director_from_credits_crew(self, session: AsyncSession) -> None:
        # Given
        tmdb_id = 238
        directors = [{"id": 1776, "job": "Director", "name": "Francis Ford Coppola"}]
        client = _create_mock_client({tmdb_id: _build_tmdb_response(tmdb_id, directors=directors)})

        # When
        await enrich_movie(tmdb_id, client, session)
        await session.commit()
        await client.aclose()

        # Then: director 테이블에 저장 확인
        director_result = await session.execute(
            select(director.c.name, director.c.tmdb_person_id).where(
                director.c.tmdb_person_id == 1776,
            ),
        )
        director_row = director_result.one()
        assert director_row.name == "Francis Ford Coppola"
        assert director_row.tmdb_person_id == 1776

        # Then: movie_director 조인 테이블 저장 확인
        movie_id_result = await session.execute(
            select(movie.c.id).where(movie.c.tmdb_id == tmdb_id),
        )
        movie_id = movie_id_result.scalar_one()
        join_result = await session.execute(
            select(movie_director).where(movie_director.c.movie_id == movie_id),
        )
        assert join_result.one() is not None

    @pytest.mark.asyncio
    async def test_saves_korean_title_from_translations(self, session: AsyncSession) -> None:
        # Given
        tmdb_id = 238
        client = _create_mock_client({
            tmdb_id: _build_tmdb_response(tmdb_id, korean_title="대부"),
        })

        # When
        await enrich_movie(tmdb_id, client, session)
        await session.commit()
        await client.aclose()

        # Then
        result = await session.execute(
            select(movie.c.korean_title).where(movie.c.tmdb_id == tmdb_id),
        )
        assert result.scalar_one() == "대부"

    @pytest.mark.asyncio
    async def test_marks_movie_as_not_found_on_404(self, session: AsyncSession) -> None:
        # Given: 응답이 없는 tmdb_id는 mock에서 404 반환
        tmdb_id = 999
        client = _create_mock_client({})

        # When
        await enrich_movie(tmdb_id, client, session)
        await session.commit()
        await client.aclose()

        # Then
        result = await session.execute(
            select(movie.c.is_not_found).where(movie.c.tmdb_id == tmdb_id),
        )
        assert result.scalar_one() is True


class TestEnrichBatch:
    @pytest.mark.asyncio
    async def test_enriches_all_movies_in_batch(self, session: AsyncSession) -> None:
        # Given: 10개 TMDB ID
        tmdb_ids = list(range(1, 11))
        responses = {tmdb_id: _build_tmdb_response(tmdb_id) for tmdb_id in tmdb_ids}
        client = _create_mock_client(responses)

        # When
        await enrich_batch(tmdb_ids, client, session)
        await session.commit()
        await client.aclose()

        # Then: 10개 모두 movie 테이블에 저장
        result = await session.execute(
            select(movie.c.tmdb_id).where(movie.c.tmdb_id.in_(tmdb_ids)),
        )
        saved_ids = sorted(row.tmdb_id for row in result.all())
        assert saved_ids == tmdb_ids
