import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load SW/backend/.env (if it exists). It does not override variables already in the environment.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


'''
alembic revision --autogenerate -m "short description"
alembic upgrade head
Commit the model and the migration together.


`alembic current`: version applied in the database
`alembic history`: list of migrations
`alembic upgrade head`: apply all the pending ones
`alembic downgrade -1`: undo the last one
`alembic heads`: check whether there is more than one head (conflict)
'''