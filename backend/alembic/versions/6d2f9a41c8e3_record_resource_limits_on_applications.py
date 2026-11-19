"""record resource limits on applications

Revision ID: 6d2f9a41c8e3
Revises: b4e817d2c05a
Create Date: 2026-11-19 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d2f9a41c8e3"
down_revision: str | Sequence[str] | None = "b4e817d2c05a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing applications take the platform's default limits; new ones get
    # them from the settings when created, so the columns keep no default
    op.add_column(
        "applications",
        sa.Column(
            "memory_limit_mb", sa.Integer(), nullable=False, server_default="512"
        ),
    )
    op.add_column(
        "applications",
        sa.Column("cpu_limit", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.alter_column("applications", "memory_limit_mb", server_default=None)
    op.alter_column("applications", "cpu_limit", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("applications", "cpu_limit")
    op.drop_column("applications", "memory_limit_mb")
