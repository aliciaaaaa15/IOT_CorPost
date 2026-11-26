from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.handlers import register_exception_handlers
from app.database import get_db
from app.routers import auth, readings, stats

VERSION = "0.1.0"

app = FastAPI(title="CorPost API", version=VERSION)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(readings.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    """The API is alive (it does not touch the database)."""
    return {"status": "ok", "version": VERSION}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """The API can talk to the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}
