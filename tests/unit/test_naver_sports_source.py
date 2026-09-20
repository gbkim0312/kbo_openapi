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


def test_parses_naver_live_count_and_runners() -> None:
    parsed = NaverSportsSource._parse_live_state(
        {
            "no": 42,
            "inn": 4,
            "currentGameState": {
                "pitcher": "67143",
                "batter": "52765",
                "strike": "2",
                "ball": "1",
                "out": "1",
                "base1": "1",
                "base2": "0",
                "base3": "3",
            },
            "homeLineup": {
                "batter": [{"pcode": "52765", "name": "타자", "batOrder": 1}],
                "pitcher": [{"pcode": "67143", "name": "투수"}],
            },
            "awayLineup": {
                "batter": [{"pcode": "60000", "name": "주자", "batOrder": 3}],
                "pitcher": [],
            },
        },
        "20260919SSLT0",
    )
    assert parsed is not None
    assert parsed["count"] == {"balls": 1, "strikes": 2, "outs": 1}
    assert parsed["pitcher"]["name"] == "투수"
    assert parsed["batter"]["name"] == "타자"
    assert parsed["runners"]["third"]["name"] == "주자"
    assert parsed["inning"] == {"number": 4, "half": "top", "display": "4회초"}


def test_parses_inning_half_from_relay_title() -> None:
    assert NaverSportsSource._parse_inning(
        {"textRelays": [{"title": "9회말 KIA 공격"}], "inn": 9}
    ) == {"number": 9, "half": "bottom", "display": "9회말"}


def test_prefers_current_attack_side_over_lagging_relay_title() -> None:
    assert NaverSportsSource._parse_inning(
        {
            "inn": 9,
            "homeOrAway": "1",
            "textRelays": [{"title": "9회초 KIA 공격"}],
        }
    ) == {"number": 9, "half": "bottom", "display": "9회말"}
