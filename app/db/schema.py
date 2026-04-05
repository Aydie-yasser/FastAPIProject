"""Create database tables from SQLAlchemy models (no separate migration CLI)."""

from app.db.base import Base
from app.db.session import engine

# Register all mapped tables on Base.metadata
from app.models import audit_log  # noqa: F401
from app.models import item  # noqa: F401
from app.models import membership  # noqa: F401
from app.models import organization  # noqa: F401
from app.models import user  # noqa: F401


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
