"""FastStream 이벤트 consumer 통합 테스트."""

from unittest import mock

import pytest

from faststream.redis.testing import TestRedisBroker

from src.events import consumer
from src.events.broker import broker
from src.events.publisher import movie_enriched_publisher
from src.events.schemas import EnrichRequestedEvent, MovieEnrichedEvent

_SAMPLE_ENRICHED_EVENT = MovieEnrichedEvent(
    director="Francis Ford Coppola",
    korean_title="대부",
    poster_path="/poster.jpg",
    title="The Godfather",
    tmdb_id=238,
)


class TestConsumeEnrichRequest:
    @pytest.mark.asyncio
    async def test_published_event_contains_correct_fields(self) -> None:
        # Given
        request_event = EnrichRequestedEvent(tmdb_id=238, requested_by="test")

        with (
            mock.patch("src.events.consumer._persist_enrichment", new_callable=mock.AsyncMock),
            mock.patch(
                "src.events.consumer._build_enriched_event",
                new_callable=mock.AsyncMock,
                return_value=_SAMPLE_ENRICHED_EVENT,
            ),
        ):
            async with TestRedisBroker(broker) as test_broker:
                # When
                await test_broker.publish(
                    request_event,
                    stream="movie.enrich_requested",
                )

                # Then: 발행된 이벤트의 필드가 enrichment 결과와 일치해야 한다
                # FastStream이 Pydantic 모델을 dict로 역직렬화하여 mock에 전달한다.
                published = movie_enriched_publisher.mock.call_args[0][0]
                assert published["tmdb_id"] == 238
                assert published["title"] == "The Godfather"
                assert published["korean_title"] == "대부"
                assert published["director"] == "Francis Ford Coppola"

    @pytest.mark.asyncio
    async def test_suppresses_publish_when_movie_not_found(self) -> None:
        # Given: enrichment 결과가 None이면 영화를 찾지 못한 것이다
        request_event = EnrichRequestedEvent(tmdb_id=999, requested_by="test")

        with (
            mock.patch("src.events.consumer._persist_enrichment", new_callable=mock.AsyncMock),
            mock.patch(
                "src.events.consumer._build_enriched_event",
                new_callable=mock.AsyncMock,
                return_value=None,
            ),
        ):
            async with TestRedisBroker(broker) as test_broker:
                # When
                await test_broker.publish(
                    request_event,
                    stream="movie.enrich_requested",
                )

                # Then: movie.enriched 이벤트가 발행되지 않아야 한다
                movie_enriched_publisher.mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_dead_letter_on_enrichment_failure(self) -> None:
        # Given: enrichment 중 예외가 발생하는 상황
        request_event = EnrichRequestedEvent(tmdb_id=238, requested_by="test")

        with (
            mock.patch(
                "src.events.consumer._persist_enrichment",
                new_callable=mock.AsyncMock,
                side_effect=RuntimeError("TMDB connection error"),
            ),
            mock.patch("src.events.consumer.logger") as mock_logger,
        ):
            async with TestRedisBroker(broker) as test_broker:
                # When
                await test_broker.publish(
                    request_event,
                    stream="movie.enrich_requested",
                )

                # Then: dead-letter 에러 로그가 스택 트레이스와 함께 남아야 한다
                mock_logger.exception.assert_called_once()
                # Then: movie.enriched 이벤트가 발행되지 않아야 한다
                movie_enriched_publisher.mock.assert_not_called()
