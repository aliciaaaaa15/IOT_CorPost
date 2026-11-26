from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.core.exceptions import ConflictException

from app.validation.validators import validate_datetime_range

from app.repositories import reading as readings_repository


from app.schemas.stats import StatsInput
from app.models.user import User

def calculate_user_stats(
    stats_criteria: StatsInput,
    db: Session,
    current_user: User
):
    # validate user has a device associated
    if current_user.device_id is None:
        raise ConflictException(
            ResponseCode.DEVICE_NOT_LINKED,
            "User has no device linked.",
        )

    # validate data range
    date_from, date_to = validate_datetime_range(stats_criteria.date_from, stats_criteria.date_to)

    # aggregate readings
    rows = readings_repository.aggregate_readings(
        db, 
        current_user.device_id, 
        date_from, 
        date_to,
        stats_criteria.group_by.value
    )

    return {
        "group_by": stats_criteria.group_by,
        "series": [
            {
                **r._asdict(),
                "good_pct": r.good_readings / r.valid_readings if r.valid_readings else 0.0,
            }
            for r in rows
        ],
    }

