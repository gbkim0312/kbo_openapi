from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from app.infrastructure.config import Settings


class NaverSportsSource:
    """Adapter for Naver Sports' live baseball game-center payloads.

    The sports gateway is not a documented Naver Open API. Keep this adapter
    isolated so it can be disabled or replaced without changing the domain.
    """

    def __init__(self, config: Settings) -> None:
        self.config = config

    async def fetch_scoreboard(self, source_game_id: str, season: int) -> dict | None:
        naver_game_id = self.to_naver_game_id(source_game_id, season)
        url = f"{self.config.naver_sports_base_url}/schedule/games/{naver_game_id}/game-polling"
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.naver_sports_user_agent},
            timeout=self.config.naver_sports_timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        game = ((payload.get("result") or {}).get("game") or {})
        if not isinstance(game, dict) or not game:
            return None
        return self._parse_scoreboard(game)

    async def fetch_live_state(self, source_game_id: str, season: int) -> dict | None:
        naver_game_id = self.to_naver_game_id(source_game_id, season)
        url = f"{self.config.naver_sports_base_url}/schedule/games/{naver_game_id}/relay"
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.naver_sports_user_agent},
            timeout=self.config.naver_sports_timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        relay = ((payload.get("result") or {}).get("textRelayData") or {})
        if not isinstance(relay, dict):
            return None
        return self._parse_live_state(relay, source_game_id)

    @staticmethod
    def to_naver_game_id(source_game_id: str, season: int) -> str:
        """Map KBO's 20260919SSLT0 identity to Naver's 20260919SSLT02026."""
        return f"{source_game_id}{season}"

    @staticmethod
    def _parse_scoreboard(game: dict) -> dict | None:
        away_scores = NaverSportsSource._inning_values(game.get("awayTeamScoreByInning"))
        home_scores = NaverSportsSource._inning_values(game.get("homeTeamScoreByInning"))
        away_rheb = NaverSportsSource._rheb(game.get("awayTeamRheb"))
        home_rheb = NaverSportsSource._rheb(game.get("homeTeamRheb"))
        if not away_scores and not home_scores and away_rheb is None and home_rheb is None:
            return None

        innings = []
        for index in range(max(len(away_scores), len(home_scores))):
            away = away_scores[index] if index < len(away_scores) else None
            home = home_scores[index] if index < len(home_scores) else None
            if away is None and home is None:
                continue
            innings.append({"inning": index + 1, "away": away, "home": home})

        return {
            "innings": innings,
            "totals": {"away": away_rheb or {}, "home": home_rheb or {}},
            "maxInning": len(innings),
            "currentInning": game.get("currentInning"),
            "source": "naver-sports",
            "sourceGameId": game.get("gameId"),
            "fetchedAt": datetime.now(UTC).isoformat(),
            "startingPitchers": {
                "away": game.get("awayStarterName"),
                "home": game.get("homeStarterName"),
            },
        }

    @staticmethod
    def _parse_live_state(relay: dict, source_game_id: str) -> dict | None:
        state = relay.get("currentGameState")
        if not isinstance(state, dict):
            return None

        players: dict[str, dict[str, str | None]] = {}
        for side, team_code, key in (
            ("home", source_game_id[10:12], "homeLineup"),
            ("away", source_game_id[8:10], "awayLineup"),
        ):
            lineup = relay.get(key)
            if not isinstance(lineup, dict):
                continue
            for group in ("batter", "pitcher"):
                for player in lineup.get(group, []):
                    if not isinstance(player, dict) or not player.get("pcode"):
                        continue
                    players[str(player["pcode"])] = {
                        "id": str(player["pcode"]),
                        "name": str(player.get("name")) if player.get("name") else None,
                        "team": team_code or None,
                        "side": side,
                    }

        def player(value: object) -> dict[str, str | None] | None:
            key = str(value or "")
            if not key or key == "0":
                return None
            return players.get(key, {"id": key, "name": None, "team": None, "side": None})

        def number(key: str) -> int | None:
            value = state.get(key)
            return int(str(value)) if str(value or "").isdigit() else None

        inning = NaverSportsSource._parse_inning(relay)
        return {
            "pitcher": player(state.get("pitcher")),
            "batter": player(state.get("batter")),
            "count": {
                "balls": number("ball"),
                "strikes": number("strike"),
                "outs": number("out"),
            },
            "runners": {
                "first": player(state.get("base1")),
                "second": player(state.get("base2")),
                "third": player(state.get("base3")),
            },
            "source": "naver-sports",
            "relayNumber": relay.get("no"),
            "playSequence": relay.get("no"),
            "inning": inning,
        }

    @staticmethod
    def _parse_inning(relay: dict) -> dict[str, int | str] | None:
        relays = relay.get("textRelays")
        if isinstance(relays, list):
            for item in reversed(relays):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                match = re.search(r"(\d+)회\s*(초|말)", title)
                if match:
                    half = "top" if match.group(2) == "초" else "bottom"
                    return {
                        "number": int(match.group(1)),
                        "half": half,
                        "display": f"{match.group(1)}회{match.group(2)}",
                    }
        number = relay.get("inn")
        if str(number).isdigit():
            side = str(relay.get("homeOrAway") or "0")
            half = "bottom" if side == "1" else "top"
            korean_half = "말" if half == "bottom" else "초"
            return {
                "number": int(str(number)),
                "half": half,
                "display": f"{number}회{korean_half}",
            }
        return None

    @staticmethod
    def _inning_values(value: object) -> list[int | None]:
        if not isinstance(value, list):
            return []
        result: list[int | None] = []
        for item in value:
            text = str(item).strip()
            result.append(int(text) if text.isdigit() else None)
        return result

    @staticmethod
    def _rheb(value: object) -> dict[str, int | None] | None:
        if not isinstance(value, list) or len(value) < 4:
            return None
        keys = ("runs", "hits", "errors", "walks")
        return {
            key: int(value[index]) if str(value[index]).strip().isdigit() else None
            for index, key in enumerate(keys)
        }
