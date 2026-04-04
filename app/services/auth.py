from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.schemas import UserCreate


class EmailAlreadyRegistered(Exception):
    pass


def hash_password(password: str) -> str:
    # convert string to bytes > hash > convert back to string
    # using gensalt so two users with the same password get different hashes
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    # convert string to bytes > check if hash matches > return bool
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("ascii"),
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    # normalize email to lowercase
    normalized = email.lower()
    user = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if user is None or not verify_password(password, user.password):
        return None
    return user


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    # expire is set for 60 mins
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


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
