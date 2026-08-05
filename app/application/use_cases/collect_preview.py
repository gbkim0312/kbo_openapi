from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.preview import (
    GameLineupEntryModel,
    GameLineupSnapshotModel,
    GamePreviewAnalysisModel,
)
from app.adapters.outbound.persistence.models.team import TeamModel
from app.adapters.outbound.sources.kbo_preview_source import KboPreviewSource


class CollectPreviewUseCase:
    def __init__(self, source: KboPreviewSource, sessions: async_sessionmaker) -> None:
        self.source, self.sessions = source, sessions

    async def execute(self, game_id: int) -> dict[str, object]:
        analysis_source_url = f"{self.source.config.kbo_base_url}/Schedule/GameCenter/Main.aspx"
        async with self.sessions() as session:
            game = await session.get(GameModel, game_id)
            if game is None or game.source_game_id is None:
                raise ValueError("game not found or does not have a KBO game id")
            teams = {
                team.id: team.code for team in (await session.scalars(select(TeamModel))).all()
            }
            preview = await self.source.fetch_preview(
                game.source_game_id, game.season, teams[game.away_team_id], teams[game.home_team_id]
            )
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            snapshot = GameLineupSnapshotModel(
                game_id=game_id,
                confirmed=preview.confirmed,
                source_url=f"{self.source.config.kbo_base_url}/Schedule/GameCenter/Preview/LineUp.aspx",
                collected_at=now,
            )
            session.add(snapshot)
            await session.flush()
            team_ids = {
                team.code: team.id for team in (await session.scalars(select(TeamModel))).all()
            }
            session.add_all(
                [
                    GameLineupEntryModel(
                        snapshot_id=snapshot.id,
                        team_id=team_ids[row.team_code],
                        batting_order=row.batting_order,
                        position=row.position,
                        player_name=row.player_name,
                        war=row.war,
                    )
                    for row in preview.lineups
                ]
            )
            stmt = (
                insert(GamePreviewAnalysisModel)
                .values(
                    game_id=game_id,
                    data=preview.analysis,
                    source_url=analysis_source_url,
                    collected_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["game_id"],
                    set_={
                        "data": preview.analysis,
                        "source_url": analysis_source_url,
                        "collected_at": now,
                    },
                )
            )
            await session.execute(stmt)
        return {
            "gameId": game_id,
            "confirmed": preview.confirmed,
            "lineupEntries": len(preview.lineups),
            "collectedAt": now,
        }
