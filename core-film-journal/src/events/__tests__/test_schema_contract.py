"""data-collector ↔ core-film-journal 이벤트 스키마 계약 테스트.

두 서비스가 동일한 이벤트 구조를 공유하는지 검증한다.
스키마가 한쪽에서만 변경되면 이 테스트가 실패하여 드리프트를 조기에 감지한다.
"""

import sys
from pathlib import Path

import pytest

# data-collector는 별도 패키지이므로 sys.path 에 직접 추가
_DATA_COLLECTOR_SRC = Path(__file__).parents[4] / "data-collector" / "src"


def _load_dc_schemas() -> object:
    """data-collector 스키마 모듈 동적 로드."""
    if not _DATA_COLLECTOR_SRC.exists():
        pytest.skip("data-collector 소스를 찾을 수 없음 — 모노레포 외부에서 실행 중")

    if str(_DATA_COLLECTOR_SRC) not in sys.path:
        sys.path.insert(0, str(_DATA_COLLECTOR_SRC))

    import importlib

    return importlib.import_module("events.schemas")


class TestSearchIndexSyncedContract:
    """search_index.synced 이벤트 스키마 계약."""

    def test_search_index_entry_fields_match(self) -> None:
        """SearchIndexEntry 필드가 두 서비스에서 동일."""
        dc = _load_dc_schemas()
        from src.events.schemas import SearchIndexEntry as CfjEntry

        dc_fields = set(dc.SearchIndexEntry.model_fields.keys())
        cfj_fields = set(CfjEntry.model_fields.keys())

        assert dc_fields == cfj_fields, (
            f"SearchIndexEntry 필드 불일치 — "
            f"data-collector: {dc_fields}, core-film-journal: {cfj_fields}"
        )

    def test_search_index_synced_payload_fields_match(self) -> None:
        """SearchIndexSyncedPayload 필드가 두 서비스에서 동일."""
        dc = _load_dc_schemas()
        from src.events.schemas import SearchIndexSyncedPayload as CfjPayload

        dc_fields = set(dc.SearchIndexSyncedPayload.model_fields.keys())
        cfj_fields = set(CfjPayload.model_fields.keys())

        assert dc_fields == cfj_fields, (
            f"SearchIndexSyncedPayload 필드 불일치 — "
            f"data-collector: {dc_fields}, core-film-journal: {cfj_fields}"
        )

    def test_search_index_entry_field_types_match(self) -> None:
        """SearchIndexEntry 필드 타입 애노테이션이 두 서비스에서 동일."""
        dc = _load_dc_schemas()
        from src.events.schemas import SearchIndexEntry as CfjEntry

        for field_name, cfj_field in CfjEntry.model_fields.items():
            dc_field = dc.SearchIndexEntry.model_fields[field_name]
            assert cfj_field.annotation == dc_field.annotation, (
                f"SearchIndexEntry.{field_name} 타입 불일치 — "
                f"data-collector: {dc_field.annotation}, "
                f"core-film-journal: {cfj_field.annotation}"
            )


class TestMovieEnrichedContract:
    """movie.enriched 이벤트 스키마 계약."""

    def test_director_info_fields_match(self) -> None:
        """DirectorInfo 필드가 두 서비스에서 동일."""
        dc = _load_dc_schemas()
        from src.events.schemas import DirectorInfo as CfjDirectorInfo

        dc_fields = set(dc.DirectorInfo.model_fields.keys())
        cfj_fields = set(CfjDirectorInfo.model_fields.keys())

        assert dc_fields == cfj_fields, (
            f"DirectorInfo 필드 불일치 — "
            f"data-collector: {dc_fields}, core-film-journal: {cfj_fields}"
        )

    def test_movie_enriched_core_fields_present(self) -> None:
        """MovieEnrichedEvent 핵심 필드가 data-collector에 존재."""
        dc = _load_dc_schemas()
        from src.events.schemas import MovieEnrichedPayload

        cfj_fields = set(MovieEnrichedPayload.model_fields.keys())
        dc_fields = set(dc.MovieEnrichedEvent.model_fields.keys())

        assert cfj_fields == dc_fields, (
            f"MovieEnriched 필드 불일치 — "
            f"data-collector: {dc_fields}, core-film-journal: {cfj_fields}"
        )
