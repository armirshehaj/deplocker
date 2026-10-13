"""free organization names

Revision ID: d54abd717fcb
Revises: 374176b6bef2
Create Date: 2026-10-07 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d54abd717fcb"
down_revision: str | Sequence[str] | None = "374176b6bef2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The slug keeps its unique index: it stays the organization's handle.
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if two organizations have since taken the same name.
    op.create_index(
        op.f("ix_organizations_name"), "organizations", ["name"], unique=True
    )
