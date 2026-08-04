from datetime import date
from pathlib import Path

from app.adapters.outbound.sources.parser.game_parser import KboScheduleParser
from app.domain.enums.game_status import GameStatus


def test_parses_observed_kbo_schedule_response() -> None:
    body = (Path(__file__).parents[1] / "fixtures/kbo_responses/regular_completed.json").read_text()
    games = KboScheduleParser("https://www.koreabaseball.com").parse(body, date(2026, 8, 5))
    assert len(games) == 1
    game = games[0]
    assert (game.source_game_id, game.away_team_code, game.home_team_code) == (
        "20260805SSLG0",
        "SS",
        "LG",
    )
    assert (game.away_score, game.home_score, game.status) == (0, 3, GameStatus.COMPLETED)
    assert game.scheduled_at and game.scheduled_at.utcoffset().total_seconds() == 9 * 3600
