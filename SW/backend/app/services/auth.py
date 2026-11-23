from datetime import datetime, timedelta, UTC

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core import config
from app.core.security import hash_password
from app.core.response_codes import ResponseCode
from app.core.exceptions import (
    ConflictException,
    AuthenticationException,
)

from app.repositories import user as user_repository

from app.validation.validators import (
    validate_email,
    validate_username,
    validate_password,
)

from app.schemas.auth import (
    RegisterInput,
    LoginInput,
    RefreshInput
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def register_user(
    db: Session,
    user_data: RegisterInput,
):

    email = validate_email(user_data.email)
    username = validate_username(user_data.username)
    password = validate_password(user_data.password)

    if user_repository.get_by_email(db, email):
        raise ConflictException(
            code=ResponseCode.EMAIL_ALREADY_REGISTERED,
            message="Email already registered.",
        )

    user = user_repository.create(
        db=db,
        email=email,
        username=username,
        password_hash=hash_password(password),
    )

    return {"id": user.id}


def login_user(
    db: Session,
    credentials: LoginInput,
):

    email = credentials.email.strip().lower()
    password = credentials.password

    user = user_repository.get_by_email(
        db,
        email,
    )

    if user is None:
        raise AuthenticationException(
            code=ResponseCode.INVALID_CREDENTIALS,
            message="Invalid credentials.",
        )

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise AuthenticationException(
            code=ResponseCode.INVALID_CREDENTIALS,
            message="Invalid credentials.",
        )

    access_token = create_token(user.id, config.ACCESS_EXPIRE_MINUTES, "access")

    refresh_token = create_token(user.id, config.REFRESH_EXPIRE_MINUTES, "refresh")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def refresh_access_token(
        db: Session,
        data: RefreshInput
):
    try:
        payload = jwt.decode(data.refresh_token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise JWTError()
        user_id = payload["sub"]

    except (JWTError, KeyError):
        raise AuthenticationException(ResponseCode.INVALID_TOKEN, "Invalid token.")

    if user_repository.get_by_id(db, user_id) is None:
        raise AuthenticationException(ResponseCode.INVALID_TOKEN, "Invalid token.")

    access_token = create_token(user_id, config.ACCESS_EXPIRE_MINUTES, "access")

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_token(
    user_id: str,
    expiration_time: int,
    token_type: str = "access",
) -> str:

    expire = datetime.now(UTC) + timedelta(
        minutes=expiration_time,
    )

    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        config.JWT_SECRET,
        algorithm=config.JWT_ALGORITHM,
    )