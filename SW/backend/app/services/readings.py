from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.core.exceptions import ConflictException

from app.validation.validators import validate_batch

from app.repositories import reading as readings_repository


from app.schemas.readings import (
    BatchInput,
    ReadingsLoadInput,
)
from app.models.user import User


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

    # convert timestamp to datetime and prepare data for db insert
    rows = [
        {
            "device_id": current_user.device_id,
            "timestamp": datetime.fromtimestamp(r.timestamp, tz=UTC),
            "acc_x": r.acc_x, "acc_y": r.acc_y, "acc_z": r.acc_z,
            "gyro_x": r.gyro_x, "gyro_y": r.gyro_y, "gyro_z": r.gyro_z,
            "angle": r.angle_deg,
            "status": r.status,
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
    # TODO: GET /readings (pagination with next_cursor, max 100 per request)
    raise NotImplementedError
