from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user


from app.services import stats as stats_service
from app.schemas.stats import StatsInput, StatsResponse
from app.models.user import User

router = APIRouter(
    prefix="/stats",
    tags=["Stats"],
)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StatsResponse,
)
def calculate_stats(
    stats_criteria: StatsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return stats_service.calculate_user_stats(stats_criteria, db, current_user)