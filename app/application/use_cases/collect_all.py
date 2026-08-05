from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.game import GameModel
from app.application.use_cases.collect_games import CollectGamesUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase


class CollectAllUseCase:
    """Collects every durable data set available for a game date in one request."""

    def __init__(
        self,
        games: CollectGamesUseCase,
        records: CollectRecordsUseCase,
        sessions: async_sessionmaker,
    ) -> None:
        self.games, self.records, self.sessions = games, records, sessions

    async def execute(self, target_date: date) -> dict[str, object]:
        game_result = await self.games.execute(target_date)
        record_result = await self.records.execute()
        async with self.sessions() as session:
            completed_game_ids = list(
                await session.scalars(
                    select(GameModel.id)
                    .where(GameModel.game_date == target_date, GameModel.status == "completed")
                    .order_by(GameModel.id)
                )
            )
        detail_results: list[dict[str, int | str | None]] = []
        detail_failures: list[dict[str, object]] = []
        for game_id in completed_game_ids:
            try:
                detail_results.append(await self.records.collect_game_details(game_id))
            except Exception as error:
                detail_failures.append({"gameId": game_id, "error": str(error)})
        return {
            "targetDate": target_date,
            "games": {
                "jobId": str(game_result.job_id),
                "status": game_result.status.value,
                "fetchedCount": game_result.fetched_count,
                "insertedCount": game_result.inserted_count,
                "updatedCount": game_result.updated_count,
                "unchangedCount": game_result.unchanged_count,
                "failedCount": game_result.failed_count,
            },
            "records": record_result,
            "gameDetails": {
                "requestedCount": len(completed_game_ids),
                "succeededCount": len(detail_results),
                "failedCount": len(detail_failures),
                "results": detail_results,
                "failures": detail_failures,
            },
        }
