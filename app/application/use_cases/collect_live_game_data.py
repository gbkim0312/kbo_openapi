from datetime import UTC, date, datetime

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
        now = datetime.now(UTC)
        async with self.sessions() as session:
            game_rows = (
                await session.execute(
                    select(GameModel.id, GameModel.status).where(
                        GameModel.game_date == target_date,
                        GameModel.status.in_(
                            (
                                "scheduled",
                                "pre_game",
                                "in_progress",
                                "delayed",
                                "suspended",
                                "completed",
                            )
                        ),
                        GameModel.scheduled_at.is_not(None),
                        GameModel.scheduled_at <= now,
                    )
                )
            ).all()
        collected = failed = 0
        for game_id, status in game_rows:
            scoreboard_ok = False
            try:
                scoreboard_ok = await self._collect_scoreboard(game_id)
            except Exception:
                pass
            if status == "completed":
                collected += 1 if scoreboard_ok else 0
                continue
            try:
                await self.records.collect_game_details(game_id)
                collected += 1 if scoreboard_ok else 0
            except Exception:
                if not scoreboard_ok:
                    failed += 1
        return {"requested": len(game_rows), "collected": collected, "failed": failed}

    async def _collect_scoreboard(self, game_id: int) -> bool:
        async with self.sessions() as session:
            game = await session.get(GameModel, game_id)
            if game is None or not game.source_game_id:
                return False
            scoreboard = await self.records.source.fetch_scoreboard(
                game.source_game_id, game.season
            )
        if scoreboard is None:
            return False
        async with self.sessions() as session, session.begin():
            game = await session.get(GameModel, game_id)
            if game is not None:
                game.scoreboard = scoreboard
                game.updated_at = datetime.now(UTC)
                return True
        return False
