from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums.game_status import GameStatus
from app.domain.enums.league_type import LeagueType


@dataclass(frozen=True, slots=True)
class SourceGame:
    source: str
    source_game_id: str | None
    season: int
    league_type: LeagueType
    game_date: date
    scheduled_at: datetime | None
    stadium: str | None
    status: GameStatus
    source_status_text: str | None
    away_team_code: str
    away_team_name: str
    home_team_code: str
    home_team_name: str
    away_score: int | None
    home_score: int | None
    inning: str | None = None
    result_text: str | None = None
    winning_pitcher: str | None = None
    losing_pitcher: str | None = None
    save_pitcher: str | None = None
    attendance: int | None = None
    source_url: str | None = None
    source_updated_at: datetime | None = None
