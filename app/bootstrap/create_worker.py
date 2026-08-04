from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.outbound.persistence.database import make_session_factory
from app.adapters.outbound.persistence.repositories.sqlalchemy_raw_snapshot_repository import (
    SqlAlchemyRawSnapshotRepository,
)
from app.adapters.outbound.sources.kbo_http_source import KboHttpSource
from app.adapters.outbound.sources.parser.game_parser import KboScheduleParser
from app.application.use_cases.collect_games import CollectGamesUseCase
from app.infrastructure.config import Settings, settings


def create_collect_use_case(config: Settings = settings) -> CollectGamesUseCase:
    sessions: async_sessionmaker = make_session_factory(config.database_url)
    snapshots = SqlAlchemyRawSnapshotRepository(sessions, config.raw_snapshot_max_bytes)
    source = KboHttpSource(config, KboScheduleParser(config.kbo_base_url), snapshots)
    return CollectGamesUseCase(source, sessions)
