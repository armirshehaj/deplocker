"""add commit_subject to deployments

Revision ID: b4e817d2c05a
Revises: a71c3e5f9b28
Create Date: 2026-10-12 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e817d2c05a"
down_revision: str | Sequence[str] | None = "a71c3e5f9b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("deployments", sa.Column("commit_subject", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deployments", "commit_subject")
