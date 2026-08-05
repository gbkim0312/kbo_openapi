from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GameLineupSnapshotModel(Base):
    __tablename__ = "game_lineup_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    confirmed: Mapped[bool] = mapped_column(Boolean)
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GameLineupEntryModel(Base):
    __tablename__ = "game_lineup_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("game_lineup_snapshots.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    batting_order: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(50))
    player_name: Mapped[str] = mapped_column(String(100))
    war: Mapped[str | None] = mapped_column(String(20))


class GamePreviewAnalysisModel(Base):
    __tablename__ = "game_preview_analyses"
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
