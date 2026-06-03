"""add_admin_and_profile_fields

Revision ID: a7c9f1e2d4b6
Revises: 7f8f14371773
Create Date: 2026-05-31 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c9f1e2d4b6"
down_revision: Union[str, Sequence[str], None] = "7f8f14371773"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("group_number", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_users_group_number"), "users", ["group_number"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_group_number"), table_name="users")
    op.drop_column("users", "group_number")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "is_admin")
