import asyncio
import json
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
from app.domain.enums.game_status import GameStatus
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
                        await asyncio.sleep(self._retry_delay(attempt, response))
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
                await asyncio.sleep(self._retry_delay(attempt))
        raise SourceTransportError("HTTP retries exhausted")

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        retry_after = response.headers.get("Retry-After") if response else None
        try:
            requested = float(retry_after) if retry_after else 30.0 * (2**attempt)
        except ValueError:
            requested = 30.0 * (2**attempt)
        return min(requested, float(self.config.kbo_refresh_failure_backoff_max_seconds))

    async def _fetch_game_ids(self, client: httpx.AsyncClient, target_date: date) -> dict:
        """Read game-center identity and live state for the target date."""
        try:
            response = await client.post(
                f"{self.config.kbo_base_url}/ws/Main.asmx/GetKboGameList",
                json={
                    "leId": "1",
                    "srId": "0,1,3,4,5,6,7,8,9",
                    "date": target_date.strftime("%Y%m%d"),
                },
                headers={
                    "Referer": f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/json; charset=UTF-8",
                },
            )
            response.raise_for_status()
            # KBO occasionally appends an HTML error page after a valid JSON body.
            body = response.text
            html_index = body.lower().find("<!doctype")
            payload = json.loads(body[:html_index] if html_index >= 0 else body)
            rows = payload.get("game", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            return {}
        return {
            (row["AWAY_ID"], row["HOME_ID"]): row
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
            live = game_ids.get((game.away_team_code, game.home_team_code))
            # Keep accepting the old string mapping for unit callers and
            # deployments that only provide game-center IDs.
            if isinstance(live, dict):
                game_id = game.source_game_id or live.get("G_ID")
            else:
                game_id = game.source_game_id or live
            if isinstance(live, dict):
                game = self._apply_live_state(game, live)
            if game_id and game_id != game.source_game_id:
                source_url = (
                    f"{self.config.kbo_base_url}/Schedule/GameCenter/Main.aspx?"
                    f"gameDate={target_date:%Y%m%d}&gameId={game_id}&section=PREVIEW"
                )
                result.append(replace(game, source_game_id=game_id, source_url=source_url))
            else:
                result.append(game)
        return result

    @staticmethod
    def _apply_live_state(game: SourceGame, live: dict[str, object]) -> SourceGame:
        """Apply only explicit game-center state; never infer live from 0:0."""
        status = game.status
        source_status_text = game.source_status_text
        cancel_code = str(live.get("CANCEL_SC_ID") or "0")
        if cancel_code != "0":
            status, source_status_text = GameStatus.CANCELED, str(
                live.get("CANCEL_SC_NM") or "취소"
            )
        elif str(live.get("GAME_RESULT_CK") or "0") == "1":
            status, source_status_text = GameStatus.COMPLETED, "경기종료"
        elif str(live.get("GAME_STATE_SC") or "") == "2":
            status, source_status_text = GameStatus.IN_PROGRESS, "경기중"

        def score(key: str) -> int | None:
            if str(live.get("SCORE_CK") or "0") != "1":
                return None
            value = live.get(key)
            return int(value) if value is not None and str(value).strip().isdigit() else None

        inning = game.inning
        inning_number = live.get("GAME_INN_NO")
        inning_side = str(live.get("GAME_TB_SC_NM") or "").strip()
        if inning_number not in (None, "") and str(inning_number).isdigit():
            inning = f"{inning_number}회{inning_side}" if inning_side else f"{inning_number}회"
        return replace(
            game,
            status=status,
            source_status_text=source_status_text,
            away_score=score("T_SCORE_CN"),
            home_score=score("B_SCORE_CN"),
            inning=inning,
        )
