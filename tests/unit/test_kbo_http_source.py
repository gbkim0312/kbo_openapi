from datetime import date

from app.adapters.outbound.sources.kbo_http_source import KboHttpSource
from app.adapters.outbound.sources.kbo_record_source import KboRecordSource
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


def test_applies_explicit_game_center_live_state_and_score() -> None:
    source = KboHttpSource(Settings(), parser=None)
    game = SourceGame(
        source="kbo-http",
        source_game_id="20260919SSLT0",
        season=2026,
        league_type=LeagueType.REGULAR,
        game_date=date(2026, 9, 19),
        scheduled_at=None,
        stadium="사직",
        status=GameStatus.PRE_GAME,
        source_status_text="-",
        away_team_code="SS",
        away_team_name="삼성 라이온즈",
        home_team_code="LT",
        home_team_name="롯데 자이언츠",
        away_score=0,
        home_score=0,
    )

    enriched = source._enrich_game_ids(
        [game],
        {
            ("SS", "LT"): {
                "G_ID": "20260919SSLT0",
                "GAME_STATE_SC": "2",
                "GAME_RESULT_CK": 0,
                "CANCEL_SC_ID": "0",
                "CANCEL_SC_NM": "정상경기",
                "T_SCORE_CN": "1",
                "B_SCORE_CN": "0",
                "SCORE_CK": "1",
                "GAME_INN_NO": 3,
                "GAME_TB_SC_NM": "말",
            }
        },
        date(2026, 9, 19),
    )

    assert enriched[0].status is GameStatus.IN_PROGRESS
    assert (enriched[0].away_score, enriched[0].home_score) == (1, 0)
    assert enriched[0].inning == "3회말"


def test_parses_scoreboard_innings_and_totals() -> None:
    source = KboRecordSource(Settings())
    payload = {
        "table2": (
            '{"headers":[{"row":[{"Text":"1"},{"Text":"2"}]}],'
            '"rows":[{"row":[{"Text":"1"},{"Text":"0"}]},'
            '{"row":[{"Text":"0"},{"Text":"2"}]}]}'
        ),
        "table3": (
            '{"rows":[{"row":[{"Text":"1"},{"Text":"4"},{"Text":"0"},{"Text":"2"}]},'
            '{"row":[{"Text":"2"},{"Text":"3"},{"Text":"1"},{"Text":"1"}]}]}'
        ),
        "maxInning": 2,
    }

    scoreboard = source._parse_scoreboard(payload)

    assert scoreboard["innings"] == [
        {"inning": 1, "away": 1, "home": 0},
        {"inning": 2, "away": 0, "home": 2},
    ]
    assert scoreboard["totals"] == {
        "away": {"runs": 1, "hits": 4, "errors": 0, "walks": 2},
        "home": {"runs": 2, "hits": 3, "errors": 1, "walks": 1},
    }
