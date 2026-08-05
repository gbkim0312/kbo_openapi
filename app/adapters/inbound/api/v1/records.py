from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sqlalchemy import select

from app.adapters.outbound.persistence.models.preview import (
    GameLineupEntryModel,
    GameLineupSnapshotModel,
    GamePreviewAnalysisModel,
)
from app.adapters.outbound.persistence.models.record import (
    AwardModel,
    GameDetailModel,
    GamePitcherRecordModel,
    PlayerSeasonStatModel,
    TeamRankSnapshotModel,
)
from app.adapters.outbound.persistence.models.team import TeamModel
from app.application.use_cases.collect_preview import CollectPreviewUseCase
from app.application.use_cases.collect_records import CollectRecordsUseCase
from app.infrastructure.config import settings

router = APIRouter(tags=["records"])


def require_admin(authorization: str | None) -> None:
    if authorization != f"Bearer {settings.admin_api_key}":
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")


@router.get("/api/v1/rankings")
async def rankings(
    request: Request, date_: Annotated[date | None, Query(alias="date")] = None
) -> dict:
    stmt = select(TeamRankSnapshotModel, TeamModel).join(
        TeamModel, TeamModel.id == TeamRankSnapshotModel.team_id
    )
    async with request.app.state.session_factory() as session:
        if date_:
            stmt = stmt.where(TeamRankSnapshotModel.as_of_date == date_)
        else:
            latest_date = await session.scalar(
                select(TeamRankSnapshotModel.as_of_date)
                .order_by(TeamRankSnapshotModel.as_of_date.desc())
                .limit(1)
            )
            stmt = stmt.where(TeamRankSnapshotModel.as_of_date == latest_date)
        rows = (await session.execute(stmt.order_by(TeamRankSnapshotModel.rank))).all()
    return {
        "asOfDate": (date_ or (rows[0][0].as_of_date if rows else None)),
        "rankings": [
            {
                "rank": rank.rank,
                "team": {"code": team.code, "name": team.name},
                "games": rank.games,
                "wins": rank.wins,
                "losses": rank.losses,
                "draws": rank.draws,
                "winningPct": rank.winning_pct,
                "gamesBehind": rank.games_behind,
                "recentTen": rank.recent_ten,
                "streak": rank.streak,
                "home": rank.home_record,
                "away": rank.away_record,
            }
            for rank, team in rows
        ],
    }


@router.get("/api/v1/player-stats")
async def player_stats(
    request: Request,
    season: int,
    role: str = Query("hitter", pattern="^(hitter|pitcher)$"),
    team: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    stmt = (
        select(PlayerSeasonStatModel, TeamModel)
        .outerjoin(TeamModel, TeamModel.id == PlayerSeasonStatModel.team_id)
        .where(PlayerSeasonStatModel.season == season, PlayerSeasonStatModel.role == role)
    )
    if team:
        stmt = stmt.where(TeamModel.code == team)
    async with request.app.state.session_factory() as session:
        rows = (
            await session.execute(
                stmt.order_by(
                    PlayerSeasonStatModel.rank.nullslast(), PlayerSeasonStatModel.player_name
                ).limit(limit)
            )
        ).all()
    return {
        "season": season,
        "role": role,
        "players": [
            {
                "playerId": stat.player_id,
                "name": stat.player_name,
                "team": team_model.code if team_model else None,
                "rank": stat.rank,
                "stats": stat.stats,
                "collectedAt": stat.collected_at,
            }
            for stat, team_model in rows
        ],
    }


@router.get("/api/v1/awards")
async def awards(request: Request, season: int | None = None) -> dict:
    stmt = select(AwardModel, TeamModel).outerjoin(TeamModel, TeamModel.id == AwardModel.team_id)
    if season:
        stmt = stmt.where(AwardModel.season == season)
    async with request.app.state.session_factory() as session:
        rows = (await session.execute(stmt.order_by(AwardModel.season.desc()))).all()
    return {
        "awards": [
            {
                "season": award.season,
                "type": award.award_type,
                "player": award.player_name,
                "team": team.code if team else None,
                "position": award.position,
                "collectedAt": award.collected_at,
            }
            for award, team in rows
        ]
    }


@router.get("/api/v1/games/{game_id}/details")
async def game_details(game_id: int, request: Request) -> dict:
    async with request.app.state.session_factory() as session:
        detail = await session.get(GameDetailModel, game_id)
        rows = (
            await session.execute(
                select(GamePitcherRecordModel, TeamModel)
                .join(TeamModel, TeamModel.id == GamePitcherRecordModel.team_id)
                .where(GamePitcherRecordModel.game_id == game_id)
            )
        ).all()
    return {
        "gameId": game_id,
        "decisiveHit": detail.decisive_hit_text if detail else None,
        "pitchers": [
            {
                "team": team.code,
                "name": record.player_name,
                "appearance": record.appearance,
                "result": record.result,
                "innings": record.innings,
                "pitches": record.pitches,
                "stats": record.stats,
            }
            for record, team in rows
        ],
    }


@router.get("/api/v1/games/{game_id}/lineups")
async def lineups(game_id: int, request: Request) -> dict:
    async with request.app.state.session_factory() as session:
        snapshot = await session.scalar(
            select(GameLineupSnapshotModel)
            .where(GameLineupSnapshotModel.game_id == game_id)
            .order_by(GameLineupSnapshotModel.collected_at.desc())
            .limit(1)
        )
        if snapshot is None:
            return {"gameId": game_id, "confirmed": False, "collectedAt": None, "lineups": []}
        rows = (
            await session.execute(
                select(GameLineupEntryModel, TeamModel)
                .join(TeamModel, TeamModel.id == GameLineupEntryModel.team_id)
                .where(GameLineupEntryModel.snapshot_id == snapshot.id)
                .order_by(GameLineupEntryModel.team_id, GameLineupEntryModel.batting_order)
            )
        ).all()
        analysis_model = await session.get(GamePreviewAnalysisModel, game_id)
    return {
        "gameId": game_id,
        "confirmed": snapshot.confirmed,
        "collectedAt": snapshot.collected_at,
        "startingPitchers": analysis_model.data.get("startingPitchers") if analysis_model else None,
        "lineups": [
            {
                "team": team.code,
                "battingOrder": entry.batting_order,
                "position": entry.position,
                "player": entry.player_name,
                "war": entry.war,
            }
            for entry, team in rows
        ],
    }


@router.get("/api/v1/games/{game_id}/analysis")
async def analysis(game_id: int, request: Request) -> dict:
    async with request.app.state.session_factory() as session:
        model = await session.get(GamePreviewAnalysisModel, game_id)
    return {
        "gameId": game_id,
        "officialAnalysis": model.data if model else None,
        "collectedAt": model.collected_at if model else None,
    }


@router.post("/internal/v1/records/collect")
async def collect_records(request: Request, authorization: str | None = Header(None)) -> dict:
    require_admin(authorization)
    return await CollectRecordsUseCase(
        request.app.state.record_source, request.app.state.session_factory
    ).execute()


@router.post("/internal/v1/games/{game_id}/details/collect")
async def collect_game_details(
    game_id: int, request: Request, authorization: str | None = Header(None)
) -> dict:
    require_admin(authorization)
    return await CollectRecordsUseCase(
        request.app.state.record_source, request.app.state.session_factory
    ).collect_game_details(game_id)


@router.post("/internal/v1/games/{game_id}/preview/collect")
async def collect_preview(
    game_id: int, request: Request, authorization: str | None = Header(None)
) -> dict:
    require_admin(authorization)
    return await CollectPreviewUseCase(
        request.app.state.preview_source, request.app.state.session_factory
    ).execute(game_id)
