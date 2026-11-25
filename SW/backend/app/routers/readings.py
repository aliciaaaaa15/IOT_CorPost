from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user

from app.schemas.readings import (
    BatchInput,
    ReadingsLoadInput,
    BatchResponse,
    ReadingsLoadResponse
)

from app.services import readings as readings_service

from app.models.user import User


router = APIRouter(
    prefix="/readings",
    tags=["Readings"],
)


@router.post(
    "/batch",
    response_model=BatchResponse,
)
def store_batch(
    batch: BatchInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return readings_service.store_batch(batch, db, current_user)


@router.get(
    "",
    response_model=ReadingsLoadResponse,
)
def load_readings(
    data: ReadingsLoadInput = Depends(),  # query params: date_from, date_to
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return readings_service.load_readings(db, current_user, data)
