"""Parser for KBO's GetScheduleList JSON response (observed 2026-08-05)."""

import json
import re
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.adapters.outbound.sources.exceptions import SourceNoGames, SourceSchemaChangedError
from app.adapters.outbound.sources.parser.status_mapper import map_status
from app.adapters.outbound.sources.parser.team_mapper import normalize_team
from app.application.dto.source_game import SourceGame
from app.domain.enums.game_status import GameStatus
from app.domain.enums.league_type import LeagueType

SEOUL = ZoneInfo("Asia/Seoul")
_DAY = re.compile(r"(?P<month>\d{2})\.(?P<day>\d{2})")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


class KboScheduleParser:
    version = "kbo-schedule-json-v1"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def parse(self, body: str, target_date: date) -> list[SourceGame]:
        try:
            payload = json.loads(body)
            rows = payload["rows"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise SourceSchemaChangedError("GetScheduleList does not contain rows") from error
        if not isinstance(rows, list):
            raise SourceSchemaChangedError("rows is not a list")
        current_date: date | None = None
        games: list[SourceGame] = []
        for item in rows:
            cells = item.get("row") if isinstance(item, dict) else None
            if not isinstance(cells, list):
                raise SourceSchemaChangedError("schedule row has no cells")
            values = {
                str(cell.get("Class") or f"cell_{index}"): str(cell.get("Text") or "")
                for index, cell in enumerate(cells)
                if isinstance(cell, dict)
            }
            day = values.get("day")
            if day:
                match = _DAY.search(BeautifulSoup(day, "html.parser").get_text(" ", strip=True))
                if not match:
                    raise SourceSchemaChangedError("unparseable schedule day")
                current_date = date(target_date.year, int(match["month"]), int(match["day"]))
            if current_date != target_date:
                continue
            game = self._parse_game(values, current_date)
            if game is not None:
                games.append(game)
        if not games and any(self._is_target_day(row, target_date) for row in rows):
            raise SourceNoGames()
        return games

    def _is_target_day(self, row: object, target_date: date) -> bool:
        if not isinstance(row, dict):
            return False
        for cell in row.get("row", []):
            if isinstance(cell, dict) and cell.get("Class") == "day":
                return f"{target_date.month:02d}.{target_date.day:02d}" in str(cell.get("Text", ""))
        return False

    def _parse_game(self, values: dict[str, str], game_date: date) -> SourceGame | None:
        play_html = values.get("play")
        if not play_html:
            raise SourceSchemaChangedError("schedule row has no play cell")
        play = BeautifulSoup(play_html, "html.parser")
        spans = [node.get_text(strip=True) for node in play.find_all("span", recursive=False)]
        if len(spans) < 2:
            raise SourceSchemaChangedError("play cell has no teams")
        away, home = normalize_team(spans[0]), normalize_team(spans[-1])
        score_spans = play.select("em span")
        numeric = [
            int(node.get_text(strip=True))
            for node in score_spans
            if node.get_text(strip=True).isdigit()
        ]
        away_score, home_score = (numeric[0], numeric[1]) if len(numeric) == 2 else (None, None)
        note = values.get("cell_8", "").strip()
        status = self._status(note, away_score, home_score)
        scheduled_at = self._scheduled_at(values.get("time", ""), game_date)
        source_game_id, source_url = self._game_link(values.get("relay", ""))
        return SourceGame(
            source="kbo-http",
            source_game_id=source_game_id,
            season=game_date.year,
            league_type=LeagueType.REGULAR,
            game_date=game_date,
            scheduled_at=scheduled_at,
            stadium=values.get("cell_7") or None,
            status=status,
            source_status_text=note or None,
            away_team_code=away.code,
            away_team_name=away.name,
            home_team_code=home.code,
            home_team_name=home.name,
            away_score=away_score,
            home_score=home_score,
            result_text=note or None,
            source_url=source_url,
            source_updated_at=None,
        )

    def _scheduled_at(self, html: str, game_date: date) -> datetime | None:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        match = _TIME.match(text)
        return (
            datetime(
                game_date.year,
                game_date.month,
                game_date.day,
                int(match[1]),
                int(match[2]),
                tzinfo=SEOUL,
            )
            if match
            else None
        )

    def _game_link(self, html: str) -> tuple[str | None, str | None]:
        anchor = BeautifulSoup(html, "html.parser").find("a", href=True)
        if anchor is None:
            return None, None
        url = urljoin(self.base_url, str(anchor["href"]))
        return parse_qs(urlparse(url).query).get("gameId", [None])[0], url

    def _status(self, note: str, away_score: int | None, home_score: int | None) -> GameStatus:
        if note and note != "-":
            return map_status(note)
        return (
            GameStatus.COMPLETED
            if away_score is not None and home_score is not None
            else GameStatus.SCHEDULED
        )
