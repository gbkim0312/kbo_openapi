"""add record snapshots

Revision ID: 0002_records
Revises: 0001_initial
"""

from alembic import op

from app.adapters.outbound.persistence.models.record import (
    AwardModel,
    GameDetailModel,
    GamePitcherRecordModel,
    PlayerSeasonStatModel,
    TeamRankSnapshotModel,
)

revision = "0002_records"
down_revision = "0001_initial"
branch_labels = None
depends_on = None
MODELS = (
    TeamRankSnapshotModel,
    PlayerSeasonStatModel,
    GamePitcherRecordModel,
    GameDetailModel,
    AwardModel,
)


def upgrade() -> None:
    for model in MODELS:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for model in reversed(MODELS):
        model.__table__.drop(op.get_bind(), checkfirst=True)
