"""search_index.synced 이벤트 페이로드 구성 단위 테스트."""

import pytest

from src.events.publisher import _split_into_batches, publish_search_index_synced
from src.events.schemas import SearchIndexEntry, SearchIndexSyncedPayload


def _make_entries(count: int) -> list[SearchIndexEntry]:
    return [
        SearchIndexEntry(
            korean_title=None,
            original_title=f"Movie {i}",
            popularity=float(i),
            tmdb_id=i,
        )
        for i in range(count)
    ]


class TestSplitIntoBatches:
    def test_빈_입력은_빈_배치_반환(self) -> None:
        assert _split_into_batches([], 10) == []

    def test_정확히_배치_크기와_같으면_단일_배치(self) -> None:
        result = _split_into_batches([1, 2, 3], 3)
        assert result == [[1, 2, 3]]

    def test_배치_크기_초과시_분할(self) -> None:
        result = _split_into_batches(list(range(5)), 2)
        assert result == [[0, 1], [2, 3], [4]]

    def test_1000건_배치_크기로_분할(self) -> None:
        items = list(range(2500))
        result = _split_into_batches(items, 1000)
        assert len(result) == 3
        assert len(result[0]) == 1000
        assert len(result[1]) == 1000
        assert len(result[2]) == 500


class TestPublishSearchIndexSynced:
    @pytest.mark.asyncio
    async def test_빈_entries_발행_안_함(self) -> None:
        published: list[SearchIndexSyncedPayload] = []

        async def mock_publish(payload: SearchIndexSyncedPayload) -> None:
            published.append(payload)

        from unittest.mock import AsyncMock, patch

        with patch("src.events.publisher.search_index_synced_publisher") as mock_publisher:
            mock_publisher.publish = AsyncMock(side_effect=mock_publish)
            await publish_search_index_synced([])

        assert published == []

    @pytest.mark.asyncio
    async def test_1000건_이하는_단일_배치_발행(self) -> None:
        entries = _make_entries(500)
        published: list[SearchIndexSyncedPayload] = []

        async def mock_publish(payload: SearchIndexSyncedPayload) -> None:
            published.append(payload)

        from unittest.mock import AsyncMock, patch

        with patch("src.events.publisher.search_index_synced_publisher") as mock_publisher:
            mock_publisher.publish = AsyncMock(side_effect=mock_publish)
            await publish_search_index_synced(entries)

        assert len(published) == 1
        assert published[0].batch_index == 0
        assert published[0].batch_total == 1
        assert len(published[0].entries) == 500

    @pytest.mark.asyncio
    async def test_1000건_초과시_복수_배치_발행(self) -> None:
        entries = _make_entries(2500)
        published: list[SearchIndexSyncedPayload] = []

        async def mock_publish(payload: SearchIndexSyncedPayload) -> None:
            published.append(payload)

        from unittest.mock import AsyncMock, patch

        with patch("src.events.publisher.search_index_synced_publisher") as mock_publisher:
            mock_publisher.publish = AsyncMock(side_effect=mock_publish)
            await publish_search_index_synced(entries)

        assert len(published) == 3
        assert all(p.batch_total == 3 for p in published)
        assert [p.batch_index for p in published] == [0, 1, 2]
        assert len(published[0].entries) == 1000
        assert len(published[2].entries) == 500

    @pytest.mark.asyncio
    async def test_페이로드_구조_검증(self) -> None:
        entries = _make_entries(2)
        published: list[SearchIndexSyncedPayload] = []

        async def mock_publish(payload: SearchIndexSyncedPayload) -> None:
            published.append(payload)

        from unittest.mock import AsyncMock, patch

        with patch("src.events.publisher.search_index_synced_publisher") as mock_publisher:
            mock_publisher.publish = AsyncMock(side_effect=mock_publish)
            await publish_search_index_synced(entries)

        payload = published[0]
        assert payload.batch_index == 0
        assert payload.batch_total == 1
        assert len(payload.entries) == 2
        assert payload.entries[0].tmdb_id == 0
        assert payload.entries[0].original_title == "Movie 0"
        assert payload.entries[0].korean_title is None
        # synced_at은 ISO 8601 형식이어야 한다
        assert "T" in payload.synced_at
