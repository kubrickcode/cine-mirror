"""data-collector 서비스 진입점 — APScheduler + FastStream 공존 기동."""

# Constraint: 단일 인스턴스 가정. 멀티 인스턴스 배포 시 daily_export_job과
# metadata_refresh_job이 중복 실행될 수 있으므로 분산 락(Redis SETNX 등)이 필요하다.

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.events.broker import broker
from src.scheduler.jobs import daily_export_job, metadata_refresh_job

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def _build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_export_job,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_export",
        name="Daily Export 파이프라인",
        replace_existing=True,
    )
    scheduler.add_job(
        metadata_refresh_job,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="metadata_refresh",
        name="만료 캐시 갱신",
        replace_existing=True,
    )
    return scheduler


async def run() -> None:
    scheduler = _build_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    async with broker:
        logger.info("FastStream connected")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
