import os
from pathlib import Path

from dotenv import load_dotenv

# Load environmental variables
load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # SW/backend/.env


# Database
DATABASE_URL = os.environ["DATABASE_URL"]

# JWT
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", 15))
REFRESH_EXPIRE_MINUTES = int(os.getenv("JWT_REFRESH_EXPIRE_MINUTES", 43200))