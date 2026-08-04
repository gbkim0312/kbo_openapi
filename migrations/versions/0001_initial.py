"""initial schema

Revision ID: 0001_initial
"""
from alembic import op
from app.adapters.outbound.persistence.models.base import Base
from app.adapters.outbound.persistence.models import team, game, game_revision, raw_snapshot, collection_job  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None: Base.metadata.create_all(op.get_bind())
def downgrade() -> None: Base.metadata.drop_all(op.get_bind())
