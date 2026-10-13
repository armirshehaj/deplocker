import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.schemas.projects import ProjectStatus


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=func.now(), onupdate=func.now()
    )

    organization: Mapped["OrganizationModel"] = relationship(  # type: ignore[name-defined]
        back_populates="projects"
    )
    applications: Mapped[list["ApplicationModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="project", cascade="all, delete-orphan"
    )

    # Names and slugs are unique within an organization, so tenants don't
    # compete for them.
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_projects_organization_id_name"
        ),
        UniqueConstraint(
            "organization_id", "slug", name="uq_projects_organization_id_slug"
        ),
    )
