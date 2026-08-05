"""add lineup and preview analysis

Revision ID: 0003_preview
Revises: 0002_records
"""

from alembic import op

from app.adapters.outbound.persistence.models.preview import (
    GameLineupEntryModel,
    GameLineupSnapshotModel,
    GamePreviewAnalysisModel,
)

revision = "0003_preview"
down_revision = "0002_records"
branch_labels = None
depends_on = None
MODELS = (GameLineupSnapshotModel, GameLineupEntryModel, GamePreviewAnalysisModel)


def upgrade() -> None:
    for model in MODELS:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for model in reversed(MODELS):
        model.__table__.drop(op.get_bind(), checkfirst=True)
