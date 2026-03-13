"""이벤트 발행 함수."""

from src.events.broker import broker
from src.events.schemas import EnrichRequestedEvent

_enrich_requested_publisher = broker.publisher(stream="movie.enrich_requested")


async def publish_enrich_requested(tmdb_id: int) -> None:
    """movie.enrich_requested 이벤트 발행."""
    event = EnrichRequestedEvent(requested_by="core-film-journal", tmdb_id=tmdb_id)
    await _enrich_requested_publisher.publish(event)
