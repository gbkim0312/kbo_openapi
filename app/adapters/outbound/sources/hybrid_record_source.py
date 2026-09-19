from __future__ import annotations

import logging

from app.adapters.outbound.sources.kbo_record_source import KboRecordSource
from app.adapters.outbound.sources.naver_sports_source import NaverSportsSource


class HybridRecordSource:
    """Use KBO as the authority and Naver as a live scoreboard fallback."""

    def __init__(self, kbo: KboRecordSource, naver: NaverSportsSource) -> None:
        self.kbo, self.naver = kbo, naver
        self.config = kbo.config
        self.logger = logging.getLogger(__name__)

    async def fetch_scoreboard(self, source_game_id: str, season: int) -> dict | None:
        provider = self.config.scoreboard_provider.lower()
        if provider == "naver":
            return await self.naver.fetch_scoreboard(source_game_id, season)
        if provider == "kbo":
            return await self.kbo.fetch_scoreboard(source_game_id, season)
        if provider != "hybrid":
            raise ValueError("SCOREBOARD_PROVIDER must be kbo, naver, or hybrid")

        try:
            scoreboard = await self.kbo.fetch_scoreboard(source_game_id, season)
        except Exception:
            self.logger.exception(
                "KBO scoreboard failed; trying Naver fallback",
                extra={"source_game_id": source_game_id},
            )
            scoreboard = None
        if self._has_data(scoreboard):
            return scoreboard
        if not self.config.naver_sports_enabled:
            return scoreboard
        try:
            return await self.naver.fetch_scoreboard(source_game_id, season)
        except Exception:
            self.logger.exception(
                "Naver live scoreboard fallback failed",
                extra={"source_game_id": source_game_id},
            )
            return scoreboard

    async def fetch_box_score(self, source_game_id: str, season: int):
        return await self.kbo.fetch_box_score(source_game_id, season)

    async def fetch_team_ranks(self):
        return await self.kbo.fetch_team_ranks()

    async def fetch_player_stats(self, role: str):
        return await self.kbo.fetch_player_stats(role)

    async def fetch_season_awards(self):
        return await self.kbo.fetch_season_awards()

    @staticmethod
    def _has_data(scoreboard: dict | None) -> bool:
        if not scoreboard:
            return False
        innings = scoreboard.get("innings")
        totals = scoreboard.get("totals")
        return bool(innings) or any(
            isinstance(side, dict) and any(value is not None for value in side.values())
            for side in (totals or {}).values()
        )
