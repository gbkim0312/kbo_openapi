from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class RawSnapshotModel(Base):
    __tablename__ = "raw_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(30)); target_date: Mapped[date | None] = mapped_column(Date)
    request_url: Mapped[str] = mapped_column(Text); request_method: Mapped[str] = mapped_column(String(10))
    request_params: Mapped[dict[str, Any] | None] = mapped_column(JSON); response_status: Mapped[int | None] = mapped_column(Integer)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON); response_body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64)); collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parser_version: Mapped[str | None] = mapped_column(String(50)); parse_status: Mapped[str] = mapped_column(String(20)); parse_error: Mapped[str | None] = mapped_column(Text)
