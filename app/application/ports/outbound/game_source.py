from datetime import date
from typing import Protocol

from app.application.dto.source_game import SourceGame


class GameSource(Protocol):
    async def fetch_games(self, target_date: date) -> list[SourceGame]: ...
