import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.schemas.organizations import OrganizationRole


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # The name is a display label organizations may share; the slug is the
    # organization's handle, unique across all of them.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["UserModel"]] = relationship(  # type: ignore[name-defined]
        secondary="organization_members", back_populates="organizations", viewonly=True
    )
    projects: Mapped[list["ProjectModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Organization({self.id}, {self.name})"


# Joins users and organizations, many to many, with each member's role
class OrganizationMembersModel(Base):
    __tablename__ = "organization_members"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )

    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole), default=OrganizationRole.MEMBER
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
