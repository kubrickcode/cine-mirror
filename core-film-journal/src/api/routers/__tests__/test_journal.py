"""저널 API 단위/통합 테스트."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from src.api.app import app
from src.api.dependencies import get_current_user_id, get_session
from src.api.routers.journal import _decode_cursor, _encode_cursor

_SEED_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_ENTRY_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_NOW = datetime(2026, 3, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """테스트 종료 시 dependency override 정리."""
    yield
    app.dependency_overrides.clear()


def _make_mock_session() -> AsyncMock:
    return AsyncMock()


def _override_deps(session: AsyncMock) -> None:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user_id] = lambda: _SEED_USER_ID


class TestCursorEncoding:
    """커서 인코딩/디코딩."""

    def test_roundtrip(self) -> None:
        """인코딩 후 디코딩하면 원본과 동일."""
        cursor = _encode_cursor(_NOW, _ENTRY_ID)
        decoded_at, decoded_id = _decode_cursor(cursor)

        assert decoded_at == _NOW
        assert decoded_id == _ENTRY_ID

    def test_invalid_cursor_raises_400(self) -> None:
        """잘못된 cursor는 HTTPException(400)."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_cursor("invalid-base64!!!")
        assert exc_info.value.status_code == 400


class TestCreateJournalEntry:
    """POST /api/journal."""

    async def test_creates_entry_when_no_movie_cache(self) -> None:
        """movie_cache 미존재 시 enrich_requested 발행 후 201 반환."""
        session = _make_mock_session()
        # movie_cache 조회 → 없음
        no_cache_result = MagicMock()
        no_cache_result.scalar_one_or_none.return_value = None
        # INSERT RETURNING 결과
        insert_result = MagicMock()
        insert_result.mappings.return_value.one.return_value = {
            "created_at": _NOW,
            "id": _ENTRY_ID,
            "rating": None,
            "short_review": None,
            "status": "discovered",
            "tmdb_id": 496243,
            "updated_at": _NOW,
        }
        session.execute.side_effect = [no_cache_result, insert_result]
        _override_deps(session)

        with patch("src.api.routers.journal.publish_enrich_requested") as mock_publish:
            mock_publish.return_value = None
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/journal", json={"tmdb_id": 496243})

        assert response.status_code == 201
        data = response.json()
        assert data["tmdb_id"] == 496243
        assert data["status"] == "discovered"
        assert data["movie"] is None
        mock_publish.assert_called_once_with(496243)

    async def test_skips_enrich_when_movie_cache_exists(self) -> None:
        """movie_cache 존재 시 enrich_requested 미발행."""
        session = _make_mock_session()
        cache_result = MagicMock()
        cache_result.scalar_one_or_none.return_value = 496243
        insert_result = MagicMock()
        insert_result.mappings.return_value.one.return_value = {
            "created_at": _NOW,
            "id": _ENTRY_ID,
            "rating": None,
            "short_review": None,
            "status": "discovered",
            "tmdb_id": 496243,
            "updated_at": _NOW,
        }
        session.execute.side_effect = [cache_result, insert_result]
        _override_deps(session)

        with patch("src.api.routers.journal.publish_enrich_requested") as mock_publish:
            mock_publish.return_value = None
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/api/journal", json={"tmdb_id": 496243})

        mock_publish.assert_not_called()

    async def test_duplicate_entry_returns_409(self) -> None:
        """이미 저널에 있는 영화 추가 시 409 반환."""
        session = _make_mock_session()
        no_cache_result = MagicMock()
        no_cache_result.scalar_one_or_none.return_value = None
        session.execute.side_effect = [
            no_cache_result,
            IntegrityError(None, None, None),
        ]
        _override_deps(session)

        with patch(
            "src.api.routers.journal.publish_enrich_requested", return_value=None
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/journal", json={"tmdb_id": 496243})

        assert response.status_code == 409


class TestListJournalEntries:
    """GET /api/journal."""

    async def test_returns_empty_list_when_no_entries(self) -> None:
        """저널 항목 없을 때 빈 목록 반환."""
        session = _make_mock_session()
        result = MagicMock()
        result.mappings.return_value.all.return_value = []
        session.execute.return_value = result
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/journal")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["has_next"] is False
        assert data["next_cursor"] is None

    async def test_returns_entries_with_movie_info(self) -> None:
        """movie_cache 조인된 항목 반환."""
        session = _make_mock_session()
        result = MagicMock()
        result.mappings.return_value.all.return_value = [
            {
                "created_at": _NOW,
                "id": _ENTRY_ID,
                "rating": None,
                "short_review": None,
                "status": "discovered",
                "tmdb_id": 496243,
                "updated_at": _NOW,
                "movie_korean_title": "기생충",
                "movie_original_title": "Parasite",
                "movie_poster_path": "/abc.jpg",
                "movie_tmdb_id": 496243,
            }
        ]
        session.execute.return_value = result
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/journal")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["movie"]["korean_title"] == "기생충"

    async def test_movie_is_none_when_not_enriched(self) -> None:
        """movie_cache 미존재(enrichment 미완료) 시 movie=None."""
        session = _make_mock_session()
        result = MagicMock()
        result.mappings.return_value.all.return_value = [
            {
                "created_at": _NOW,
                "id": _ENTRY_ID,
                "rating": None,
                "short_review": None,
                "status": "discovered",
                "tmdb_id": 496243,
                "updated_at": _NOW,
                "movie_korean_title": None,
                "movie_original_title": None,
                "movie_poster_path": None,
                "movie_tmdb_id": None,
            }
        ]
        session.execute.return_value = result
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/journal")

        assert response.status_code == 200
        assert response.json()["data"][0]["movie"] is None

    async def test_invalid_status_returns_422(self) -> None:
        """유효하지 않은 status 필터는 422 반환."""
        session = _make_mock_session()
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/journal", params={"status": "invalid_status"}
            )

        assert response.status_code == 422

    async def test_has_next_true_when_more_items_exist(self) -> None:
        """limit+1 개 항목 반환 시 has_next=True, next_cursor 존재."""
        session = _make_mock_session()
        result = MagicMock()
        # limit=2로 요청 → DB에서 3개(limit+1) 반환 → has_next=True
        rows = [
            {
                "created_at": _NOW,
                "id": UUID(f"aaaaaaaa-0000-0000-0000-00000000000{i}"),
                "rating": None,
                "short_review": None,
                "status": "discovered",
                "tmdb_id": i,
                "updated_at": _NOW,
                "movie_korean_title": None,
                "movie_original_title": None,
                "movie_poster_path": None,
                "movie_tmdb_id": None,
            }
            for i in range(1, 4)
        ]
        result.mappings.return_value.all.return_value = rows
        session.execute.return_value = result
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/journal", params={"limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["has_next"] is True
        assert data["next_cursor"] is not None

    async def test_cursor_round_trip_decodes_correctly(self) -> None:
        """인코딩된 cursor를 API에 전달하면 정상 파싱됨 (400 없음)."""
        from src.api.routers.journal import _encode_cursor

        session = _make_mock_session()
        result = MagicMock()
        result.mappings.return_value.all.return_value = []
        session.execute.return_value = result
        _override_deps(session)

        cursor = _encode_cursor(_NOW, _ENTRY_ID)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/journal", params={"cursor": cursor})

        assert response.status_code == 200

    async def test_invalid_cursor_returns_400(self) -> None:
        """유효하지 않은 cursor는 400 반환."""
        session = _make_mock_session()
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/journal", params={"cursor": "not-valid!!"}
            )

        assert response.status_code == 400


class TestGetJournalEntry:
    """GET /api/journal/{id}."""

    async def test_returns_detail_with_movie_and_directors(self) -> None:
        """영화 정보 + 감독 정보 포함 상세 반환."""
        session = _make_mock_session()
        entry_result = MagicMock()
        entry_result.mappings.return_value.one_or_none.return_value = {
            "created_at": _NOW,
            "id": _ENTRY_ID,
            "rating": None,
            "short_review": None,
            "status": "discovered",
            "tmdb_id": 496243,
            "updated_at": _NOW,
            "movie_korean_title": "기생충",
            "movie_original_title": "Parasite",
            "movie_poster_path": "/abc.jpg",
            "movie_tmdb_id": 496243,
        }
        director_result = MagicMock()
        director_result.mappings.return_value.all.return_value = [
            {"name": "봉준호", "tmdb_person_id": 21684}
        ]
        session.execute.side_effect = [entry_result, director_result]
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/journal/{_ENTRY_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(_ENTRY_ID)
        assert data["movie"]["korean_title"] == "기생충"
        assert data["movie"]["directors"][0]["name"] == "봉준호"

    async def test_not_found_returns_404(self) -> None:
        """존재하지 않는 항목 조회 시 404 반환."""
        session = _make_mock_session()
        result = MagicMock()
        result.mappings.return_value.one_or_none.return_value = None
        session.execute.return_value = result
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/journal/{_ENTRY_ID}")

        assert response.status_code == 404

    async def test_movie_is_none_when_not_enriched(self) -> None:
        """enrichment 미완료 시 movie=None이고 directors는 빈 리스트."""
        session = _make_mock_session()
        entry_result = MagicMock()
        entry_result.mappings.return_value.one_or_none.return_value = {
            "created_at": _NOW,
            "id": _ENTRY_ID,
            "rating": None,
            "short_review": None,
            "status": "discovered",
            "tmdb_id": 496243,
            "updated_at": _NOW,
            "movie_korean_title": None,
            "movie_original_title": None,
            "movie_poster_path": None,
            "movie_tmdb_id": None,
        }
        director_result = MagicMock()
        director_result.mappings.return_value.all.return_value = []
        session.execute.side_effect = [entry_result, director_result]
        _override_deps(session)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/journal/{_ENTRY_ID}")

        assert response.status_code == 200
        assert response.json()["movie"] is None
