from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    code: str
    name: str


class InningScoreOut(BaseModel):
    inning: int
    away: int | None
    home: int | None


class ScoreOut(BaseModel):
    away: int | None
    home: int | None
    innings: list[InningScoreOut] | None = None
    hits: dict[str, int | None] | None = None
    errors: dict[str, int | None] | None = None
    walks: dict[str, int | None] | None = None
    scoreboard_source: str | None = Field(default=None, alias="scoreboardSource")
    live: "LiveStateOut | None" = None


class PlayerRefOut(BaseModel):
    id: str
    name: str | None = None
    team: str | None = None
    side: str | None = None


class LiveCountOut(BaseModel):
    balls: int | None = None
    strikes: int | None = None
    outs: int | None = None


class LiveRunnersOut(BaseModel):
    first: PlayerRefOut | None = None
    second: PlayerRefOut | None = None
    third: PlayerRefOut | None = None


class LiveStateOut(BaseModel):
    pitcher: PlayerRefOut | None = None
    batter: PlayerRefOut | None = None
    count: LiveCountOut
    runners: LiveRunnersOut
    source: str
    relay_number: int | None = Field(default=None, alias="relayNumber")
    inning: int | None = None


class GameOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    source: str
    source_game_id: str | None = Field(alias="sourceGameId")
    season: int
    league_type: str = Field(alias="leagueType")
    game_date: date = Field(alias="gameDate")
    scheduled_at: datetime | None = Field(alias="scheduledAt")
    stadium: str | None
    status: str
    source_status_text: str | None = Field(alias="sourceStatusText")
    away_team: TeamOut = Field(alias="awayTeam")
    home_team: TeamOut = Field(alias="homeTeam")
    score: ScoreOut
    inning: str | None
    revision: int
    last_collected_at: datetime = Field(alias="lastCollectedAt")
    updated_at: datetime = Field(alias="updatedAt")


class ApiErrorOut(BaseModel):
    code: str
    message: str


class GameListMetaOut(BaseModel):
    count: int
    next_cursor: int | None = Field(default=None, alias="nextCursor")
    collected_at: datetime | None = Field(default=None, alias="collectedAt")
    fetched_at: datetime | None = Field(default=None, alias="fetchedAt")
    source: str
    refresh_interval_seconds: int = Field(alias="refreshIntervalSeconds")
    stale: bool


class GameListOut(BaseModel):
    games: list[GameOut]
    meta: GameListMetaOut


class ErrorResponseOut(BaseModel):
    error: ApiErrorOut


class LatestResultsMetaOut(BaseModel):
    fetched_at: datetime | None = Field(default=None, alias="fetchedAt")
    source: str
    refresh_interval_seconds: int = Field(alias="refreshIntervalSeconds")
    stale: bool


class LatestResultsOut(BaseModel):
    games: list[GameOut]
    meta: LatestResultsMetaOut
