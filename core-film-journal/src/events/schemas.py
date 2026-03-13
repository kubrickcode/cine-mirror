"""구독하는 이벤트 페이로드 스키마 정의."""

from datetime import datetime

from pydantic import BaseModel


class DirectorInfo(BaseModel):
    """감독 정보."""

    name: str
    tmdb_person_id: int


class EnrichRequestedEvent(BaseModel):
    """movie.enrich_requested 이벤트 페이로드."""

    requested_by: str
    tmdb_id: int


class MovieEnrichedPayload(BaseModel):
    """movie.enriched 이벤트 페이로드.

    대응 발행자: data-collector/src/events/schemas.py MovieEnrichedEvent
    """

    directors: list[DirectorInfo]
    korean_title: str | None
    poster_path: str | None
    schema_version: int = 1
    title: str
    tmdb_id: int


class SearchIndexEntry(BaseModel):
    """검색 인덱스 개별 항목."""

    korean_title: str | None
    original_title: str
    popularity: float
    tmdb_id: int


class SearchIndexSyncedPayload(BaseModel):
    """search_index.synced 이벤트 페이로드."""

    batch_index: int
    batch_total: int
    entries: list[SearchIndexEntry]
    schema_version: int = 1
    synced_at: datetime
