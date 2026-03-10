"""TMDB 검색 매칭률 검증 CLI 스크립트.

CSV에 정의된 영화 목록을 TMDB /search/movie API로 조회하여
top-1 / top-5 명중률과 실패 유형을 분석한 보고서를 생성한다.
"""

import asyncio
import csv
import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import httpx
from dotenv import load_dotenv

# scripts/ 디렉토리에서 실행될 때 src 패키지를 찾기 위해 프로젝트 루트를 경로에 추가
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.tmdb.client import InvalidAPIKeyError, TMDBClient  # noqa: E402

# YEAR_AMBIGUITY 판정 기준: top-10 결과 내 정규화 제목 일치 건수 임계값
_AMBIGUITY_COUNT_THRESHOLD = 2
# top-N 명중 판정 기준
_TOP1_RANK = 1
_TOP5_RANK = 5
_TOP10_RANK = 10


class FailureType(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    YEAR_AMBIGUITY = "YEAR_AMBIGUITY"
    TITLE_MISMATCH = "TITLE_MISMATCH"


@dataclass(frozen=True)
class MovieEntry:
    language: str
    user_title: str


@dataclass(frozen=True)
class MatchResult:
    failure_type: FailureType | None
    is_top1_match: bool
    is_top5_match: bool
    language: str
    top1_tmdb_id: int | None
    user_title: str


# ---------------------------------------------------------------------------
# 순수 함수 (테스트 가능)
# ---------------------------------------------------------------------------


def normalize_title(title: str) -> str:
    """검색 비교를 위해 제목을 정규화한다.

    Unicode NFC 정규화 후 소문자로 변환하고 구두점을 제거한다.
    한국어·영어 모두 동일한 기준으로 비교하기 위해 정규식 [^\\w\\s]를 사용한다.
    """
    normalized = unicodedata.normalize("NFC", title)
    lowercased = normalized.lower()
    return re.sub(r"[^\w\s]", "", lowercased)


def is_result_match(result: dict, user_title: str) -> bool:  # type: ignore[type-arg]
    """TMDB 검색 결과 단건이 사용자 제목과 일치하는지 판정한다.

    original_title 또는 한국어 번역 title 중 하나라도 일치하면 매칭으로 간주한다.
    """
    # Any: TMDB API 응답은 외부 비정형 데이터이므로 Any 허용
    normalized_query = normalize_title(user_title)
    original = normalize_title(result.get("original_title", ""))
    localized = normalize_title(result.get("title", ""))
    return original == normalized_query or localized == normalized_query


def classify_failure(
    results: list[dict],  # type: ignore[type-arg]
    user_title: str,
) -> FailureType:
    """매칭 실패 원인을 분류한다.

    결과 없음 → NOT_FOUND
    top-10 내 정규화 제목 일치 2개 이상 → YEAR_AMBIGUITY (동명이인/리메이크)
    그 외 → TITLE_MISMATCH
    """
    if not results:
        return FailureType.NOT_FOUND

    top10 = results[:_TOP10_RANK]
    match_count = sum(1 for r in top10 if is_result_match(r, user_title))
    if match_count >= _AMBIGUITY_COUNT_THRESHOLD:
        return FailureType.YEAR_AMBIGUITY

    return FailureType.TITLE_MISMATCH


def check_match(
    results: list[dict],  # type: ignore[type-arg]
    entry: MovieEntry,
) -> tuple[bool, bool, FailureType | None, int | None]:
    """검색 결과에서 top-1 / top-5 명중 여부와 실패 유형을 반환한다.

    반환값: (is_top1_match, is_top5_match, failure_type, top1_tmdb_id)
    """
    top5 = results[:_TOP5_RANK]

    is_top1 = bool(results) and is_result_match(results[0], entry.user_title)
    is_top5 = any(is_result_match(r, entry.user_title) for r in top5)

    if is_top5:
        top1_id: int | None = results[0].get("id") if results else None
        return is_top1, is_top5, None, top1_id

    failure = classify_failure(results, entry.user_title)
    top1_id = results[0].get("id") if results else None
    return False, False, failure, top1_id


def compute_subset_accuracy(subset: list[MatchResult]) -> dict:  # type: ignore[type-arg]
    """주어진 서브셋의 top-1 / top-5 정확도를 계산한다."""
    total = len(subset)
    if total == 0:
        return {"top1_accuracy": 0.0, "top5_accuracy": 0.0, "total": 0}

    top1_hits = sum(1 for r in subset if r.is_top1_match)
    top5_hits = sum(1 for r in subset if r.is_top5_match)
    return {
        "top1_accuracy": round(top1_hits / total, 3),
        "top5_accuracy": round(top5_hits / total, 3),
        "total": total,
    }


def build_report(results: list[MatchResult]) -> dict:  # type: ignore[type-arg]
    """매칭 결과 목록에서 최종 보고서 딕셔너리를 생성한다."""
    total = len(results)
    top1_hits = sum(1 for r in results if r.is_top1_match)
    top5_hits = sum(1 for r in results if r.is_top5_match)

    failures: list[MatchResult] = [r for r in results if r.failure_type is not None]
    failures_by_type: dict[str, int] = {}
    for failure_type in FailureType:
        count = sum(1 for r in failures if r.failure_type == failure_type)
        if count > 0:
            failures_by_type[failure_type.value] = count

    # "ko" 보완 집합으로 외국 영화를 계산해야 "fr", "ja" 등 다른 언어가 누락되지 않는다.
    korean_subset = compute_subset_accuracy([r for r in results if r.language == "ko"])
    foreign_subset = compute_subset_accuracy([r for r in results if r.language != "ko"])

    details = [
        {
            "failure_type": r.failure_type.value if r.failure_type else None,
            "is_top1_match": r.is_top1_match,
            "is_top5_match": r.is_top5_match,
            "language": r.language,
            "top1_tmdb_id": r.top1_tmdb_id,
            "user_title": r.user_title,
        }
        for r in results
    ]

    return {
        "details": details,
        "failures_by_type": failures_by_type,
        "foreign_subset": foreign_subset,
        "generated_at": datetime.now(UTC).isoformat(),
        "korean_subset": korean_subset,
        "top1_accuracy": round(top1_hits / total, 3) if total > 0 else 0.0,
        "top1_hits": top1_hits,
        "top5_accuracy": round(top5_hits / total, 3) if total > 0 else 0.0,
        "top5_hits": top5_hits,
        "total": total,
    }


# ---------------------------------------------------------------------------
# I/O 함수
# ---------------------------------------------------------------------------


def load_entries(csv_path: Path) -> list[MovieEntry]:
    """CSV 파일에서 영화 목록을 읽어 MovieEntry 리스트로 반환한다."""
    entries: list[MovieEntry] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                MovieEntry(
                    language=row["language"].strip(),
                    user_title=row["user_title"].strip(),
                )
            )
    return entries


async def search_movie(
    client: TMDBClient,
    user_title: str,
) -> list[dict]:  # type: ignore[type-arg]
    """TMDB /search/movie API를 호출하여 검색 결과 목록을 반환한다."""
    response = await client.request_json(
        method="GET",
        path="/search/movie",
        params={"query": user_title, "language": "ko-KR"},
    )
    return response.get("results", [])


async def _search_with_fallback(
    client: TMDBClient,
    entry: MovieEntry,
) -> tuple[MovieEntry, list[dict]]:  # type: ignore[type-arg]
    """TMDB 검색 실패 시 빈 목록을 반환하여 부분 실패를 허용한다.

    InvalidAPIKeyError는 설정 오류이므로 전체 검증을 중단해야 한다.
    네트워크 오류 등 일시적 실패는 NOT_FOUND로 기록하고 계속 진행한다.
    """
    try:
        results = await search_movie(client, entry.user_title)
        return entry, results
    except InvalidAPIKeyError:
        raise
    except Exception as err:
        print(f"경고: '{entry.user_title}' 검색 실패 — {err}", file=sys.stderr)
        return entry, []


async def run_validation(
    entries: list[MovieEntry],
    api_key: str,
) -> list[MatchResult]:
    """전체 영화 목록을 TMDB로 검색하여 매칭 결과를 수집한다.

    API 요청은 TMDBClient 내부 세마포어로 동시성이 제한된다.
    """
    match_results: list[MatchResult] = []

    async with TMDBClient(access_token=api_key) as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_search_with_fallback(client, e)) for e in entries]

    for task in tasks:
        entry, search_results = task.result()
        is_top1, is_top5, failure_type, top1_id = check_match(search_results, entry)
        match_results.append(
            MatchResult(
                failure_type=failure_type,
                is_top1_match=is_top1,
                is_top5_match=is_top5,
                language=entry.language,
                top1_tmdb_id=top1_id,
                user_title=entry.user_title,
            )
        )

    return match_results


def save_report(report: dict, output_path: Path) -> None:  # type: ignore[type-arg]
    """보고서를 JSON 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


async def main() -> None:
    """CLI 진입점: CSV 로드 → TMDB 검색 → 보고서 저장."""
    load_dotenv()
    api_key = os.environ.get("TMDB_ACCESS_TOKEN")
    if not api_key:
        raise RuntimeError("TMDB_ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")

    scripts_dir = Path(__file__).parent
    csv_path = scripts_dir / "data" / "user_movies.csv"
    output_path = scripts_dir.parent / "results" / "matching_accuracy_report.json"

    print(f"CSV 로드 중: {csv_path}")
    entries = load_entries(csv_path)
    print(f"총 {len(entries)}편 검증 시작...")

    match_results = await run_validation(entries, api_key)

    report = build_report(match_results)
    save_report(report, output_path)

    print(f"\n=== 매칭률 검증 결과 ===")
    print(f"전체: {report['total']}편")
    print(f"Top-1 정확도: {report['top1_accuracy']:.1%} ({report['top1_hits']}건)")
    print(f"Top-5 정확도: {report['top5_accuracy']:.1%} ({report['top5_hits']}건)")
    print(f"한국 영화: Top-1 {report['korean_subset']['top1_accuracy']:.1%}, Top-5 {report['korean_subset']['top5_accuracy']:.1%}")
    print(f"외국 영화: Top-1 {report['foreign_subset']['top1_accuracy']:.1%}, Top-5 {report['foreign_subset']['top5_accuracy']:.1%}")
    print(f"실패 유형: {report['failures_by_type']}")
    print(f"\n보고서 저장 완료: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
