"""store normalized completed at-bat relay events

Revision ID: 0005_at_bat_events
Revises: 0004_game_scoreboard
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_at_bat_events"
down_revision = "0004_game_scoreboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "at_bat_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_event_no", sa.Integer(), nullable=False),
        sa.Column("source_seqno", sa.Integer(), nullable=False),
        sa.Column("inning", sa.Integer()),
        sa.Column("half", sa.String(10)),
        sa.Column("batter_id", sa.String(50)),
        sa.Column("batter_name", sa.String(100)),
        sa.Column("team_code", sa.String(20)),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("result_text", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("runs", sa.Integer()),
        sa.Column("rbi", sa.Integer()),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", sa.JSON()),
    )
    op.create_index(
        "uq_at_bat_events_source_key",
        "at_bat_events",
        ["game_id", "source_event_no", "source_seqno"],
        unique=True,
    )
    op.create_index(
        "ix_at_bat_events_game_order",
        "at_bat_events",
        ["game_id", "source_event_no", "source_seqno"],
    )


def downgrade() -> None:
    op.drop_index("ix_at_bat_events_game_order", table_name="at_bat_events")
    op.drop_index("uq_at_bat_events_source_key", table_name="at_bat_events")
    op.drop_table("at_bat_events")
