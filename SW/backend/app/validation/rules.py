import re

from decimal import Decimal

from app.core.response_codes import ResponseCode


# EMAIL

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

EMAIL_RULES = {
    "field_name": "Email",
    "codes": {
        "empty": ResponseCode.EMAIL_EMPTY,
        "too_short": ResponseCode.EMAIL_TOO_SHORT,
        "too_long": ResponseCode.EMAIL_TOO_LONG,
        "spaces": ResponseCode.EMAIL_CONTAINS_SPACES,
        "control": ResponseCode.EMAIL_CONTROL_CHARACTERS,
        "invalid": ResponseCode.EMAIL_INVALID_CHARACTERS,
    },
    "min_length": 5,
    "max_length": 254,
    "pattern": EMAIL_PATTERN,
    "allow_spaces": False,
    "strip": True,
    "normalize": "lower",
}


# USERNAME

USERNAME_PATTERN = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9_-]+$"
)

USERNAME_RULES = {
    "field_name": "Username",
    "codes": {
        "empty": ResponseCode.USERNAME_EMPTY,
        "too_short": ResponseCode.USERNAME_TOO_SHORT,
        "too_long": ResponseCode.USERNAME_TOO_LONG,
        "spaces": ResponseCode.USERNAME_CONTAINS_SPACES,
        "control": ResponseCode.USERNAME_CONTROL_CHARACTERS,
        "invalid": ResponseCode.USERNAME_INVALID_CHARACTERS,
    },
    "min_length": 3,
    "max_length": 30,
    "pattern": USERNAME_PATTERN,
    "allow_spaces": False,
    "strip": True,
}


# PASSWORD

PASSWORD_PATTERN = re.compile(
    r"^[^\s]+$"
)

PASSWORD_RULES = {
    "field_name": "Password",
    "codes": {
        "empty": ResponseCode.PASSWORD_EMPTY,
        "too_short": ResponseCode.PASSWORD_TOO_SHORT,
        "too_long": ResponseCode.PASSWORD_TOO_LONG,
        "spaces": ResponseCode.PASSWORD_CONTAINS_SPACES,
        "control": ResponseCode.PASSWORD_CONTROL_CHARACTERS,
        "invalid": ResponseCode.PASSWORD_INVALID_CHARACTERS,
    },
    "min_length": 8,
    "max_length": 64,
    "pattern": PASSWORD_PATTERN,
    "allow_spaces": False,
    "strip": False,
}


# READING
INT16_MIN, INT16_MAX = -32768, 32767

ACC_RULES = {
    "field_name": "Acceleration",
    "codes": {
        "invalid": ResponseCode.READING_ACC_INVALID,
        "too_small": ResponseCode.READING_ACC_TOO_SMALL,
        "too_large": ResponseCode.READING_ACC_TOO_LARGE,
    },
    "min_value": -4096,
    "max_value": 4096,
}

GYRO_RULES = {
    "field_name": "Gyroscope",
    "codes": {
        "invalid": ResponseCode.READING_GYRO_INVALID,
        "too_small": ResponseCode.READING_GYRO_TOO_SMALL,
        "too_large": ResponseCode.READING_GYRO_TOO_LARGE,
    },
    "min_value": INT16_MIN,
    "max_value": INT16_MAX,
}

STATUS_RULES = {
    "field_name": "Status",
    "codes": {
        "invalid": ResponseCode.READING_STATUS_INVALID,
        "too_small": ResponseCode.READING_STATUS_INVALID,
        "too_large": ResponseCode.READING_STATUS_INVALID,
    },
    "min_value": 0,
    "max_value": 2,
}

ANGLE_RULES = {
    "field_name": "Angle",
    "codes": {
        "invalid": ResponseCode.READING_ANGLE_INVALID,
        "too_small": ResponseCode.READING_ANGLE_OUT_OF_RANGE,
        "too_large": ResponseCode.READING_ANGLE_OUT_OF_RANGE,
    },
    "min_value": 0.0,
    "max_value": 180.0,
}

TIMESTAMP_RULES = {
    "field_name": "Timestamp",
    "codes": {
        "invalid": ResponseCode.READING_TIMESTAMP_INVALID,
        "too_small": ResponseCode.READING_TIMESTAMP_TOO_OLD,
        "too_large": ResponseCode.READING_TIMESTAMP_IN_FUTURE,
    },
    "min_value": 1577836800,  # 2020-01-01 UTC
    # max_value is computed at validation time: now + TIMESTAMP_FUTURE_TOLERANCE_S
}

TIMESTAMP_FUTURE_TOLERANCE_S = 300