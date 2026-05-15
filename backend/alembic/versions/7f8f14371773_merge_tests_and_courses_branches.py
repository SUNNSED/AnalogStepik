"""merge tests and courses branches

Revision ID: 7f8f14371773
Revises: b9b2f972d9d3, ccc797910a10
Create Date: 2026-05-15 14:12:51.662466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f8f14371773'
down_revision: Union[str, Sequence[str], None] = ('b9b2f972d9d3', 'ccc797910a10')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
