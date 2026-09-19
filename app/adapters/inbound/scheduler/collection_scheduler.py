from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.application.use_cases.collect_all import CollectAllUseCase
from app.application.use_cases.collect_games import CollectGamesUseCase
from app.application.use_cases.collect_live_game_data import CollectLiveGameDataUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase
from app.infrastructure.config import Settings, settings

SEOUL = ZoneInfo("Asia/Seoul")


def create_scheduler(
    use_case: CollectGamesUseCase,
    record_use_case: CollectRecordsUseCase | None = None,
    live_game_use_case: CollectLiveGameDataUseCase | None = None,
    config: Settings = settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=SEOUL)

    async def collect_today() -> None:
        await use_case.execute(datetime.now(SEOUL).date())

    async def collect_yesterday_all() -> None:
        target_date = datetime.now(SEOUL).date() - timedelta(days=1)
        if record_use_case:
            await CollectAllUseCase(use_case, record_use_case, use_case.sessions).execute(
                target_date
            )
        else:
            await use_case.execute(target_date)
        if live_game_use_case:
            await live_game_use_case.collect_live_details(target_date)

    async def collect_today_and_live_details() -> None:
        target_date = datetime.now(SEOUL).date()
        await use_case.execute(target_date)
        if live_game_use_case:
            await live_game_use_case.collect_live_details(target_date)

    async def collect_today_previews() -> None:
        if live_game_use_case:
            await live_game_use_case.collect_previews(datetime.now(SEOUL).date())

    async def collect_live_snapshot() -> None:
        now = datetime.now(SEOUL)
        if not 17 <= now.hour <= 23:
            return
        await use_case.execute(now.date())
        if live_game_use_case:
            await live_game_use_case.collect_live_details(now.date())

    scheduler.add_job(collect_yesterday_all, CronTrigger(hour=0, minute=30, timezone=SEOUL))
    scheduler.add_job(collect_today, CronTrigger(hour=6, minute=0, timezone=SEOUL))
    scheduler.add_job(collect_today, CronTrigger(hour=12, minute=0, timezone=SEOUL))
    scheduler.add_job(
        collect_today_and_live_details, CronTrigger(hour="17-23", minute="*/5", timezone=SEOUL)
    )
    scheduler.add_job(
        collect_today_previews, CronTrigger(hour="12-23", minute="*/15", timezone=SEOUL)
    )
    scheduler.add_job(
        collect_live_snapshot,
        IntervalTrigger(seconds=config.kbo_refresh_live_seconds, timezone=SEOUL),
        max_instances=1,
        coalesce=True,
    )
    return scheduler
