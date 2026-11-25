from sqlalchemy.dialects.postgresql import insert

from app.models.reading import Reading
from datetime import datetime
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session


def insert_readings(db, rows: list[dict]) -> int:
    """Insert rows, skipping existing (device_id, timestamp). Returns how many were inserted."""
    stmt = (
        insert(Reading)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["device_id", "timestamp"])
        .returning(Reading.timestamp)
    )
    inserted = len(db.execute(stmt).all())
    db.commit()
    return inserted


def load_readings(
    db, 
    device_id: str,
    date_from: datetime, 
    date_to: datetime,
    limit: int = 100,
) -> tuple[list, datetime | None]:

    conditions = [
        Reading.device_id == device_id,
        Reading.timestamp >= date_from,
        Reading.timestamp <= date_to,
    ]

    stmt = (
        select(Reading.timestamp, Reading.angle_deg, Reading.status)
        .where(and_(*conditions))
        .order_by(Reading.timestamp.asc())
        .limit(limit + 1)
    )

    rows = list(db.execute(stmt).all())

    next_cursor = None
    readings = rows[:limit]

    if len(rows) > limit: 
        next_cursor = rows[-1].timestamp

    return readings, next_cursor
