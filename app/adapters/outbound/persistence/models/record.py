from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TeamRankSnapshotModel(Base):
    __tablename__ = "team_rank_snapshots"
    __table_args__ = (UniqueConstraint("as_of_date", "team_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    rank: Mapped[int] = mapped_column(Integer)
    games: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer)
    losses: Mapped[int] = mapped_column(Integer)
    draws: Mapped[int] = mapped_column(Integer)
    winning_pct: Mapped[str] = mapped_column(String(16))
    games_behind: Mapped[str] = mapped_column(String(16))
    recent_ten: Mapped[str] = mapped_column(String(30))
    streak: Mapped[str] = mapped_column(String(30))
    home_record: Mapped[str] = mapped_column(String(30))
    away_record: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlayerSeasonStatModel(Base):
    __tablename__ = "player_season_stats"
    __table_args__ = (UniqueConstraint("season", "role", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    player_id: Mapped[int] = mapped_column(Integer)
    player_name: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    rank: Mapped[int | None] = mapped_column(Integer)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GamePitcherRecordModel(Base):
    __tablename__ = "game_pitcher_records"
    __table_args__ = (UniqueConstraint("game_id", "team_id", "player_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    appearance: Mapped[str] = mapped_column(String(30))
    result: Mapped[str | None] = mapped_column(String(30))
    innings: Mapped[str | None] = mapped_column(String(20))
    pitches: Mapped[int | None] = mapped_column(Integer)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GameDetailModel(Base):
    __tablename__ = "game_details"
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True)
    decisive_hit_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AwardModel(Base):
    __tablename__ = "awards"
    __table_args__ = (UniqueConstraint("season", "award_type", "player_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer)
    award_type: Mapped[str] = mapped_column(String(50))
    player_name: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    position: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
