from pydantic import BaseModel, EmailStr
from typing import Optional


# --- INPUT SCHEMAS (Request Bodies) ---

# PUT /users/me
class UserUpdateInput(BaseModel):
    """Schema for updating user profile. All fields optional."""



# --- OUTPUT SCHEMAS (Response Bodies) ---

# GET /users/me
# PUT /users/me
class UserDataResponse(BaseModel):
    """Schema for public/safe user data response."""
