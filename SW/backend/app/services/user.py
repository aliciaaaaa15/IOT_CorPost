from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.core.response_codes import ResponseCode
from app.core.security import hash_password

from app.repositories import user as user_repository

from app.validation.validators import (
    validate_username,
    validate_password,
)

from app.schemas.user import UserUpdateInput

from app.models.user import User


def get_me(current_user: User):
    # needed on app launch: premium status (updated externally) and paired device_id
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "premium": current_user.premium,
        "consent": current_user.consent,
        "device_id": current_user.device_id,
    }


def update_me(
    db: Session,
    current_user: User,
    data: UserUpdateInput,
):
    # at least one field must be sent
    if (
        data.username is None
        and data.password is None
        and data.consent is None
        and data.premium is None
    ):
        raise ValidationException(
            code=ResponseCode.NO_DATA_PROVIDED,
            message="No data provided.",
        )

    # validate everything first, so nothing is modified if any field is invalid
    if data.username is not None:
        username = validate_username(data.username)

    if data.password is not None:
        password_hash = hash_password(validate_password(data.password))

    # username is not unique: no duplicate check
    if data.username is not None:
        current_user.username = username

    if data.password is not None:
        current_user.password_hash = password_hash

    if data.consent is not None:
        current_user.consent = data.consent

    if data.premium is not None:
        current_user.premium = data.premium

    user_repository.update(db, current_user)


def delete_me(
    db: Session,
    current_user: User,
):
    # purges the account and all the data related (readings, reports)
    user_repository.delete(db, current_user)


def delete_me_data(
    db: Session,
    current_user: User,
):
    # purges readings, cached insights and reports (the account stays)
    user_repository.delete_data(db, c