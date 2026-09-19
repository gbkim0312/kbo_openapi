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
