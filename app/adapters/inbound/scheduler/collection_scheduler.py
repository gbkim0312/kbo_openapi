from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.application.use_cases.collect_games import CollectGamesUseCase

SEOUL = ZoneInfo("Asia/Seoul")


def create_scheduler(use_case: CollectGamesUseCase) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=SEOUL)

    async def collect_today() -> None:
        await use_case.execute(datetime.now(SEOUL).date())

    async def collect_yesterday() -> None:
        await use_case.execute(datetime.now(SEOUL).date() - timedelta(days=1))

    scheduler.add_job(collect_yesterday, CronTrigger(hour=0, minute=10, timezone=SEOUL))
    scheduler.add_job(collect_today, CronTrigger(hour=6, minute=0, timezone=SEOUL))
    scheduler.add_job(collect_today, CronTrigger(hour=12, minute=0, timezone=SEOUL))
    scheduler.add_job(collect_today, CronTrigger(hour="17-23", minute="*/5", timezone=SEOUL))
    return scheduler
