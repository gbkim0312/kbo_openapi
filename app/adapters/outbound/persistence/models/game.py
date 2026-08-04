from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class GameModel(TimestampMixin, Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("away_score IS NULL OR away_score >= 0", name="away_score_nonnegative"),
        CheckConstraint("home_score IS NULL OR home_score >= 0", name="home_score_nonnegative"),
        CheckConstraint("away_team_id != home_team_id", name="different_teams"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        Index("uq_games_source_game_id", "source", "source_game_id", unique=True, postgresql_where="source_game_id IS NOT NULL"),
        Index("ix_games_natural", "season", "league_type", "game_date", "away_team_id", "home_team_id", "scheduled_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    source_game_id: Mapped[str | None] = mapped_column(String(100))
    season: Mapped[int] = mapped_column(Integer)
    league_type: Mapped[str] = mapped_column(String(30))
    game_date: Mapped[date] = mapped_column(Date)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stadium: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    source_status_text: Mapped[str | None] = mapped_column(String(100))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_score: Mapped[int | None] = mapped_column(Integer)
    inning: Mapped[str | None] = mapped_column(String(30))
    result_text: Mapped[str | None] = mapped_column(Text)
    winning_pitcher: Mapped[str | None] = mapped_column(String(100))
    losing_pitcher: Mapped[str | None] = mapped_column(String(100))
    save_pitcher: Mapped[str | None] = mapped_column(String(100))
    attendance: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    canonical_hash: Mapped[str] = mapped_column(String(64))
    away_team = relationship("TeamModel", foreign_keys=[away_team_id])
    home_team = relationship("TeamModel", foreign_keys=[home_team_id])
