from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class GroupByCriteria(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

class GroupStats(BaseModel):
    start: datetime
    total_readings: int
    valid_readings: int
    good_readings: int
    bad_readings: int
    invalid_readings: int
    good_pct: float
    avg_angle_deg: float | None = None
    max_angle_deg: float | None = None


# --- INPUT SCHEMAS ---
# GET /stats
class StatsInput(BaseModel):
    date_from: datetime
    date_to: datetime
    group_by: GroupByCriteria


# --- RESPONSE SCHEMA ---
# GET / stats
class StatsResponse(BaseModel):
    group_by: GroupByCriteria
    series: list[GroupStats]