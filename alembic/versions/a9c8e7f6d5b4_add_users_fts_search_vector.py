"""add users.search_vector for PostgreSQL full-text search (GIN index)

Revision ID: a9c8e7f6d5b4
Revises: e3b4c5d6a7f8
Create Date: 2026-04-04

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a9c8e7f6d5b4"
down_revision: Union[str, Sequence[str], None] = "e3b4c5d6a7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'english',
                coalesce(full_name, '') || ' ' || coalesce(email, '')
            )
        ) STORED;
        """
    )
    op.create_index(
        "ix_users_search_vector",
        "users",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_users_search_vector", table_name="users")
    op.drop_column("users", "search_vector")
