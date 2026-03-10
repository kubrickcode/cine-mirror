"""통합 검증 CLI — 전체 마일스톤 0 검증을 순서대로 실행하고 최종 리포트를 생성한다.

순서:
  1. Daily Export → movie_search_index 적재
  2. 매칭률 측정 → matching_accuracy_report.json
  3. 100건 타이밍 → pipeline_timing_report.json
  4. 이벤트 인프라 왕복 테스트
  5. final_report.md 생성

사용법:
    uv run python scripts/run_validation.py
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# DATABASE_URL 환경 변수는 src.db.connection 임포트 전에 로드되어야 한다.
load_dotenv()

from scripts.run_pipeline import run_export, run_timing_sample  # noqa: E402
from scripts.validate_matching import (  # noqa: E402
    build_report,
    load_entries,
    run_validation,
)
from src.tmdb.client import InvalidAPIKeyError  # noqa: E402

_TIMING_SAMPLE_SIZE = 100
_TOP1_ACCURACY_THRESHOLD = 0.80
_MAX_ESTIMATED_HOURS = 12.0


# ---------------------------------------------------------------------------
# 이벤트 인프라 왕복 테스트
# ---------------------------------------------------------------------------


async def test_event_infrastructure(redis_url: str) -> tuple[bool, str]:
    """Redis 연결 및 Stream 발행/소비 왕복을 테스트한다.

    실제 consumer 프로세스 없이 Redis Stream 기본 동작만 검증한다.
    """
    try:
        # redis.asyncio는 faststream[redis]에 포함된다.
        from redis.asyncio import Redis  # type: ignore[import-untyped]

        redis = Redis.from_url(redis_url)
        try:
            pong = await redis.ping()
            if not pong:
                return False, "Redis PING 실패"

            test_stream = "validation.event_roundtrip_test"
            test_payload = {"tmdb_id": "238", "requested_by": "validation_test"}

            msg_id = await redis.xadd(test_stream, test_payload)
            messages = await redis.xread({test_stream: "0-0"}, count=1)

            await redis.delete(test_stream)

            if not messages:
                return False, "Stream 메시지 소비 실패"

            return True, f"Redis PING 성공, Stream 왕복 확인 (msg_id={msg_id.decode()})"
        finally:
            await redis.aclose()
    except Exception as err:
        return False, f"이벤트 인프라 테스트 실패: {err}"


# ---------------------------------------------------------------------------
# 단계별 실행
# ---------------------------------------------------------------------------


async def step_export() -> tuple[bool, str, int]:
    """Daily Export를 실행하고 적재 결과를 반환한다."""
    print("\n[1/5] Daily Export 실행 중...")
    try:
        row_count = await run_export()
        return True, f"{row_count}건 upsert 완료", row_count
    except Exception as err:
        return False, f"Export 실패: {err}", 0


async def step_matching(access_token: str) -> tuple[bool, str, dict]:  # type: ignore[type-arg]
    """매칭률 측정을 실행하고 리포트를 저장한다."""
    print("\n[2/5] 매칭률 측정 중...")
    scripts_dir = _PROJECT_ROOT / "scripts"
    csv_path = scripts_dir / "data" / "user_movies.csv"
    output_path = _PROJECT_ROOT / "results" / "matching_accuracy_report.json"

    try:
        entries = load_entries(csv_path)
        match_results = await run_validation(entries, access_token)
        report = build_report(match_results)

        output_path.parent.mkdir(exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        top1 = report["top1_accuracy"]
        passed = top1 >= _TOP1_ACCURACY_THRESHOLD
        status = "✅" if passed else "❌"
        msg = (
            f"Top-1 정확도: {top1:.1%} ({status}, 기준 {_TOP1_ACCURACY_THRESHOLD:.0%})"
        )
        print(f"  {msg}")
        return passed, msg, report
    except InvalidAPIKeyError:
        raise
    except Exception as err:
        return False, f"매칭률 측정 실패: {err}", {}


async def step_timing(access_token: str) -> tuple[bool, str, dict]:  # type: ignore[type-arg]
    """enrichment 타이밍을 측정하고 리포트를 저장한다."""
    print(f"\n[3/5] 타이밍 측정 중 ({_TIMING_SAMPLE_SIZE}건 샘플)...")
    output_path = _PROJECT_ROOT / "results" / "pipeline_timing_report.json"

    try:
        report = await run_timing_sample(access_token, _TIMING_SAMPLE_SIZE)

        output_path.parent.mkdir(exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        hours = report["estimated_wall_hours"]
        passed = hours <= _MAX_ESTIMATED_HOURS
        status = "✅" if passed else "❌"
        msg = f"5만 건 추산: {hours:.1f}시간 ({status}, 기준 {_MAX_ESTIMATED_HOURS:.0f}시간)"
        print(f"  {msg}")
        return passed, msg, report
    except Exception as err:
        return False, f"타이밍 측정 실패: {err}", {}


async def step_event_test(redis_url: str) -> tuple[bool, str]:
    """이벤트 인프라 왕복 테스트를 실행한다."""
    print("\n[4/5] 이벤트 인프라 왕복 테스트 중...")
    passed, msg = await test_event_infrastructure(redis_url)
    status = "✅" if passed else "❌"
    print(f"  {status} {msg}")
    return passed, msg


# ---------------------------------------------------------------------------
# 최종 리포트 생성
# ---------------------------------------------------------------------------


def generate_final_report(
    *,
    export_result: tuple[bool, str, int],
    matching_result: tuple[bool, str, dict],  # type: ignore[type-arg]
    timing_result: tuple[bool, str, dict],  # type: ignore[type-arg]
    event_result: tuple[bool, str],
) -> str:
    """마일스톤 0 통과 여부를 판정하는 최종 리포트 마크다운을 생성한다."""
    export_ok, export_msg, row_count = export_result
    matching_ok, matching_msg, matching_report = matching_result
    timing_ok, timing_msg, timing_report = timing_result
    event_ok, event_msg = event_result

    milestone_passed = matching_ok and timing_ok and event_ok
    verdict = "✅ **통과**" if milestone_passed else "❌ **실패**"

    top1 = matching_report.get("top1_accuracy", 0.0)
    top5 = matching_report.get("top5_accuracy", 0.0)
    hours = timing_report.get("estimated_wall_hours", 0.0)
    p50 = timing_report.get("p50_seconds", 0.0)
    p95 = timing_report.get("p95_seconds", 0.0)
    sample_size = timing_report.get("sample_size", 0)
    korean_top1 = matching_report.get("korean_subset", {}).get("top1_accuracy", 0.0)
    foreign_top1 = matching_report.get("foreign_subset", {}).get("top1_accuracy", 0.0)
    failures_by_type = matching_report.get("failures_by_type", {})

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return dedent(f"""\
        # 마일스톤 0 최종 검증 리포트

        > **생성 시각**: {generated_at}
        > **판정**: {verdict}

        ---

        ## 1. 판정 기준

        | 항목 | 기준 | 결과 | 통과 여부 |
        |------|------|------|-----------|
        | Top-1 매칭률 | ≥ 80% | {top1:.1%} | {"✅" if matching_ok else "❌"} |
        | 5만 건 추산 시간 | ≤ 12시간 | {hours:.1f}시간 | {"✅" if timing_ok else "❌"} |
        | 이벤트 왕복 | 성공 | {"성공" if event_ok else "실패"} | {"✅" if event_ok else "❌"} |

        ---

        ## 2. 매칭률 검증 (`matching_accuracy_report.json`)

        - **전체 Top-1 정확도**: {top1:.1%} ({matching_report.get("top1_hits", 0)}/{matching_report.get("total", 0)}건)
        - **전체 Top-5 정확도**: {top5:.1%}
        - **한국 영화 Top-1**: {korean_top1:.1%}
        - **외국 영화 Top-1**: {foreign_top1:.1%}
        - **실패 유형 분포**: {failures_by_type if failures_by_type else "없음"}

        ---

        ## 3. 파이프라인 타이밍 (`pipeline_timing_report.json`)

        - **샘플 크기**: {sample_size}건
        - **p50 응답 시간**: {p50:.3f}초
        - **p95 응답 시간**: {p95:.3f}초
        - **5만 건 추산 (동시성 4)**: {hours:.1f}시간

        ---

        ## 4. 이벤트 인프라

        - **결과**: {event_msg}

        ---

        ## 5. Daily Export

        - **적재 결과**: {export_msg}

        ---

        ## 결론

        마일스톤 0 {verdict}

        {"세 가지 기준(Top-1 ≥ 80%, 추산 ≤ 12h, 이벤트 왕복 성공)을 모두 충족하여 본격 개발 진행이 가능합니다." if milestone_passed else "하나 이상의 기준을 충족하지 못했습니다. 각 항목별 원인을 분석하고 개선 후 재검증이 필요합니다."}
    """)


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


async def main() -> None:
    access_token = os.environ.get("TMDB_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("TMDB_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

    results_dir = _PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    print("=== 마일스톤 0 통합 검증 시작 ===")

    export_result = await step_export()
    matching_result = await step_matching(access_token)
    timing_result = await step_timing(access_token)
    event_result = await step_event_test(redis_url)

    print("\n[5/5] 최종 리포트 생성 중...")
    report_md = generate_final_report(
        export_result=export_result,
        matching_result=matching_result,
        timing_result=timing_result,
        event_result=event_result,
    )

    final_report_path = results_dir / "final_report.md"
    final_report_path.write_text(report_md, encoding="utf-8")
    print(f"  최종 리포트 저장 완료: {final_report_path}")

    milestone_passed = matching_result[0] and timing_result[0] and event_result[0]
    verdict = "✅ 통과" if milestone_passed else "❌ 실패"
    print(f"\n=== 마일스톤 0 판정: {verdict} ===\n")


if __name__ == "__main__":
    asyncio.run(main())
