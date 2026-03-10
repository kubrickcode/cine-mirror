"""Pipeline 실행 CLI — Daily Export 다운로드 및 enrichment 타이밍 측정.

사용법:
    uv run python scripts/run_pipeline.py --export-only
    uv run python scripts/run_pipeline.py --timing-sample 100
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# DATABASE_URL 환경 변수는 src.db.connection 임포트 전에 로드되어야 한다.
load_dotenv()

from src.db.connection import AsyncSessionFactory  # noqa: E402
from src.tmdb.client import TMDBClient  # noqa: E402
from src.tmdb.config import SEARCH_INDEX_SIZE  # noqa: E402
from src.tmdb.enricher import enrich_movie  # noqa: E402
from src.tmdb.export_pipeline import (  # noqa: E402
    download_daily_export,
    filter_top_n,
    upsert_search_index,
)

# 5만 건 추산 기준 목표 크기
_ENRICH_TARGET_SIZE = 50_000
# 타이밍 측정 동시성 (TMDBClient 세마포어와 동일)
_API_CONCURRENCY = 4


async def run_export() -> int:
    """Daily Export를 다운로드하고 movie_search_index에 upsert한다."""
    target_date = date.today()
    ndjson_path = await download_daily_export(target_date)
    df = filter_top_n(str(ndjson_path), n=SEARCH_INDEX_SIZE)
    async with AsyncSessionFactory() as session, session.begin():
        await upsert_search_index(df, session)
    row_count = len(df)
    print(f"movie_search_index 적재 완료: {row_count}건")
    return row_count


async def run_timing_sample(access_token: str, sample_size: int) -> dict:  # type: ignore[type-arg]
    """top-N건 enrichment 실측 후 p50/p95 및 5만 건 추산 시간을 계산한다."""
    target_date = date.today()
    print(f"Daily Export 다운로드 중 ({target_date})...")
    ndjson_path = await download_daily_export(target_date)
    df = filter_top_n(str(ndjson_path), n=sample_size)
    tmdb_ids = df["id"].to_list()

    print(f"enrichment 타이밍 측정 시작: {len(tmdb_ids)}건")
    latencies_seconds: list[float] = []

    async with TMDBClient(access_token=access_token) as client:
        async with AsyncSessionFactory() as session, session.begin():
            for i, tmdb_id in enumerate(tmdb_ids, start=1):
                start = time.monotonic()
                try:
                    async with session.begin_nested():
                        await enrich_movie(tmdb_id, client, session)
                except Exception as err:
                    print(f"경고: tmdb_id={tmdb_id} 실패 — {err}", file=sys.stderr)
                elapsed = time.monotonic() - start
                latencies_seconds.append(elapsed)
                if i % 10 == 0:
                    print(f"  진행: {i}/{len(tmdb_ids)}건 완료")

    return _compute_timing_report(latencies_seconds)


def _compute_timing_report(latencies_seconds: list[float]) -> dict:  # type: ignore[type-arg]
    """측정된 지연 목록으로 타이밍 리포트를 계산한다."""
    n = len(latencies_seconds)
    if n == 0:
        return {
            "estimated_wall_hours": 0.0,
            "p50_seconds": 0.0,
            "p95_seconds": 0.0,
            "sample_size": 0,
            "target_size": _ENRICH_TARGET_SIZE,
            "total_sample_seconds": 0.0,
        }

    sorted_latencies = sorted(latencies_seconds)
    p50 = statistics.median(sorted_latencies)
    p95_idx = min(int(n * 0.95), n - 1)
    p95 = sorted_latencies[p95_idx]

    # 동시성 _API_CONCURRENCY 기준 wall-clock 추산
    avg_per_request = sum(latencies_seconds) / n
    estimated_wall_seconds = (_ENRICH_TARGET_SIZE * avg_per_request) / _API_CONCURRENCY
    estimated_hours = estimated_wall_seconds / 3600

    return {
        "estimated_wall_hours": round(estimated_hours, 2),
        "p50_seconds": round(p50, 3),
        "p95_seconds": round(p95, 3),
        "sample_size": n,
        "target_size": _ENRICH_TARGET_SIZE,
        "total_sample_seconds": round(sum(latencies_seconds), 2),
    }


async def main(args: argparse.Namespace) -> None:
    results_dir = _PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    if args.export_only:
        await run_export()
        return

    if args.timing_sample > 0:
        access_token = os.environ.get("TMDB_ACCESS_TOKEN")
        if not access_token:
            raise RuntimeError("TMDB_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")

        report = await run_timing_sample(access_token, args.timing_sample)

        output_path = results_dir / "pipeline_timing_report.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        threshold_check = (
            "✅ 통과" if report["estimated_wall_hours"] <= 12 else "❌ 실패"
        )
        print("\n=== Enrichment 타이밍 결과 ===")
        print(f"샘플 크기: {report['sample_size']}건")
        print(f"p50 응답 시간: {report['p50_seconds']:.3f}초")
        print(f"p95 응답 시간: {report['p95_seconds']:.3f}초")
        print(f"5만 건 추산 소요 시간: {report['estimated_wall_hours']:.1f}시간")
        print(f"12시간 기준: {threshold_check}")
        print(f"\n보고서 저장 완료: {output_path}")
        return

    print(
        "오류: --export-only 또는 --timing-sample N 중 하나를 지정하세요.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline 실행 CLI")
    parser.add_argument(
        "--export-only", action="store_true", help="Daily Export만 실행"
    )
    parser.add_argument(
        "--timing-sample",
        type=int,
        default=0,
        metavar="N",
        help="N건 enrichment 타이밍 샘플 측정",
    )
    asyncio.run(main(parser.parse_args()))
