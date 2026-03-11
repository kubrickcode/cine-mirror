"""이벤트 페이로드 스키마 정의."""

from pydantic import BaseModel


class EnrichRequestedEvent(BaseModel):
    requested_by: str
    tmdb_id: int


class MovieEnrichedEvent(BaseModel):
    director: str | None
    korean_title: str | None
    poster_path: str | None
    title: str
    tmdb_id: int


class SearchIndexEntry(BaseModel):
    korean_title: str | None
    original_title: str
    popularity: float
    tmdb_id: int


class SearchIndexSyncedPayload(BaseModel):
    batch_index: int
    batch_total: int
    entries: list[SearchIndexEntry]
    schema_version: int = 1
    synced_at: str
