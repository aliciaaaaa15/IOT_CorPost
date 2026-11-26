from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user

from app.schemas.user import (
    UserUpdateInput,
    UserDataResponse,
)

from app.services import user as user_service

from app.models.user import User


router = APIRouter(
    prefix="/me",
    tags=["User"],
)


@router.patch(
    "",
    status_code=status.HTTP_200_OK,
)
def update_me(
    data: UserUpdateInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return user_service.update_me(db, current_user, data)


@router.get(
    "",
    response_model=UserDataResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return user_service.get_me(current_user)


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
)
def delete_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return user_service.delete_me(db, current_user)


@router.delete(
    "/data",
    status_code=status.HTTP_200_OK,
)
def delete_me_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return user_service.delete_me_data(db, current_user)
