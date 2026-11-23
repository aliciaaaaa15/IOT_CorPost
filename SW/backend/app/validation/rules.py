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

