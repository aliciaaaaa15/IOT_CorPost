from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import get_current_user

from app.schemas.readings import (
    BatchInput,
    ReadingsLoadInput,
    BatchResponse,
    ReadingsLoadResponse
)

from app.services import readings as readings_service


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
    db: Session = Depends(get_current_user),
):
    return readings_service.store_batch(db, batch)


@router.get(
    response_model=ReadingsLoadResponse,
)
def loaf_readings(
    data: ReadingsLoadInput,
    db: Session = Depends(get_current_user),
):
    return readings_service.load_readings(db, data)

