from datetime import date

from app.adapters.outbound.sources.exceptions import (
    SourceNoGames,
    SourceSchemaChangedError,
    SourceTransportError,
)
from app.application.dto.source_game import SourceGame
from app.application.ports.outbound.game_source import GameSource
from app.domain.exceptions import SourceUnavailableError


class CompositeKboSource(GameSource):
    def __init__(
        self,
        http: GameSource,
        cli: GameSource | None = None,
        playwright: GameSource | None = None,
        fallback_on_schema_error: bool = True,
    ) -> None:
        self.http, self.cli, self.playwright, self.fallback_on_schema_error = (
            http,
            cli,
            playwright,
            fallback_on_schema_error,
        )

    async def fetch_games(self, target_date: date) -> list[SourceGame]:
        try:
            return await self.http.fetch_games(target_date)
        except SourceNoGames:
            return []
        except SourceSchemaChangedError:
            if not self.fallback_on_schema_error:
                raise SourceUnavailableError() from None
        except SourceTransportError:
            pass
        if self.cli:
            try:
                return await self.cli.fetch_games(target_date)
            except (SourceTransportError, SourceSchemaChangedError):
                pass
        if self.playwright:
            return await self.playwright.fetch_games(target_date)
        raise SourceUnavailableError()
