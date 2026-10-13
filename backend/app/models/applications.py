import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.schemas.applications import AppStatus


class ApplicationModel(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    dockerfile_path: Mapped[str] = mapped_column(
        String(255), nullable=False, default="./Dockerfile"
    )

    port: Mapped[int] = mapped_column(Integer, nullable=False, default=8000)
    env_vars: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Unique across all applications, unlike name and slug: routing resolves a
    # request to its application by domain alone.
    domain: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    desired_replicas: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[AppStatus] = mapped_column(
        Enum(AppStatus), nullable=False, default=AppStatus.CREATED
    )

    # Docker container IDs are 64 hex characters
    container_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=func.now(), onupdate=func.now()
    )
    last_deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["ProjectModel"] = relationship(back_populates="applications")  # type: ignore[name-defined]
    deployments: Mapped[list["DeploymentModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="application", cascade="all, delete-orphan"
    )

    # Names and slugs are unique within a project, so tenants don't compete for
    # them.
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_applications_project_id_name"),
        UniqueConstraint("project_id", "slug", name="uq_applications_project_id_slug"),
    )
