"""APScheduler 작업 정의 — Daily Export 파이프라인 및 만료 캐시 갱신."""

import logging
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from src.db.connection import AsyncSessionFactory
from src.tmdb.client import TMDBClient
from src.tmdb.config import SEARCH_INDEX_SIZE
from src.tmdb.enricher import enrich_batch
from src.tmdb.export_pipeline import download_daily_export, filter_top_n, upsert_search_index

# Constraint: 실 서비스에서는 기동 전 TMDB_API_KEY 환경 변수 설정이 필수다.
_TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

_REFRESH_LOOKAHEAD_DAYS = 7

logger = logging.getLogger(__name__)


async def daily_export_job() -> None:
    """TMDB Daily Export 상위 N건을 movie_search_index에 적재한다.

    매일 00:00 UTC에 실행된다.
    """
    target_date = date.today()
    logger.info("daily_export_job 시작: date=%s, size=%d", target_date, SEARCH_INDEX_SIZE)

    try:
        ndjson_path = await download_daily_export(target_date)
        df = filter_top_n(str(ndjson_path), n=SEARCH_INDEX_SIZE)
        async with AsyncSessionFactory() as session, session.begin():
            await upsert_search_index(df, session)
        logger.info("daily_export_job 완료: %d건 upsert", len(df))
    except Exception:
        logger.exception("daily_export_job 실패: date=%s", target_date)
        raise


async def metadata_refresh_job() -> None:
    """만료 임박(7일 이내) Movie 레코드를 재enrichment한다.

    매일 02:00 UTC에 실행된다.
    """
    threshold = datetime.now(tz=timezone.utc) + timedelta(days=_REFRESH_LOOKAHEAD_DAYS)
    logger.info("metadata_refresh_job 시작: expires_at < %s", threshold.isoformat())

    try:
        tmdb_ids = await _fetch_expiring_tmdb_ids(threshold)
        if not tmdb_ids:
            logger.info("metadata_refresh_job: 갱신 대상 없음")
            return

        logger.info("metadata_refresh_job: %d건 갱신 대상", len(tmdb_ids))
        async with TMDBClient(api_key=_TMDB_API_KEY) as client:
            async with AsyncSessionFactory() as session, session.begin():
                await enrich_batch(tmdb_ids, client, session)
        logger.info("metadata_refresh_job 완료: %d건 갱신", len(tmdb_ids))
    except Exception:
        logger.exception("metadata_refresh_job 실패")
        raise


async def _fetch_expiring_tmdb_ids(threshold: datetime) -> list[int]:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("""
                SELECT tmdb_id
                FROM movie
                WHERE expires_at < :threshold
                  AND is_not_found = FALSE
            """),
            {"threshold": threshold},
        )
        return [row.tmdb_id for row in result]
