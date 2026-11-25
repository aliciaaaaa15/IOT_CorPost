from decimal import Decimal
from datetime import datetime, time, date, timezone
import math

from app.core.exceptions import ValidationException

from app.core.response_codes import ResponseCode

from app.schemas.readings import BatchInput, HWCompletePayload

from app.validation.rules import (
    EMAIL_RULES,
    USERNAME_RULES,
    PASSWORD_RULES,
    ACC_RULES,
    GYRO_RULES,
    STATUS_RULES,
    ANGLE_RULES,
    TIMESTAMP_RULES,
    TIMESTAMP_FUTURE_TOLERANCE_S,
    DATETIME_RULES
)


# HELPERS

def _raise_validation_error(
    code: str,
    message: str,
):

    raise ValidationException(
        code=code,
        message=message,
    )

def _contains_control_characters(value: str) -> bool:
    """
    Reject Unicode control characters.

    Includes:
        - ASCII C0 (0-31)
        - DEL (127)
        - Unicode C1 (128-159)
    """
    return any(
        ord(ch) < 32 or 127 <= ord(ch) <= 159
        for ch in value
    )


# GENERIC VALIDATORS

def _validate_text(
    value: str,
    field_name: str,
    codes: dict,
    min_length: int,
    max_length: int,
    pattern=None,
    allow_spaces: bool = False,
    strip: bool = True,
    normalize: str | None = None,
) -> str:

    if value is None:
        value = ""

    if strip:
        value = value.strip()

    if normalize == "lower":
        value = value.lower()

    elif normalize == "upper":
        value = value.upper()

    if not value:
        _raise_validation_error(
            codes["empty"],
            f"{field_name} cannot be empty.",
        )

    if len(value) < min_length:
        _raise_validation_error(
            codes["too_short"],
            f"{field_name} must contain at least {min_length} characters.",
        )

    if len(value) > max_length:
        _raise_validation_error(
            codes["too_long"],
            f"{field_name} cannot exceed {max_length} characters.",
        )

    if _contains_control_characters(value):
        _raise_validation_error(
            codes["control"],
            f"{field_name} contains invalid control characters.",
        )

    if not allow_spaces and any(ch.isspace() for ch in value):
        _raise_validation_error(
            codes["spaces"],
            f"{field_name} cannot contain spaces.",
        )

    if pattern is not None and not pattern.fullmatch(value):
        _raise_validation_error(
            codes["invalid"],
            f"{field_name} contains invalid characters.",
        )

    return value


def _validate_integer(
    value,
    *,
    field_name: str,
    codes: dict,
    min_value: int,
    max_value: int,
) -> int:

    if not isinstance(value, int):
        _raise_validation_error(
            codes["invalid"],
            f"{field_name} must be an integer.",
        )

    if value < min_value:
        _raise_validation_error(
            codes["too_small"],
            f"{field_name} must be at least {min_value}.",
        )

    if value > max_value:
        _raise_validation_error(
            codes["too_large"],
            f"{field_name} cannot exceed {max_value}.",
        )

    return value

def _validate_float(
    value: float,
    *,
    field_name: str,
    codes: dict,
    min_value: float,
    max_value: float,
) -> float:

    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _raise_validation_error(
            codes["invalid"],
            f"{field_name} is invalid",
        )

    if value < min_value:
        _raise_validation_error(
            codes["too_small"],
            f"{field_name} must be at least {min_value}.",
        )

    if value > max_value:
        _raise_validation_error(
            codes["too_large"],
            f"{field_name} cannot exceed {max_value}.",
        )

    return value


def _validate_datetime(
    value: datetime | None,
    *,
    field_name: str,
    codes: dict,
    min_value: datetime,
    max_value: datetime | None = None,
) -> datetime:
    """Validate a datetime and return it normalized to UTC.

    A naive datetime is assumed to be UTC; an aware one is converted to UTC.
    min_value / max_value must be aware datetimes; max_value is optional.
    """

    if not isinstance(value, datetime):
        _raise_validation_error(
            codes["invalid"],
            f"{field_name} must be a datetime.",
        )

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    if value < min_value:
        _raise_validation_error(
            codes["too_small"],
            f"{field_name} cannot be before {min_value.isoformat()}.",
        )

    if max_value is not None and value > max_value:
        _raise_validation_error(
            codes["too_large"],
            f"{field_name} cannot be after {max_value.isoformat()}.",
        )

    return value


def _validate_reading(reading: HWCompletePayload) -> str | None:
    """Return None if the reading is valid, otherwise the ResponseCode of the first failure."""
    max_timestamp = int(datetime.now(timezone.utc).timestamp()) + TIMESTAMP_FUTURE_TOLERANCE_S

    try:
        _validate_integer(reading.timestamp, max_value=max_timestamp, **TIMESTAMP_RULES)
        _validate_integer(reading.acc_x, **ACC_RULES)
        _validate_integer(reading.acc_y, **ACC_RULES)
        _validate_integer(reading.acc_z, **ACC_RULES)
        _validate_integer(reading.gyro_x, **GYRO_RULES)
        _validate_integer(reading.gyro_y, **GYRO_RULES)
        _validate_integer(reading.gyro_z, **GYRO_RULES)
        _validate_float(reading.angle_deg, **ANGLE_RULES)
        _validate_integer(reading.status, **STATUS_RULES)
    except ValidationException as exc:
        return exc.code

    return None




# PUBLIC TEXT VALIDATORS

def validate_email(email: str) -> str:
    return _validate_text(
        value=email,
        **EMAIL_RULES,
    )


def validate_username(username: str) -> str:
    return _validate_text(
        value=username,
        **USERNAME_RULES,
    )


def validate_password(password: str) -> str:
    return _validate_text(
        value=password,
        **PASSWORD_RULES,
    )


def validate_batch(batch: BatchInput) -> tuple[list[HWCompletePayload], list[tuple[int, str]]]:
    """Split a batch into valid readings and rejected ones as (timestamp, code)."""
    valid: list[HWCompletePayload] = []
    rejected: list[tuple[int, str]] = []

    for reading in batch.readings:
        code = _validate_reading(reading)
        if code is None:
            valid.append(reading)
        else:
            rejected.append((reading.timestamp, code))

    return valid, rejected


def validate_datetime_range(date_from: datetime, date_to: datetime) -> tuple[datetime, datetime]:

    date_from_valid = _validate_datetime(date_from, **DATETIME_RULES)
    date_to_valid = _validate_datetime(date_to, **DATETIME_RULES)

    if date_from_valid > date_to_valid:
        _raise_validation_error(
            DATETIME_RULES["codes"]["range"],
            f"{date_from_valid} must be a datetime before {date_to_valid}.",
        ) 

    return date_from_valid, date_to_valid