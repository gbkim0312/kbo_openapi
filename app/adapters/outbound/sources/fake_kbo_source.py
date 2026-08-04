from datetime import date

from app.application.dto.source_game import SourceGame


class FakeKboSource:
    def __init__(self, games: list[SourceGame] | None = None) -> None:
        self.games = games or []

    async def fetch_games(self, target_date: date) -> list[SourceGame]:
        return [g for g in self.games if g.game_date == target_date]
