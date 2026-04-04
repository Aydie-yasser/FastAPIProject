"""add organization and membership tables

Revision ID: e3b4c5d6a7f8
Revises: d4d135016689
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3b4c5d6a7f8"
down_revision: Union[str, Sequence[str], None] = "d4d135016689"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("org_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("org_id"),
    )
    op.create_table(
        "membership",
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.org_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_id", "user_id"),
        sa.CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_membership_role",
        ),
    )


def downgrade() -> None:
    op.drop_table("membership")
    op.drop_table("organization")
