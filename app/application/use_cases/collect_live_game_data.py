from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.preview import GameLineupSnapshotModel
from app.application.use_cases.collect_preview import CollectPreviewUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase


class CollectLiveGameDataUseCase:
    """Refreshes game-center data that can change near or during a game."""

    def __init__(
        self,
        records: CollectRecordsUseCase,
        previews: CollectPreviewUseCase,
        sessions: async_sessionmaker,
    ) -> None:
        self.records, self.previews, self.sessions = records, previews, sessions

    async def collect_previews(self, target_date: date) -> dict[str, int]:
        async with self.sessions() as session:
            game_ids = list(
                await session.scalars(
                    select(GameModel.id).where(
                        GameModel.game_date == target_date,
                        GameModel.status.in_(("scheduled", "pre_game", "in_progress")),
                    )
                )
            )
            confirmed_ids = set(
                await session.scalars(
                    select(GameLineupSnapshotModel.game_id).where(
                        GameLineupSnapshotModel.game_id.in_(game_ids),
                        GameLineupSnapshotModel.confirmed.is_(True),
                    )
                )
            )
        collected = failed = 0
        for game_id in game_ids:
            if game_id in confirmed_ids:
                continue
            try:
                await self.previews.execute(game_id)
                collected += 1
            except Exception:
                failed += 1
        return {
            "requested": len(game_ids) - len(confirmed_ids),
            "collected": collected,
            "failed": failed,
        }

    async def collect_live_details(self, target_date: date) -> dict[str, int]:
        async with self.sessions() as session:
            game_ids = list(
                await session.scalars(
                    select(GameModel.id).where(
                        GameModel.game_date == target_date, GameModel.status == "in_progress"
                    )
                )
            )
        collected = failed = 0
        for game_id in game_ids:
            try:
                await self.records.collect_game_details(game_id)
                collected += 1
            except Exception:
                failed += 1
        return {"requested": len(game_ids), "collected": collected, "failed": failed}
