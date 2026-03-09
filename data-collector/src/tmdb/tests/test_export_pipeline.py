"""Tests for TMDB Daily Export pipeline."""

import json
import os
from pathlib import Path

import polars as pl
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.metadata import metadata
from src.db.models import movie_search_index
from src.tmdb.export_pipeline import (
    ExportStructureReport,
    filter_top_n,
    report_export_structure,
    upsert_search_index,
)


def _write_ndjson(path: Path, records: list[dict[str, int | float | str]]) -> None:
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def _build_movie_records(count: int) -> list[dict[str, int | float | str]]:
    """Build sample NDJSON records with deterministic popularity values."""
    return [
        {
            "id": i + 1,
            "original_title": f"Movie {i + 1}",
            "popularity": float(count - i),
        }
        for i in range(count)
    ]


class TestFilterTopN:
    def test_returns_top_n_sorted_by_popularity_descending(self, tmp_path: Path) -> None:
        records = _build_movie_records(100)
        filepath = tmp_path / "movies.ndjson"
        _write_ndjson(filepath, records)

        result = filter_top_n(filepath, n=5)

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 5
        assert result["id"].to_list() == [1, 2, 3, 4, 5]
        assert result["popularity"].to_list(
        ) == [100.0, 99.0, 98.0, 97.0, 96.0]

    def test_returns_all_records_when_n_exceeds_total(self, tmp_path: Path) -> None:
        records = _build_movie_records(7)
        filepath = tmp_path / "movies.ndjson"
        _write_ndjson(filepath, records)

        result = filter_top_n(filepath, n=100)

        assert len(result) == 7
        assert result["popularity"].to_list() == [7.0, 6.0, 5.0,
                                                  4.0, 3.0, 2.0, 1.0]

    def test_returns_empty_dataframe_for_empty_file(self, tmp_path: Path) -> None:
        filepath = tmp_path / "empty.ndjson"
        filepath.write_text("")

        result = filter_top_n(filepath, n=10)

        assert len(result) == 0


class TestReportExportStructure:
    def test_reports_record_count_fields_and_file_size(self, tmp_path: Path) -> None:
        records = _build_movie_records(20)
        filepath = tmp_path / "movies.ndjson"
        _write_ndjson(filepath, records)

        report = report_export_structure(filepath)

        assert isinstance(report, ExportStructureReport)
        assert report.record_count == 20
        assert set(report.fields) == {"id", "original_title", "popularity"}
        assert report.file_size_bytes == filepath.stat().st_size
        assert report.popularity_min == 1.0
        assert report.popularity_max == 20.0


class TestUpsertSearchIndex:
    """Integration tests requiring a running PostgreSQL instance."""

    @pytest.fixture
    def database_url(self) -> str:
        url = os.environ.get("DATABASE_URL")
        if url is None:
            pytest.skip(
                "DATABASE_URL not set — integration test requires PostgreSQL")
        return url

    @pytest_asyncio.fixture
    async def session(self, database_url: str) -> AsyncSession:
        engine = create_async_engine(database_url)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False,
        )
        async with session_factory() as session:
            yield session
            await session.execute(text("DELETE FROM movie_search_index"))
            await session.commit()
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_upserts_filtered_data_into_movie_search_index(
        self,
        session: AsyncSession,
    ) -> None:
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "original_title": ["Godfather", "Parasite", "Oldboy"],
            "popularity": [100.0, 90.0, 80.0],
        })

        await upsert_search_index(df, session)
        await session.commit()

        result = await session.execute(
            select(
                movie_search_index.c.tmdb_id,
                movie_search_index.c.original_title,
                movie_search_index.c.popularity,
            ).order_by(movie_search_index.c.popularity.desc()),
        )
        rows = result.all()
        assert len(rows) == 3
        assert rows[0].tmdb_id == 1
        assert rows[0].original_title == "Godfather"
        assert rows[0].popularity == 100.0

    @pytest.mark.asyncio
    async def test_updates_existing_records_on_conflict(
        self,
        session: AsyncSession,
    ) -> None:
        initial_df = pl.DataFrame({
            "id": [1],
            "original_title": ["Old Title"],
            "popularity": [50.0],
        })
        await upsert_search_index(initial_df, session)
        await session.commit()

        updated_df = pl.DataFrame({
            "id": [1],
            "original_title": ["New Title"],
            "popularity": [99.0],
        })
        await upsert_search_index(updated_df, session)
        await session.commit()

        result = await session.execute(
            select(
                movie_search_index.c.original_title,
                movie_search_index.c.popularity,
            ).where(movie_search_index.c.tmdb_id == 1),
        )
        row = result.one()
        assert row.original_title == "New Title"
        assert row.popularity == 99.0
