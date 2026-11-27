from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from app.models.reading import Reading
from app.models.user import User
from app.models.weekly_report import WeeklyReport

def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return ""


def create(
    db: Session,
    email: str,
    username: str,
    password_hash: str
) -> User:

    return ""


def update(db: Session, user: User) -> User:
    db.commit()
    db.refresh(user)
    return user


def delete(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()

def _purge_data(db: Session, user: User) -> None:
    """Delete readings (linked by device_id, there is no FK) and reports. No commit."""
    if user.device_id is not None:
        db.execute(sa_delete(Reading).where(Reading.device_id == user.device_id))
    db.execute(sa_delete(WeeklyReport).where(WeeklyReport.user_id == user.id))


def delete_data(db: Session, user: User) -> None:
    """Purge the user's readings and reports. The account stays."""
    _purge_data(db, user)
    db.commit()
