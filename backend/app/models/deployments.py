import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.schemas.deployments import DeploymentStatus


class DeploymentModel(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id"), index=True
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus), nullable=False, default="pending"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=True)

    # The log file, on local disk or in cloud storage such as S3 or GCS
    log_uri: Mapped[str] = mapped_column(String(255), nullable=True)
    log_size: Mapped[int] = mapped_column(nullable=True)  # In bytes

    application: Mapped["ApplicationModel"] = relationship(back_populates="deployments")  # type: ignore[name-defined]

    # Serves an application's deployments, most recent first
    __table_args__ = (
        Index("ix_deployments_app_started", "application_id", "started_at"),
    )
