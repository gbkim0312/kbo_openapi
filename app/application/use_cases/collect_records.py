from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.record import (
    AwardModel,
    GameDetailModel,
    GamePitcherRecordModel,
    PlayerSeasonStatModel,
    TeamRankSnapshotModel,
)
from app.adapters.outbound.persistence.models.team import TeamModel
from app.adapters.outbound.sources.kbo_record_source import KboRecordSource


class CollectRecordsUseCase:
    def __init__(self, source: KboRecordSource, sessions: async_sessionmaker) -> None:
        self.source, self.sessions = source, sessions

    async def execute(self) -> dict[str, int | str]:
        ranks, hitters, pitchers, awards = (
            await self.source.fetch_team_ranks(),
            await self.source.fetch_player_stats("hitter"),
            await self.source.fetch_player_stats("pitcher"),
            await self.source.fetch_season_awards(),
        )
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            teams = {
                team.code: team.id for team in (await session.scalars(select(TeamModel))).all()
            }
            for rank in ranks:
                values = {
                    **asdict(rank),
                    "team_id": teams[rank.team_code],
                    "source_url": (
                        f"{self.source.config.kbo_base_url}/Record/TeamRank/TeamRankDaily.aspx"
                    ),
                    "collected_at": now,
                }
                values.pop("team_code")
                stmt = (
                    insert(TeamRankSnapshotModel)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["as_of_date", "team_id"],
                        set_={
                            key: value
                            for key, value in values.items()
                            if key not in {"as_of_date", "team_id"}
                        },
                    )
                )
                await session.execute(stmt)
            for record in [*hitters, *pitchers]:
                values = {
                    "season": record.season,
                    "role": record.role,
                    "player_id": record.player_id,
                    "player_name": record.player_name,
                    "team_id": teams[record.team_code],
                    "rank": record.rank,
                    "stats": record.stats,
                    "source_url": f"{self.source.config.kbo_base_url}/Record/Player",
                    "collected_at": now,
                }
                stmt = (
                    insert(PlayerSeasonStatModel)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["season", "role", "player_id"],
                        set_={
                            key: value
                            for key, value in values.items()
                            if key not in {"season", "role", "player_id"}
                        },
                    )
                )
                await session.execute(stmt)
            for award in awards:
                values = {
                    "season": award.season,
                    "award_type": award.award_type,
                    "player_name": award.player_name,
                    "team_id": teams.get(award.team_code) if award.team_code else None,
                    "position": award.position,
                    "source_url": (
                        f"{self.source.config.kbo_base_url}/Player/Awards/PlayerPrize.aspx"
                    ),
                    "collected_at": now,
                }
                stmt = (
                    insert(AwardModel)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["season", "award_type", "player_name"],
                        set_={
                            key: value
                            for key, value in values.items()
                            if key not in {"season", "award_type", "player_name"}
                        },
                    )
                )
                await session.execute(stmt)
        return {
            "asOfDate": ranks[0].as_of_date.isoformat(),
            "teamRanks": len(ranks),
            "hitterStats": len(hitters),
            "pitcherStats": len(pitchers),
            "seasonAwards": len(awards),
        }

    async def collect_game_details(self, game_id: int) -> dict[str, int | str | None]:
        async with self.sessions() as session:
            game = await session.get(GameModel, game_id)
            if game is None or not game.source_game_id:
                raise ValueError("game not found or does not have a KBO game id")
            decisive, records = await self.source.fetch_box_score(game.source_game_id, game.season)
            away_id, home_id = game.away_team_id, game.home_team_id
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            detail = await session.get(GameDetailModel, game_id)
            if detail:
                detail.decisive_hit_text, detail.collected_at = decisive, now
            else:
                session.add(
                    GameDetailModel(
                        game_id=game_id,
                        decisive_hit_text=decisive,
                        source_url=f"{self.source.config.kbo_base_url}/Schedule/GameCenter/ReviewNew.aspx",
                        collected_at=now,
                    )
                )
            for record in records:
                team_id = away_id if record["side"] == 0 else home_id
                stmt = (
                    insert(GamePitcherRecordModel)
                    .values(
                        game_id=game_id,
                        team_id=team_id,
                        player_name=record["player_name"],
                        appearance=record["appearance"],
                        result=record["result"],
                        innings=record["innings"],
                        pitches=record["pitches"],
                        stats=record["stats"],
                        collected_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["game_id", "team_id", "player_name"],
                        set_={
                            "appearance": record["appearance"],
                            "result": record["result"],
                            "innings": record["innings"],
                            "pitches": record["pitches"],
                            "stats": record["stats"],
                            "collected_at": now,
                        },
                    )
                )
                await session.execute(stmt)
        return {"gameId": game_id, "decisiveHit": decisive, "pitcherRecords": len(records)}
