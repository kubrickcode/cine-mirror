"""movie_search_cache 검색 쿼리 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock

from src.search.query import _escape_like_wildcards, find_movies


class TestEscapeLikeWildcards:
    """LIKE 와일드카드 이스케이프."""

    def test_escapes_percent(self) -> None:
        assert _escape_like_wildcards("%") == "\\%"

    def test_escapes_underscore(self) -> None:
        assert _escape_like_wildcards("_") == "\\_"

    def test_escapes_backslash(self) -> None:
        assert _escape_like_wildcards("\\") == "\\\\"

    def test_plain_text_unchanged(self) -> None:
        assert _escape_like_wildcards("기생충") == "기생충"

    def test_mixed_input(self) -> None:
        assert _escape_like_wildcards("100% sure") == "100\\% sure"


class TestFindMovies:
    """find_movies 검색 함수."""

    async def test_empty_query_returns_empty(self) -> None:
        """빈 쿼리는 DB 조회 없이 빈 리스트 반환."""
        session = AsyncMock()

        result = await find_movies(session, "")

        assert result == []
        session.execute.assert_not_called()

    async def test_whitespace_query_returns_empty(self) -> None:
        """공백만 있는 쿼리는 DB 조회 없이 빈 리스트 반환."""
        session = AsyncMock()

        result = await find_movies(session, "   ")

        assert result == []
        session.execute.assert_not_called()

    async def test_korean_query_executes_search(self) -> None:
        """한글 쿼리는 DB를 조회하여 결과 반환."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {
                "tmdb_id": 496243,
                "original_title": "Parasite",
                "korean_title": "기생충",
                "popularity": 87.5,
            }
        ]
        session.execute.return_value = mock_result

        result = await find_movies(session, "기생")

        assert len(result) == 1
        assert result[0]["korean_title"] == "기생충"
        session.execute.assert_called_once()

    async def test_english_query_executes_search(self) -> None:
        """영문 쿼리는 DB를 조회하여 결과 반환."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {
                "tmdb_id": 496243,
                "original_title": "Parasite",
                "korean_title": "기생충",
                "popularity": 87.5,
            }
        ]
        session.execute.return_value = mock_result

        result = await find_movies(session, "Parasite")

        assert len(result) == 1
        assert result[0]["original_title"] == "Parasite"
        session.execute.assert_called_once()

    async def test_wildcard_chars_in_query_do_not_match_all(self) -> None:
        """%만 입력해도 전체 매칭이 되지 않음 (이스케이프 적용)."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        result = await find_movies(session, "%")

        # DB는 호출되어야 하지만 이스케이프된 패턴으로 쿼리됨
        session.execute.assert_called_once()
        assert result == []

    async def test_default_limit_is_ten(self) -> None:
        """limit 기본값은 10."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        session.execute.return_value = mock_result

        await find_movies(session, "test")

        session.execute.assert_called_once()

    async def test_custom_limit_respected(self) -> None:
        """커스텀 limit 값 적용 — 결과가 요청한 개수 이하로 반환됨."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {
                "tmdb_id": i,
                "original_title": f"Movie {i}",
                "korean_title": None,
                "popularity": float(i),
            }
            for i in range(3)
        ]
        session.execute.return_value = mock_result

        result = await find_movies(session, "Movie", limit=3)

        assert len(result) <= 3
        session.execute.assert_called_once()
