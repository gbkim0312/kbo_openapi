import json
from dataclasses import dataclass

import httpx

from app.infrastructure.config import Settings


@dataclass(frozen=True, slots=True)
class LineupEntry:
    team_code: str
    batting_order: int
    position: str
    player_name: str
    war: str | None


@dataclass(frozen=True, slots=True)
class PreviewData:
    confirmed: bool
    lineups: list[LineupEntry]
    analysis: dict[str, object]


class KboPreviewSource:
    def __init__(self, config: Settings) -> None:
        self.config = config

    async def fetch_preview(
        self, source_game_id: str, season: int, away_code: str, home_code: str
    ) -> PreviewData:
        game_date = source_game_id[:8]
        referer = (
            f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx?"
            f"gameDate={game_date}&gameId={source_game_id}&section=PREVIEW"
        )
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.kbo_user_agent},
            timeout=self.config.kbo_total_timeout_seconds,
            follow_redirects=True,
        ) as client:
            await client.get(referer)
            params = {"leId": "1", "srId": "0", "seasonId": str(season), "gameId": source_game_id}
            game_list = await self._post(
                client,
                "/ws/Main.asmx/GetKboGameList",
                {
                    "leId": "1",
                    "srId": "0,1,3,4,5,6,7,8,9",
                    "date": game_date,
                },
                referer,
            )
            lineup = await self._post(
                client, "/ws/Schedule.asmx/GetLineUpAnalysis", params, referer
            )
            team_record = await self._post(
                client, "/ws/Schedule.asmx/GetTeamRecord", {**params, "groupSc": "SEASON"}, referer
            )
            key_players = await self._post(
                client,
                "/ws/Schedule.asmx/GetTeamKeyPlayer",
                {
                    "leId": "1",
                    "srId": "0",
                    "seasonId": str(season),
                    "awayTeamId": away_code,
                    "homeTeamId": home_code,
                },
                referer,
            )
            starters, starter_analysis = await self._fetch_starting_pitchers(
                client, game_list, source_game_id, params, away_code, home_code, referer
            )
        confirmed = bool(lineup[0][0].get("LINEUP_CK"))
        home_war = lineup[1][0] if len(lineup) > 1 and lineup[1] else {}
        away_war = lineup[2][0] if len(lineup) > 2 and lineup[2] else {}
        entries = [
            *self._entries(lineup[3] if len(lineup) > 3 else [], home_code),
            *self._entries(lineup[4] if len(lineup) > 4 else [], away_code),
        ]
        return PreviewData(
            confirmed,
            entries,
            {
                "lineupWar": {"away": away_war, "home": home_war},
                "teamRecord": team_record,
                "keyPlayers": key_players,
                "startingPitchers": starters,
                "startingPitcherAnalysis": starter_analysis,
            },
        )

    async def _fetch_starting_pitchers(
        self,
        client: httpx.AsyncClient,
        game_list: object,
        source_game_id: str,
        params: dict[str, str],
        away_code: str,
        home_code: str,
        referer: str,
    ) -> tuple[dict[str, object] | None, object | None]:
        games = game_list.get("game", []) if isinstance(game_list, dict) else []
        game = next(
            (row for row in games if isinstance(row, dict) and row.get("G_ID") == source_game_id),
            None,
        )
        if game is None or not game.get("T_PIT_P_ID") or not game.get("B_PIT_P_ID"):
            return None, None
        starters: dict[str, object] = {
            "away": {
                "team": away_code,
                "playerId": game["T_PIT_P_ID"],
                "name": str(game["T_PIT_P_NM"]).strip(),
            },
            "home": {
                "team": home_code,
                "playerId": game["B_PIT_P_ID"],
                "name": str(game["B_PIT_P_NM"]).strip(),
            },
        }
        analysis = await self._post(
            client,
            "/ws/Schedule.asmx/GetPitcherRecordAnalysis",
            {
                **params,
                "awayTeamId": away_code,
                "awayPitId": str(game["T_PIT_P_ID"]),
                "homeTeamId": home_code,
                "homePitId": str(game["B_PIT_P_ID"]),
                "groupSc": "SEASON",
            },
            referer,
        )
        return starters, analysis

    def _entries(self, table_json: str | dict | list, team_code: str) -> list[LineupEntry]:
        if isinstance(table_json, list):
            table_json = table_json[0] if table_json else {}
        table = json.loads(table_json) if isinstance(table_json, str) else table_json
        entries: list[LineupEntry] = []
        for row in table.get("rows", []):
            values = [str(cell.get("Text", "")).strip() for cell in row.get("row", [])]
            if len(values) >= 4 and values[0].isdigit():
                entries.append(
                    LineupEntry(team_code, int(values[0]), values[1], values[2], values[3] or None)
                )
        return entries

    async def _post(
        self, client: httpx.AsyncClient, path: str, data: dict[str, str], referer: str
    ) -> object:
        response = await client.post(
            f"{self.config.kbo_base_url}{path}",
            data=data,
            headers={"Referer": referer, "X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        return response.json()
