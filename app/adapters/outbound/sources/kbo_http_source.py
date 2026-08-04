import asyncio
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
                return games
            except SourceNoGames:
                return []
            except SourceSchemaChangedError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt + 1 == self.config.kbo_max_retries:
                    raise SourceTransportError(str(error)) from error
                await asyncio.sleep(2**attempt)
        raise SourceTransportError("HTTP retries exhausted")
