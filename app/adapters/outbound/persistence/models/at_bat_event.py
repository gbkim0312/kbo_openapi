from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AtBatEventModel(Base):
    __tablename__ = "at_bat_events"
    __table_args__ = (
        Index(
            "uq_at_bat_events_source_key", "game_id", "source_event_no", "source_seqno", unique=True
        ),
        Index("ix_at_bat_events_game_order", "game_id", "source_event_no", "source_seqno"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    source_event_no: Mapped[int] = mapped_column(Integer)
    source_seqno: Mapped[int] = mapped_column(Integer)
    inning: Mapped[int | None] = mapped_column(Integer)
    half: Mapped[str | None] = mapped_column(String(10))
    batter_id: Mapped[str | None] = mapped_column(String(50))
    batter_name: Mapped[str | None] = mapped_column(String(100))
    team_code: Mapped[str | None] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(30))
    result_text: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    runs: Mapped[int | None] = mapped_column(Integer)
    rbi: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict | None] = mapped_column(JSON)
