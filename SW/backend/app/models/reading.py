from datetime import datetime
from sqlalchemy import REAL, DateTime, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Reading(Base):
    __tablename__ = "readings"

    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    acc_x: Mapped[int] = mapped_column(SmallInteger)   # mg
    acc_y: Mapped[int] = mapped_column(SmallInteger)
    acc_z: Mapped[int] = mapped_column(SmallInteger)
    gyro_x: Mapped[int] = mapped_column(SmallInteger)  # 1/16 °/s
    gyro_y: Mapped[int] = mapped_column(SmallInteger)
    gyro_z: Mapped[int] = mapped_column(SmallInteger)
    angle: Mapped[float] = mapped_column(REAL)         # degrees
    status: Mapped[int] = mapped_column(SmallInteger)  # 0 OK, 1 BAD, 2 INVALID
    battery: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # None if 0xFF