"""scope project and application names to their parent

Revision ID: 374176b6bef2
Revises: cdc1ce8c8ab9
Create Date: 2026-10-07 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "374176b6bef2"
down_revision: str | Sequence[str] | None = "cdc1ce8c8ab9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Global uniqueness is a stricter rule than the scoped one, so every
    # existing row already satisfies the new constraints.
    op.drop_index(op.f("ix_projects_name"), table_name="projects")
    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.create_unique_constraint(
        "uq_projects_organization_id_name", "projects", ["organization_id", "name"]
    )
    op.create_unique_constraint(
        "uq_projects_organization_id_slug", "projects", ["organization_id", "slug"]
    )

    op.drop_index(op.f("ix_applications_name"), table_name="applications")
    op.drop_index(op.f("ix_applications_slug"), table_name="applications")
    op.create_unique_constraint(
        "uq_applications_project_id_name", "applications", ["project_id", "name"]
    )
    op.create_unique_constraint(
        "uq_applications_project_id_slug", "applications", ["project_id", "slug"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if two organizations (or two projects) have since taken the same
    # name: the global indexes can't be restored over those duplicates.
    op.drop_constraint(
        "uq_applications_project_id_slug", "applications", type_="unique"
    )
    op.drop_constraint(
        "uq_applications_project_id_name", "applications", type_="unique"
    )
    op.create_index(op.f("ix_applications_slug"), "applications", ["slug"], unique=True)
    op.create_index(op.f("ix_applications_name"), "applications", ["name"], unique=True)

    op.drop_constraint("uq_projects_organization_id_slug", "projects", type_="unique")
    op.drop_constraint("uq_projects_organization_id_name", "projects", type_="unique")
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=True)
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=True)
