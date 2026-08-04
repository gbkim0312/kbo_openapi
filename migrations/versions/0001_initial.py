"""initial schema

Revision ID: 0001_initial
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.adapters.outbound.persistence.models.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())
    now = datetime.now(UTC)
    teams = sa.table(
        "teams",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("short_name", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        teams,
        [
            {
                "code": code,
                "name": name,
                "short_name": short,
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
            for code, name, short in [
                ("LG", "LG 트윈스", "LG"),
                ("HH", "한화 이글스", "한화"),
                ("SK", "SSG 랜더스", "SSG"),
                ("SS", "삼성 라이온즈", "삼성"),
                ("NC", "NC 다이노스", "NC"),
                ("KT", "KT 위즈", "KT"),
                ("LT", "롯데 자이언츠", "롯데"),
                ("HT", "KIA 타이거즈", "KIA"),
                ("OB", "두산 베어스", "두산"),
                ("WO", "키움 히어로즈", "키움"),
            ]
        ],
    )


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
