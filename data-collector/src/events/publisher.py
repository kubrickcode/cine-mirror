"""movie.enriched 이벤트 발행 모듈."""

from src.events.broker import broker
from src.events.schemas import MovieEnrichedEvent

movie_enriched_publisher = broker.publisher(stream="movie.enriched")


async def publish_movie_enriched(event: MovieEnrichedEvent) -> None:
    await movie_enriched_publisher.publish(event)
