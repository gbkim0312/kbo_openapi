from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.adapters.outbound.persistence.models.base import Base
from app.adapters.outbound.persistence.models.collection_job import CollectionJobModel
from app.adapters.outbound.persistence.models.game import GameModel
from app.adapters.outbound.persistence.models.game_revision import GameRevisionModel
from app.adapters.outbound.persistence.models.raw_snapshot import RawSnapshotModel
from app.adapters.outbound.persistence.models.team import TeamModel
from app.infrastructure.config import settings

config = context.config
if config.config_file_name and config.get_section("loggers"):
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "+psycopg"))
target_metadata = Base.metadata
MODELS = (TeamModel, GameModel, GameRevisionModel, RawSnapshotModel, CollectionJobModel)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
