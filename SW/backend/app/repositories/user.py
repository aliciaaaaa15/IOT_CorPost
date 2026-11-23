from sqlalchemy.orm import Session

from app.models.user import User


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