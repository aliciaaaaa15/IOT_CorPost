from sqlalchemy.dialects.postgresql import insert

from app.models.reading import Reading
from datetime import datetime
from sqlalchemy import and_, func, or_, select
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


def aggregate_readings(
    db: Session,
    device_id: str,
    date_from: datetime,
    date_to: datetime,
    group_by: str,  # "hour" | "day" | "week" | "month"
) -> list:
    
    bucket = func.date_trunc(group_by, Reading.timestamp, "UTC").label("start")
    valid = Reading.status.in_((0, 1))  # OK or BAD (not INVALID)

    stmt = (
        select(
            bucket,
            func.count().label("total_readings"),
            func.count().filter(valid).label("valid_readings"),
            func.count().filter(Reading.status == 0).label("good_readings"),
            func.count().filter(Reading.status == 1).label("bad_readings"),
            func.count().filter(Reading.status == 2).label("invalid_readings"),
            func.avg(Reading.angle_deg).filter(valid).label("avg_angle_deg"),
            func.max(Reading.angle_deg).filter(valid).label("max_angle_deg"),
        )
        .where(
            Reading.device_id == device_id,
            Reading.timestamp >= date_from,
            Reading.timestamp <= date_to,
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    
    return list(db.execute(stmt).all())
