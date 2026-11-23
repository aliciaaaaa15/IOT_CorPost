from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from app.models.user import User


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))  # pending | ready | failed
    week_start: Mapped[date] = mapped_column(Date)   # Monday
    week_end: Mapped[date] = mapped_column(Date)     # Sunday
    report_content: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="weekly_reports")
