import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MembershipRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class Membership(Base):
    __tablename__ = "membership"

    org_id: Mapped[int] = mapped_column(
        ForeignKey("organization.org_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
