import json
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.adapters.outbound.sources.parser.team_mapper import normalize_team
from app.infrastructure.config import Settings


@dataclass(frozen=True, slots=True)
class TeamRank:
    as_of_date: date
    team_code: str
    rank: int
    games: int
    wins: int
    losses: int
    draws: int
    winning_pct: str
    games_behind: str
    recent_ten: str
    streak: str
    home_record: str
    away_record: str


@dataclass(frozen=True, slots=True)
class PlayerStat:
    season: int
    role: str
    player_id: int
    player_name: str
    team_code: str
    rank: int | None
    stats: dict[str, str]


@dataclass(frozen=True, slots=True)
class SeasonAward:
    season: int
    award_type: str
    player_name: str
    team_code: str | None
    position: str


class KboRecordSource:
    def __init__(self, config: Settings) -> None:
        self.config = config

    async def fetch_team_ranks(self) -> list[TeamRank]:
        url = f"{self.config.kbo_base_url}/Record/TeamRank/TeamRankDaily.aspx"
        body = await self._get(url)
        soup = BeautifulSoup(body, "html.parser")
        stamp = soup.select_one(".exp2")
        match = re.search(r"(\d{4})년\s*(\d{2})월\s*(\d{2})일", stamp.get_text() if stamp else "")
        if not match:
            raise ValueError("KBO team rank date is missing")
        as_of = date(*map(int, match.groups()))
        rows: list[TeamRank] = []
        rank_table = soup.select_one("table[summary^='순위, 팀명']")
        if rank_table is None:
            raise ValueError("KBO team rank table is missing")
        for row in rank_table.select("tbody tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) != 12:
                continue
            team = normalize_team(cells[1])
            rows.append(
                TeamRank(
                    as_of,
                    team.code,
                    int(cells[0]),
                    int(cells[2]),
                    int(cells[3]),
                    int(cells[4]),
                    int(cells[5]),
                    cells[6],
                    cells[7],
                    cells[8],
                    cells[9],
                    cells[10],
                    cells[11],
                )
            )
        if not rows:
            raise ValueError("KBO team rank rows are missing")
        return rows

    async def fetch_player_stats(self, role: str) -> list[PlayerStat]:
        if role not in {"hitter", "pitcher"}:
            raise ValueError("role must be hitter or pitcher")
        path = "HitterBasic" if role == "hitter" else "PitcherBasic"
        url = f"{self.config.kbo_base_url}/Record/Player/{path}/Basic1.aspx"
        soup = BeautifulSoup(await self._get(url), "html.parser")
        season_el = soup.select_one("select[id$='ddlSeason_ddlSeason'] option[selected]")
        if season_el is None:
            raise ValueError("KBO player stat season is missing")
        season = int(str(season_el.get("value")))
        table = soup.select_one("table.tData01.tt")
        if table is None:
            raise ValueError("KBO player stat table is missing")
        headers = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
        records: list[PlayerStat] = []
        for row in table.select("tbody tr"):
            cells = row.select("td")
            if len(cells) != len(headers):
                continue
            values = [cell.get_text(" ", strip=True).replace("\xa0", "") for cell in cells]
            link = cells[1].find("a", href=True)
            if link is None:
                continue
            player_id = parse_qs(urlparse(str(link["href"])).query).get("playerId", [None])[0]
            if player_id is None or not player_id.isdigit():
                continue
            stats = dict(zip(headers[3:], values[3:], strict=True))
            records.append(
                PlayerStat(
                    season,
                    role,
                    int(player_id),
                    values[1],
                    normalize_team(values[2]).code,
                    int(values[0]) if values[0].isdigit() else None,
                    stats,
                )
            )
        return records

    async def fetch_season_awards(self) -> list[SeasonAward]:
        url = f"{self.config.kbo_base_url}/Player/Awards/PlayerPrize.aspx"
        soup = BeautifulSoup(await self._get(url), "html.parser")
        table = soup.select_one("table[summary='MVP・신인상']")
        if table is None:
            raise ValueError("KBO award table is missing")
        awards: list[SeasonAward] = []
        for row in table.select("tbody tr"):
            cells = row.select("td")
            if len(cells) != 3 or not cells[0].get_text(strip=True).isdigit():
                continue
            values = [span.get_text(strip=True) for span in cells[1].select("span")]
            if len(values) == 3 and values[0] != "-":
                try:
                    team_code = normalize_team(values[1]).code
                except ValueError:
                    team_code = None
                awards.append(
                    SeasonAward(
                        int(cells[0].get_text(strip=True)),
                        "season_mvp",
                        values[0],
                        team_code,
                        values[2],
                    )
                )
        return awards

    async def fetch_box_score(
        self, source_game_id: str, season: int
    ) -> tuple[str | None, list[dict[str, object]]]:
        url = f"{self.config.kbo_base_url}/ws/Schedule.asmx/GetBoxScoreScroll"
        game_date = source_game_id[:8]
        referer = (
            f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx?"
            f"gameDate={game_date}&gameId={source_game_id}&section=REVIEW"
        )
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.kbo_user_agent},
            timeout=self.config.kbo_total_timeout_seconds,
            follow_redirects=True,
        ) as client:
            await client.get(referer)
            response = await client.post(
                url,
                data={"leId": "1", "srId": "0", "seasonId": str(season), "gameId": source_game_id},
                headers={"Referer": referer, "X-Requested-With": "XMLHttpRequest"},
            )
            response.raise_for_status()
        payload = response.json()
        detail = json.loads(payload["tableEtc"])
        decisive = next(
            (row["row"][1]["Text"] for row in detail["rows"] if row["row"][0]["Text"] == "결승타"),
            None,
        )
        records: list[dict[str, object]] = []
        for side, group in enumerate(payload["arrPitcher"]):
            table = json.loads(group["table"])
            headers = [item["Text"] for item in table["headers"][0]["row"]]
            for row in table["rows"]:
                vals = [item["Text"].replace("&nbsp;", "").strip() for item in row["row"]]
                records.append(
                    {
                        "side": side,
                        "player_name": vals[0],
                        "appearance": vals[1],
                        "result": vals[2] or None,
                        "innings": vals[6],
                        "pitches": int(vals[8]) if vals[8].isdigit() else None,
                        "stats": dict(zip(headers[3:], vals[3:], strict=True)),
                    }
                )
        return decisive, records

    async def _get(self, url: str) -> str:
        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.kbo_user_agent},
            timeout=self.config.kbo_total_timeout_seconds,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
