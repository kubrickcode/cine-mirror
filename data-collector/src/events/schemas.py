"""이벤트 페이로드 스키마 정의."""

from pydantic import BaseModel


class DirectorInfo(BaseModel):
    name: str
    tmdb_person_id: int


class EnrichRequestedEvent(BaseModel):
    requested_by: str
    tmdb_id: int


class MovieEnrichedEvent(BaseModel):
    """movie.enriched 이벤트 페이로드.

    대응 구독자: core-film-journal/src/events/schemas.py MovieEnrichedPayload
    """

    directors: list[DirectorInfo]
    korean_title: str | None
    poster_path: str | None
    schema_version: int = 1
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
