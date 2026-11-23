from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.weekly_report import WeeklyReport


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    # Plain column, no FK (readings.device_id is not unique)
    device_id: Mapped[str | None] = mapped_column(String(32), unique=True)

    # Deleting a user also deletes their reports
    weekly_reports: Mapped[list["WeeklyReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
