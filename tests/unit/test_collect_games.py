from types import SimpleNamespace

from app.application.use_cases.collect_games import CollectGamesUseCase


def test_backfills_game_center_identity_without_changing_game_revision() -> None:
    game = SimpleNamespace(source_game_id=None, source_url=None)
    source_game = SimpleNamespace(
        source_game_id="20260805HHSS0",
        source_url="https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?gameId=20260805HHSS0",
    )

    CollectGamesUseCase._enrich_source_identity(game, source_game)

    assert game.source_game_id == "20260805HHSS0"
    assert game.source_url == (
        "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?gameId=20260805HHSS0"
    )
