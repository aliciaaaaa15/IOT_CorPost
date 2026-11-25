from sqlalchemy.dialects.postgresql import insert

from app.models.reading import Reading


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