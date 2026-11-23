from decimal import Decimal
from datetime import datetime, time, date
from typing import Iterable
from fastapi import UploadFile


from app.core.exceptions import ValidationException


from app.core.response_codes import ResponseCode

from app.validation.rules import (
    EMAIL_RULES,
    USERNAME_RULES,
    PASSWORD_RULES,
)


# HELPERS

def raise_validation_error(
    code: str,
    message: str,
):

    raise ValidationException(
        code=code,
        message=message,
    )

def contains_control_characters(value: str) -> bool:
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

def validate_text(
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
        raise_validation_error(
            codes["empty"],
            f"{field_name} cannot be empty.",
        )

    if len(value) < min_length:
        raise_validation_error(
            codes["too_short"],
            f"{field_name} must contain at least {min_length} characters.",
        )

    if len(value) > max_length:
        raise_validation_error(
            codes["too_long"],
            f"{field_name} cannot exceed {max_length} characters.",
        )

    if contains_control_characters(value):
        raise_validation_error(
            codes["control"],
            f"{field_name} contains invalid control characters.",
        )

    if not allow_spaces and any(ch.isspace() for ch in value):
        raise_validation_error(
            codes["spaces"],
            f"{field_name} cannot contain spaces.",
        )

    if pattern is not None and not pattern.fullmatch(value):
        raise_validation_error(
            codes["invalid"],
            f"{field_name} contains invalid characters.",
        )

    return value


def validate_decimal(
    value,
    *,
    field_name: str,
    codes: dict,
    min_value: Decimal,
    max_value: Decimal,
    decimal_places: int,
) -> Decimal:

    try:
        value = Decimal(value)
    except Exception:
        raise_validation_error(
            codes["invalid"],
            f"{field_name} is invalid.",
        )

    if value < min_value:
        raise_validation_error(
            codes["too_small"],
            f"{field_name} must be at least {min_value}.",
        )

    if value > max_value:
        raise_validation_error(
            codes["too_large"],
            f"{field_name} cannot exceed {max_value}.",
        )

    if abs(value.as_tuple().exponent) > decimal_places:
        raise_validation_error(
            codes["decimals"],
            f"{field_name} cannot have more than {decimal_places} decimal places.",
        )

    return value


def validate_integer(
    value,
    *,
    field_name: str,
    codes: dict,
    min_value: int,
    max_value: int,
) -> int:

    if not isinstance(value, int):
        raise_validation_error(
            codes["invalid"],
            f"{field_name} must be an integer.",
        )

    if value < min_value:
        raise_validation_error(
            codes["too_small"],
            f"{field_name} must be at least {min_value}.",
        )

    if value > max_value:
        raise_validation_error(
            codes["too_large"],
            f"{field_name} cannot exceed {max_value}.",
        )

    return value


def validate_time(
    value: str | None,
    *,
    field_name: str,
    codes: dict,
    optional: bool = False,
) -> time | None:

    if value is None:

        if optional:
            return None

        raise_validation_error(
            codes["invalid"],
            f"{field_name} is required.",
        )

    try:
        return datetime.strptime(value, "%H:%M").time()

    except ValueError:

        raise_validation_error(
            codes["invalid"],
            f"{field_name} must have format HH:MM.",
        )


# PUBLIC TEXT VALIDATORS

def validate_email(email: str) -> str:
    return validate_text(
        value=email,
        **EMAIL_RULES,
    )


def validate_username(username: str) -> str:
    return validate_text(
        value=username,
        **USERNAME_RULES,
    )


def validate_password(password: str) -> str:
    return validate_text(
        value=password,
        **PASSWORD_RULES,
    )


