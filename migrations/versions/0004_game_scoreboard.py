"""add live scoreboard snapshot

Revision ID: 0004_game_scoreboard
Revises: 0003_preview
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_game_scoreboard"
down_revision = "0003_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("scoreboard", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "scoreboard")

