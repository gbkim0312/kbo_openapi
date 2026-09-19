from app.adapters.outbound.sources.naver_sports_source import NaverSportsSource


def test_maps_kbo_id_to_naver_id() -> None:
    assert NaverSportsSource.to_naver_game_id("20260919SSLT0", 2026) == "20260919SSLT02026"


def test_parses_naver_live_rheb_and_innings() -> None:
    parsed = NaverSportsSource._parse_scoreboard(
        {
            "gameId": "20260919SSLT02026",
            "currentInning": "5회말",
            "awayTeamScoreByInning": ["0", "0", "1", "0", "0", "-"],
            "homeTeamScoreByInning": ["0", "0", "0", "0", "0", "-"],
            "awayTeamRheb": [1, 4, 0, 2],
            "homeTeamRheb": [0, 2, 1, 2],
            "awayStarterName": "최원태",
            "homeStarterName": "나균안",
        }
    )
    assert parsed is not None
    assert parsed["source"] == "naver-sports"
    assert parsed["totals"]["away"] == {"runs": 1, "hits": 4, "errors": 0, "walks": 2}
    assert parsed["innings"][2] == {"inning": 3, "away": 1, "home": 0}
    assert parsed["startingPitchers"] == {"away": "최원태", "home": "나균안"}
