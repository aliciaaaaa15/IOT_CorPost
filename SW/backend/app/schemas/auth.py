from pydantic import BaseModel


# --- INPUT SCHEMAS (Request Bodies) ---

# POST /auth/register
class RegisterInput(BaseModel):
    """Schema for user registration request."""
    email: str
    username: str
    password: str


# POST /auth/login
class LoginInput(BaseModel):
    """Schema for user login request."""
    email: str
    password: str

# POST /auth/refresh
class RefreshInput(BaseModel):
    """Schema to refresh access token"""
    refresh_token: str


# --- OUTPUT SCHEMAS (Response Bodies) ---

# POST /auth/register
class RegisterResponse(BaseModel):
    """Schema for public/safe user id response."""
    id: str


# POST /auth/login
class LoginResponse(BaseModel):
    """Schema for successful login response containing the JWT token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# POST /auth/refresh
class RefreshResponse(BaseModel):
    """Schema to refresh access token"""
    access_token: str
    token_type: str = "bearer"
