"""TMDB Daily Export pipeline — download, filter, and upsert to movie_search_index."""

import gzip
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DAILY_EXPORT_BASE_URL = "http://files.tmdb.org/p/exports"


@dataclass(frozen=True)
class ExportStructureReport:
    fields: list[str]
    file_size_bytes: int
    popularity_max: float
    popularity_median: float
    popularity_min: float
    record_count: int


async def download_daily_export(target_date: date, *, output_dir: str = "/tmp") -> Path:
    """Download TMDB daily export gzip file for the given date.

    Returns the path to the decompressed NDJSON file.
    """
    formatted_date = target_date.strftime("%m_%d_%Y")
    filename = f"movie_ids_{formatted_date}.json.gz"
    url = f"{DAILY_EXPORT_BASE_URL}/{filename}"

    gz_path = Path(output_dir) / filename
    ndjson_path = gz_path.with_suffix("")

    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
            response.raise_for_status()
            with open(gz_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    try:
        with gzip.open(gz_path, "rb") as gz_file, open(ndjson_path, "wb") as out_file:
            while chunk_bytes := gz_file.read(65536):
                out_file.write(chunk_bytes)
    finally:
        gz_path.unlink(missing_ok=True)

    return ndjson_path


def filter_top_n(filepath: str | Path, *, n: int) -> pl.DataFrame:
    """Filter top N movies by popularity from an NDJSON file using lazy evaluation."""
    path = Path(filepath)
    if path.stat().st_size == 0:
        return pl.DataFrame()

    return (
        pl.scan_ndjson(str(path))
        .sort("popularity", descending=True)
        .head(n)
        .collect()
    )


async def upsert_search_index(df: pl.DataFrame, session: AsyncSession) -> None:
    """Upsert filtered movie data into movie_search_index table.

    Does not commit — caller owns the transaction boundary.
    """
    rows = df.select("id", "original_title", "popularity").to_dicts()
    if not rows:
        return

    await session.execute(
        text("""
            INSERT INTO movie_search_index (tmdb_id, original_title, popularity)
            VALUES (:tmdb_id, :original_title, :popularity)
            ON CONFLICT (tmdb_id) DO UPDATE SET
                original_title = EXCLUDED.original_title,
                popularity = EXCLUDED.popularity,
                indexed_at = NOW()
        """),
        [
            {
                "tmdb_id": row["id"],
                "original_title": row["original_title"],
                "popularity": row["popularity"],
            }
            for row in rows
        ],
    )


def report_export_structure(filepath: str | Path) -> ExportStructureReport:
    """Report structure and statistics of an NDJSON export file."""
    path = Path(filepath)
    df = pl.read_ndjson(str(filepath))

    popularity = df["popularity"]

    return ExportStructureReport(
        fields=sorted(df.columns),
        file_size_bytes=path.stat().st_size,
        popularity_max=popularity.max(),
        popularity_median=popularity.median(),
        popularity_min=popularity.min(),
        record_count=len(df),
    )
