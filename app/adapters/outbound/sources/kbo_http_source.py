import asyncio
from dataclasses import replace
from datetime import date

import httpx

from app.adapters.outbound.sources.exceptions import (
    SourceConfigurationError,
    SourceNoGames,
    SourceSchemaChangedError,
    SourceTransportError,
)
from app.application.dto.source_game import SourceGame
from app.application.ports.outbound.game_source import GameSource
from app.infrastructure.config import Settings


class KboHttpSource(GameSource):
    """Transport adapter. Parsing is deliberately injected after endpoint investigation."""

    def __init__(
        self, config: Settings, parser: object | None = None, snapshots: object | None = None
    ) -> None:
        self.config, self.parser, self.snapshots = config, parser, snapshots

    async def fetch_games(self, target_date: date) -> list[SourceGame]:
        if not self.config.kbo_schedule_url:
            raise SourceConfigurationError("KBO_SCHEDULE_URL is not configured")
        timeout = httpx.Timeout(
            self.config.kbo_total_timeout_seconds,
            connect=self.config.kbo_connect_timeout_seconds,
            read=self.config.kbo_read_timeout_seconds,
        )
        headers = {"User-Agent": self.config.kbo_user_agent}
        for attempt in range(self.config.kbo_max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=timeout, headers=headers, follow_redirects=True
                ) as client:
                    schedule_page = (
                        f"{self.config.kbo_base_url}/Schedule/Schedule.aspx?"
                        f"year={target_date.year}&month={target_date.month:02d}"
                    )
                    await client.get(schedule_page)
                    response = await client.post(
                        self.config.kbo_schedule_url,
                        data={
                            "leId": "1",
                            "srIdList": "0,9,6",
                            "seasonId": str(target_date.year),
                            "gameMonth": f"{target_date.month:02d}",
                            "teamId": "",
                        },
                        headers={"Referer": schedule_page, "X-Requested-With": "XMLHttpRequest"},
                    )
                    game_ids = await self._fetch_game_ids(client, target_date)
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    if attempt + 1 < self.config.kbo_max_retries:
                        await asyncio.sleep(float(response.headers.get("Retry-After", 2**attempt)))
                        continue
                    raise SourceTransportError(f"HTTP {response.status_code}")
                response.raise_for_status()
                if self.parser is None:
                    raise SourceConfigurationError("No KBO parser has been configured")
                snapshot_id = None
                if self.snapshots and self.config.raw_snapshot_enabled:
                    snapshot_id = await self.snapshots.save_http(  # type: ignore[attr-defined]
                        target_date,
                        str(response.url),
                        response.status_code,
                        dict(response.headers),
                        response.text,
                    )
                try:
                    games = self.parser.parse(response.text, target_date)  # type: ignore[attr-defined]
                except SourceSchemaChangedError as error:
                    if snapshot_id:
                        await self.snapshots.mark(snapshot_id, False, type(error).__name__)  # type: ignore[attr-defined]
                    raise
                if snapshot_id:
                    await self.snapshots.mark(snapshot_id, True)  # type: ignore[attr-defined]
                return self._enrich_game_ids(games, game_ids, target_date)
            except SourceNoGames:
                return []
            except SourceSchemaChangedError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt + 1 == self.config.kbo_max_retries:
                    raise SourceTransportError(str(error)) from error
                await asyncio.sleep(2**attempt)
        raise SourceTransportError("HTTP retries exhausted")

    async def _fetch_game_ids(self, client: httpx.AsyncClient, target_date: date) -> dict:
        """Read game-center IDs, which KBO omits from some schedule rows before a relay exists."""
        try:
            response = await client.post(
                f"{self.config.kbo_base_url}/ws/Main.asmx/GetKboGameList",
                data={
                    "leId": "1",
                    "srId": "0,1,3,4,5,6,7,8,9",
                    "date": target_date.strftime("%Y%m%d"),
                },
                headers={
                    "Referer": f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            response.raise_for_status()
            rows = response.json().get("game", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            return {}
        return {
            (row["AWAY_ID"], row["HOME_ID"]): row["G_ID"]
            for row in rows
            if isinstance(row, dict)
            and row.get("AWAY_ID")
            and row.get("HOME_ID")
            and row.get("G_ID")
        }

    def _enrich_game_ids(
        self, games: list[SourceGame], game_ids: dict, target_date: date
    ) -> list[SourceGame]:
        result: list[SourceGame] = []
        for game in games:
            game_id = game.source_game_id or game_ids.get(
                (game.away_team_code, game.home_team_code)
            )
            if game_id and game_id != game.source_game_id:
                source_url = (
                    f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx?"
                    f"gameDate={target_date:%Y%m%d}&gameId={game_id}&section=PREVIEW"
                )
                result.append(replace(game, source_game_id=game_id, source_url=source_url))
            else:
                result.append(game)
        return result
