import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyRegistered(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def register_user(db: Session, body: UserCreate) -> User:
    email = str(body.email).lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise EmailAlreadyRegistered
    user = User(
        full_name=body.full_name,
        email=email,
        password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
