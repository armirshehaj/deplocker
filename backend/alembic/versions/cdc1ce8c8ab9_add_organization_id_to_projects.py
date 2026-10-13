"""add organization_id to projects

Revision ID: cdc1ce8c8ab9
Revises: 3f8c21ad74be
Create Date: 2026-09-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cdc1ce8c8ab9"
down_revision: str | Sequence[str] | None = "3f8c21ad74be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Added nullable first so existing rows can be backfilled before the
    # constraint applies.
    op.add_column("projects", sa.Column("organization_id", sa.UUID(), nullable=True))

    # Projects never recorded who created them, so there is no owner to derive.
    # They go to the oldest organization: on a single-user install that is the
    # user's own default organization.
    op.execute(
        """
        UPDATE projects
        SET organization_id = (
            SELECT id FROM organizations ORDER BY created_at, id LIMIT 1
        )
        WHERE organization_id IS NULL
        """
    )

    orphans = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM projects WHERE organization_id IS NULL")
    )
    if orphans:
        raise RuntimeError(
            f"{orphans} project(s) exist but there is no organization to assign "
            "them to. Register a user (which creates a default organization), "
            "or delete these projects, then run the migration again."
        )

    op.alter_column("projects", "organization_id", nullable=False)
    op.create_index(
        op.f("ix_projects_organization_id"),
        "projects",
        ["organization_id"],
        unique=False,
    )
    op.create_foreign_key(
        "projects_organization_id_fkey",
        "projects",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("projects_organization_id_fkey", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_organization_id"), table_name="projects")
    op.drop_column("projects", "organization_id")
