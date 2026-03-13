"""구독하는 이벤트 페이로드 스키마 정의."""

from datetime import datetime

from pydantic import BaseModel


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
