from typing import Any

from sqlalchemy import Computed, String
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    # PostgreSQL: stored tsvector for full-text search; GIN index in migration.
    # tsvector is a PostgreSQL data type that stores a full-text search index.
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(full_name, '') || ' ' || coalesce(email, ''))",
            persisted=True,
        ),
    )
