import asyncio
import sys
from datetime import date, timedelta

import uvicorn


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "api"
    if command == "api":
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
    elif command == "migrate":
        from alembic.config import main as alembic_main

        alembic_main(argv=["upgrade", "head"])
    elif command == "worker":
        asyncio.run(run_worker())
    elif command == "collect-date":
        if len(sys.argv) != 3:
            raise SystemExit("Usage: collect-date YYYY-MM-DD")
        asyncio.run(collect_date(date.fromisoformat(sys.argv[2])))
    elif command == "backfill":
        if len(sys.argv) != 4:
            raise SystemExit("Usage: backfill YYYY-MM-DD YYYY-MM-DD")
        asyncio.run(backfill(date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])))
    elif command == "collect-records":
        asyncio.run(collect_records())
    else:
        raise SystemExit(f"Unknown command: {command}")


async def collect_date(target_date: date) -> None:
    from app.bootstrap.create_worker import create_collect_use_case

    result = await create_collect_use_case().execute(target_date)
    print(result)


async def backfill(start: date, end: date) -> None:
    if end < start or (end - start).days > 31:
        raise SystemExit("Backfill range must be between 0 and 31 days")
    for offset in range((end - start).days + 1):
        await collect_date(start + timedelta(days=offset))


async def collect_records() -> None:
    from app.bootstrap.create_worker import create_record_use_case

    print(await create_record_use_case().execute())


async def run_worker() -> None:
    from app.adapters.inbound.scheduler.collection_scheduler import create_scheduler
    from app.bootstrap.create_worker import create_collect_use_case, create_record_use_case
    from app.infrastructure.config import settings

    if not settings.scheduler_enabled:
        await asyncio.Event().wait()
    scheduler = create_scheduler(create_collect_use_case(), create_record_use_case())
    scheduler.start()
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
