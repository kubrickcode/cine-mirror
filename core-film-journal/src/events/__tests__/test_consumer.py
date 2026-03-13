"""이벤트 소비자 단위 테스트."""

from unittest.mock import AsyncMock

from src.events.consumer import upsert_movie_enriched, upsert_search_index
from src.events.schemas import DirectorInfo, MovieEnrichedPayload, SearchIndexEntry


class TestUpsertSearchIndex:
    """search_index.synced 배치 UPSERT 로직."""

    async def test_empty_entries_skips_db(self) -> None:
        """빈 entries 배치는 DB 호출 없이 스킵."""
        session = AsyncMock()

        await upsert_search_index(session, [])

        session.execute.assert_not_called()
        session.commit.assert_not_called()

    async def test_single_entry_upserted(self) -> None:
        """단일 항목이 정상적으로 UPSERT됨."""
        session = AsyncMock()
        entries = [
            SearchIndexEntry(
                tmdb_id=496243,
                original_title="Parasite",
                korean_title="기생충",
                popularity=87.5,
            )
        ]

        await upsert_search_index(session, entries)

        session.execute.assert_called_once()
        session.commit.assert_called_once()

    async def test_multiple_entries_upserted_in_single_call(self) -> None:
        """여러 항목을 단일 DB 호출로 UPSERT (N+1 방지)."""
        session = AsyncMock()
        entries = [
            SearchIndexEntry(
                tmdb_id=i,
                original_title=f"Movie {i}",
                korean_title=None,
                popularity=float(i),
            )
            for i in range(10)
        ]

        await upsert_search_index(session, entries)

        # 배치 단일 실행 (N+1 금지)
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    async def test_korean_title_nullable(self) -> None:
        """korean_title이 None인 항목도 정상 처리."""
        session = AsyncMock()
        entries = [
            SearchIndexEntry(
                tmdb_id=1,
                original_title="Unknown Film",
                korean_title=None,
                popularity=10.0,
            )
        ]

        # 예외 없이 실행되어야 함
        await upsert_search_index(session, entries)

        session.execute.assert_called_once()


class TestUpsertMovieEnriched:
    """movie.enriched 이벤트 UPSERT 로직."""

    async def test_upserts_movie_cache(self) -> None:
        """movie_cache UPSERT가 실행됨."""
        session = AsyncMock()
        payload = MovieEnrichedPayload(
            directors=[],
            korean_title="기생충",
            poster_path="/abc.jpg",
            title="Parasite",
            tmdb_id=496243,
        )

        await upsert_movie_enriched(session, payload)

        # movie_cache UPSERT 1회 + commit 1회
        assert session.execute.call_count == 1
        session.commit.assert_called_once()

    async def test_upserts_directors_when_present(self) -> None:
        """directors 있을 때 director_cache + movie_director_cache UPSERT 추가 실행."""
        session = AsyncMock()
        payload = MovieEnrichedPayload(
            directors=[
                DirectorInfo(name="봉준호", tmdb_person_id=21684),
                DirectorInfo(name="박찬욱", tmdb_person_id=10000),
            ],
            korean_title="기생충",
            poster_path="/abc.jpg",
            title="Parasite",
            tmdb_id=496243,
        )

        await upsert_movie_enriched(session, payload)

        # movie_cache + director_cache + movie_director_cache = 3회
        assert session.execute.call_count == 3
        session.commit.assert_called_once()

    async def test_skips_director_upsert_when_no_directors(self) -> None:
        """directors 없을 때 director_cache UPSERT 스킵."""
        session = AsyncMock()
        payload = MovieEnrichedPayload(
            directors=[],
            korean_title=None,
            poster_path=None,
            title="Unknown Film",
            tmdb_id=99999,
        )

        await upsert_movie_enriched(session, payload)

        assert session.execute.call_count == 1
