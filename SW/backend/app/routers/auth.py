from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.auth import (
    RegisterInput,
    LoginInput,
    RegisterResponse,
    LoginResponse,
    RefreshInput,
    RefreshResponse
)

from app.services import auth as auth_service


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
)
def register(
    user: RegisterInput,
    db: Session = Depends(get_db),
):
    return auth_service.register_user(db, user)


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginInput,
    db: Session = Depends(get_db),
):
    return auth_service.login_user(db, credentials)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    refresh_token: RefreshInput,
    db: Session = Depends(get_db)
):
    return auth_service.refresh_access_token(db, refresh_token)
