from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class CollectionJobModel(TimestampMixin, Base):
    __tablename__ = "collection_jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(30)); target_date: Mapped[date] = mapped_column(Date); source: Mapped[str] = mapped_column(String(30)); status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1); fetched_count: Mapped[int] = mapped_column(Integer, default=0); inserted_count: Mapped[int] = mapped_column(Integer, default=0); updated_count: Mapped[int] = mapped_column(Integer, default=0); unchanged_count: Mapped[int] = mapped_column(Integer, default=0); failed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50)); error_message: Mapped[str | None] = mapped_column(Text)
