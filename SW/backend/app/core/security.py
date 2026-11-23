from fastapi import Depends

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import user as user_repository
from app.core import config
from app.core.exceptions import AuthenticationException
from app.core.response_codes import ResponseCode

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False: if the header is missing, we raise our own AuthenticationException
# (so the error uses our format) instead of FastAPI's {"detail": ...}.
bearer_scheme = HTTPBearer(auto_error=False)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:

    return pwd_context.hash(password)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise AuthenticationException(
            code=ResponseCode.INVALID_TOKEN,
            message="Missing token.",
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
        )

        if payload.get("type") != "access":
            raise JWTError()

        user_id = payload["sub"]

    except (JWTError, KeyError, ValueError):
        raise AuthenticationException(
            code=ResponseCode.INVALID_TOKEN,
            message="Invalid token.",
        )

    user = user_repository.get_by_id(db, user_id)

    if user is None:
        raise AuthenticationException(
            code=ResponseCode.INVALID_TOKEN,
            message="Invalid token.",
        )

    return user