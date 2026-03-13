"""영화 검색 API 통합 테스트."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.api.dependencies import get_session


def _make_mock_session(rows: list[dict]) -> AsyncMock:
    """DB 결과를 반환하는 mock 세션 생성."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows
    session.execute.return_value = mock_result
    return session


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> AsyncGenerator[None, None]:
    """테스트 종료 시 dependency override 정리 — 테스트 격리 보장."""
    yield
    app.dependency_overrides.clear()


class TestSearchMoviesApi:
    """GET /api/movies/search 엔드포인트."""

    async def test_search_returns_matching_movies(self) -> None:
        """검색어에 일치하는 영화 목록 반환."""
        mock_session = _make_mock_session(
            [
                {
                    "tmdb_id": 496243,
                    "original_title": "Parasite",
                    "korean_title": "기생충",
                    "popularity": 87.5,
                }
            ]
        )
        app.dependency_overrides[get_session] = lambda: mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/movies/search", params={"q": "기생"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tmdb_id"] == 496243
        assert data[0]["korean_title"] == "기생충"
        assert data[0]["original_title"] == "Parasite"

    async def test_empty_query_returns_empty_list(self) -> None:
        """빈 검색어는 빈 결과 반환 (오류 없음)."""
        mock_session = _make_mock_session([])
        app.dependency_overrides[get_session] = lambda: mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/movies/search", params={"q": ""})

        assert response.status_code == 200
        assert response.json() == []

    async def test_no_results_returns_empty_list(self) -> None:
        """검색 결과 없을 때 빈 리스트 반환."""
        mock_session = _make_mock_session([])
        app.dependency_overrides[get_session] = lambda: mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/movies/search", params={"q": "존재하지않는영화xyz"}
            )

        assert response.status_code == 200
        assert response.json() == []

    async def test_korean_title_nullable_in_response(self) -> None:
        """korean_title이 None인 영화도 정상 응답."""
        mock_session = _make_mock_session(
            [
                {
                    "tmdb_id": 1,
                    "original_title": "Some Film",
                    "korean_title": None,
                    "popularity": 10.0,
                }
            ]
        )
        app.dependency_overrides[get_session] = lambda: mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/movies/search", params={"q": "Some"})

        assert response.status_code == 200
        assert response.json()[0]["korean_title"] is None

    async def test_custom_limit_caps_result_count(self) -> None:
        """limit 파라미터만큼만 결과 반환."""
        rows = [
            {
                "tmdb_id": i,
                "original_title": f"Movie {i}",
                "korean_title": None,
                "popularity": float(i),
            }
            for i in range(3)
        ]
        mock_session = _make_mock_session(rows)
        app.dependency_overrides[get_session] = lambda: mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/movies/search", params={"q": "Movie", "limit": 3}
            )

        assert response.status_code == 200
        assert len(response.json()) <= 3
