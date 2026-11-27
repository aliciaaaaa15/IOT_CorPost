from pydantic import BaseModel, EmailStr
from typing import Optional

# --- INPUT SCHEMAS (Request Bodies) ---

# PATCH /me
class UserUpdateInput(BaseModel):
    """Schema for updating the user data. All fields optional (at least one is required)."""
    username: str | None = None
    password: str | None = None
    # StrictBool: only real JSON booleans are accepted ("yes", 1... are rejected)
    consent: StrictBool | None = None
    premium: StrictBool | None = None


# --- OUTPUT SCHEMAS (Response Bodies) ---

# GET /me
class UserDataResponse(BaseModel):
    """Schema for public/safe user data response (never exposes password_hash)."""
    user_id: str
    username: str
    email: str
    premium: bool
    consent: bool
    device_id: str | None = None
