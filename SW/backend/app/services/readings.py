from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.core.exceptions import ConflictException

from app.validation.validators import validate_batch, validate_datetime_range

from app.repositories import reading as readings_repository


from app.schemas.readings import (
    BatchInput,
    ReadingsLoadInput,
)
from app.models.user import User

MAX_LOADED_READINGS_PER_REQUEST = 100

def store_batch(
    batch: BatchInput,
    db: Session,
    current_user: User
):
    # validate user has a device associated
    if current_user.device_id is None:
        raise ConflictException(
            ResponseCode.DEVICE_NOT_LINKED,
            "User has no device linked.",
        )

    # validate batch data
    valid_batch_readings, invalid_batch_readings = validate_batch(batch)

    # prepare rows for db insert: payload fields match the Reading columns,
    # so only device_id is added and timestamp is converted (epoch -> datetime UTC)
    rows = [
        {
            **r.model_dump(),
            "device_id": current_user.device_id,
            "timestamp": datetime.fromtimestamp(r.timestamp, tz=UTC),
        }
        for r in valid_batch_readings
    ]

    # add batch to db (filters duplicates)
    inserted = readings_repository.insert_readings(db, rows) if rows else 0

    return {
        "inserted": inserted,
        "duplicated": len(valid_batch_readings) - inserted,
        "rejected": [
            {"timestamp": timestamp, "code": code}
            for timestamp, code in invalid_batch_readings
        ],
    }


def load_readings(
    db: Session,
    current_user: User,
    data: ReadingsLoadInput,
):
    # validate user has a device associated
    if current_user.device_id is None:
        raise ConflictException(
            ResponseCode.DEVICE_NOT_LINKED,
            "User has no device linked.",
        )

    # validate data range selected
    date_from, date_to = validate_datetime_range(
        data.date_from, 
        data.date_to,
    )

    # load readings from db
    readings, next_cursor = readings_repository.load_readings(
        db,
        current_user.device_id,
        date_from,
        date_to,
        MAX_LOADED_READINGS_PER_REQUEST
    )

    return {
        "readings": [
            {"timestamp": timestamp, "angle_deg": angle_deg, "status": status}
            for timestamp, angle_deg, status in readings
        ],
        "next_cursor": next_cursor,
    }

