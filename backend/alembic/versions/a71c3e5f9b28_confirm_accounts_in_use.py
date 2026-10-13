"""confirm accounts in use

Revision ID: a71c3e5f9b28
Revises: d54abd717fcb
Create Date: 2026-10-12 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a71c3e5f9b28"
down_revision: str | Sequence[str] | None = "d54abd717fcb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Confirms the unconfirmed accounts holding more than an empty default
    # organization: only a Google or GitHub login reaches one, and releasing it
    # would delete that work.
    op.execute(
        """
        UPDATE users SET is_active = true
        WHERE is_active = false
          AND (
            EXISTS (
              SELECT 1 FROM organizations
              JOIN projects ON projects.organization_id = organizations.id
              WHERE organizations.owner_id = users.id
            )
            OR (SELECT count(*) FROM organizations WHERE owner_id = users.id) > 1
          )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The accounts it confirmed are not recorded, so they stay confirmed.
    pass
