from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

app = FastAPI(title="CorPost API")


@app.get("/health")
def health():
    """The API is alive (it does not touch the database)."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """The API can talk to the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}
