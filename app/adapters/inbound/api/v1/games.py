from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.adapters.inbound.api.schemas.game import GameOut, ScoreOut, TeamOut
from app.adapters.outbound.persistence.models.game import GameModel
from app.domain.exceptions import GameNotFoundError
from app.infrastructure.config import settings

router = APIRouter(prefix="/api/v1", tags=["games"])


def output(game: GameModel) -> GameOut:
    return GameOut(
        id=game.id,
        source=game.source,
        sourceGameId=game.source_game_id,
        season=game.season,
        leagueType=game.league_type,
        gameDate=game.game_date,
        scheduledAt=game.scheduled_at,
        stadium=game.stadium,
        status=game.status,
        sourceStatusText=game.source_status_text,
        awayTeam=TeamOut(code=game.away_team.code, name=game.away_team.name),
        homeTeam=TeamOut(code=game.home_team.code, name=game.home_team.name),
        score=ScoreOut(away=game.away_score, home=game.home_score),
        inning=game.inning,
        revision=game.revision,
        lastCollectedAt=game.last_collected_at,
    )


@router.get("/games")
async def get_games(
    request: Request,
    date_: Annotated[date | None, Query(alias="date")] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    team: str | None = None,
    status: str | None = None,
    league_type: str | None = Query(None, alias="leagueType"),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    cursor: int | None = Query(None, ge=0),
) -> dict:
    if date_ and (from_ or to):
        return {
            "error": {
                "code": "INVALID_DATE_RANGE",
                "message": "date와 from/to를 함께 사용할 수 없습니다.",
            }
        }
    if bool(from_) != bool(to):
        return {"error": {"code": "INVALID_DATE_RANGE", "message": "from과 to는 함께 필요합니다."}}
    if from_ and to and (to < from_ or to - from_ > timedelta(days=settings.max_query_range_days)):
        return {"error": {"code": "DATE_RANGE_TOO_LARGE", "message": "조회 기간이 너무 깁니다."}}
    clauses = []
    if date_:
        clauses.append(GameModel.game_date == date_)
    if from_ and to:
        clauses.append(GameModel.game_date.between(from_, to))
    if team:
        clauses.append(or_(GameModel.away_team.has(code=team), GameModel.home_team.has(code=team)))
    if status:
        clauses.append(GameModel.status == status)
    if league_type:
        clauses.append(GameModel.league_type == league_type)
    if cursor:
        clauses.append(GameModel.id > cursor)
    stmt = (
        select(GameModel)
        .options(selectinload(GameModel.away_team), selectinload(GameModel.home_team))
        .where(and_(*clauses))
        .order_by(GameModel.scheduled_at, GameModel.id)
        .limit(limit + 1)
    )
    async with request.app.state.session_factory() as session:
        games = list((await session.scalars(stmt)).all())
    next_cursor = games[limit - 1].id if len(games) > limit else None
    games = games[:limit]
    return {
        "games": [output(game).model_dump(by_alias=True) for game in games],
        "meta": {
            "count": len(games),
            "nextCursor": next_cursor,
            "collectedAt": max((g.last_collected_at for g in games), default=None),
            "stale": False,
        },
    }


@router.get("/games/{game_id}")
async def get_game(game_id: int, request: Request) -> dict:
    stmt = (
        select(GameModel)
        .options(selectinload(GameModel.away_team), selectinload(GameModel.home_team))
        .where(GameModel.id == game_id)
    )
    async with request.app.state.session_factory() as session:
        game = await session.scalar(stmt)
    if not game:
        raise GameNotFoundError()
    return output(game).model_dump(by_alias=True)


@router.get("/results/latest")
async def latest_results(
    request: Request,
    date_: Annotated[date | None, Query(alias="date")] = None,
    team: str | None = None,
    limit: int = Query(10, ge=1, le=200),
) -> dict:
    stmt = (
        select(GameModel)
        .options(selectinload(GameModel.away_team), selectinload(GameModel.home_team))
        .where(GameModel.status == "completed")
        .order_by(GameModel.game_date.desc(), GameModel.id.desc())
        .limit(limit)
    )
    if team:
        stmt = stmt.where(
            or_(GameModel.away_team.has(code=team), GameModel.home_team.has(code=team))
        )
    if date_:
        stmt = stmt.where(GameModel.game_date == date_)
    async with request.app.state.session_factory() as session:
        games = (await session.scalars(stmt)).all()
    return {"games": [output(game).model_dump(by_alias=True) for game in games]}
