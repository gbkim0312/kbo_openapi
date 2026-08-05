from datetime import date

from app.adapters.outbound.sources.kbo_http_source import KboHttpSource
from app.application.dto.source_game import SourceGame
from app.domain.enums.game_status import GameStatus
from app.domain.enums.league_type import LeagueType
from app.infrastructure.config import Settings


def test_enriches_a_schedule_game_without_a_relay_link() -> None:
    source = KboHttpSource(Settings(), parser=None)
    game = SourceGame(
        source="kbo-http",
        source_game_id=None,
        season=2026,
        league_type=LeagueType.REGULAR,
        game_date=date(2026, 8, 5),
        scheduled_at=None,
        stadium="대구",
        status=GameStatus.SCHEDULED,
        source_status_text=None,
        away_team_code="HH",
        away_team_name="한화 이글스",
        home_team_code="SS",
        home_team_name="삼성 라이온즈",
        away_score=None,
        home_score=None,
    )

    enriched = source._enrich_game_ids([game], {("HH", "SS"): "20260805HHSS0"}, date(2026, 8, 5))

    assert enriched[0].source_game_id == "20260805HHSS0"
    assert "gameId=20260805HHSS0" in (enriched[0].source_url or "")
