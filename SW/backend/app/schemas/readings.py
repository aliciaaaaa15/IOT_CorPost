from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

# Max readings per batch.
MAX_BATCH_READINGS = 20


class HWSimplifiedPayload(BaseModel):
    """Schema to represent simplified hw data payload request"""
    timestamp: datetime 
    angle_deg: float
    status: int

class HWCompletePayload(BaseModel):
    """Schema to represent complete hw data payload request"""
    model_config = ConfigDict(strict=True)

    timestamp: int
    acc_x: int
    acc_y: int
    acc_z: int
    gyro_x: int
    gyro_y: int
    gyro_z: int
    angle_deg: float
    status: int


# --- INPUT SCHEMAS ---
class BatchInput(BaseModel):
    """Schema for hw data batch"""
    readings: list[HWCompletePayload] = Field(min_length=1, max_length=MAX_BATCH_READINGS)

class ReadingsLoadInput(BaseModel):
    """Schema for hw data load request"""
    date_from: datetime
    date_to: datetime


# --- OUTPUT SCHEMAS ---
class BatchResponse(BaseModel):
    """Schema for hw data saved and duplicated from batch"""
    inserted: int
    duplicated: int


class ReadingsLoadResponse(BaseModel):
    """Schema for user hw data load"""
    readings: list[HWSimplifiedPayload]
    next_cursor: datetime | None = None
