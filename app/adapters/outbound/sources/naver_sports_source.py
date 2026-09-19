from __future__ import annotations

from datetime import datetime

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
            "fetchedAt": datetime.now().isoformat(),
            "startingPitchers": {
                "away": game.get("awayStarterName"),
                "home": game.get("homeStarterName"),
            },
        }

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
