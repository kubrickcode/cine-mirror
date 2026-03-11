"""이벤트 발행 모듈."""

from collections.abc import Sequence
from datetime import datetime, timezone

from src.events.broker import broker
from src.events.schemas import MovieEnrichedEvent, SearchIndexEntry, SearchIndexSyncedPayload

_SEARCH_INDEX_BATCH_SIZE = 1000

movie_enriched_publisher = broker.publisher(stream="movie.enriched")
search_index_synced_publisher = broker.publisher(stream="search_index.synced")


async def publish_movie_enriched(event: MovieEnrichedEvent) -> None:
    await movie_enriched_publisher.publish(event)


async def publish_search_index_synced(entries: Sequence[SearchIndexEntry]) -> None:
    """search_index.synced 배치 이벤트를 발행한다.

    전체 entries를 _SEARCH_INDEX_BATCH_SIZE 단위로 분할하여 여러 메시지로 발행한다.
    """
    batches = _split_into_batches(entries, _SEARCH_INDEX_BATCH_SIZE)
    batch_total = len(batches)
    synced_at = datetime.now(tz=timezone.utc).isoformat()

    for batch_index, batch in enumerate(batches):
        payload = SearchIndexSyncedPayload(
            batch_index=batch_index,
            batch_total=batch_total,
            entries=list(batch),
            synced_at=synced_at,
        )
        await search_index_synced_publisher.publish(payload)


def _split_into_batches[T](items: Sequence[T], batch_size: int) -> list[list[T]]:
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]
