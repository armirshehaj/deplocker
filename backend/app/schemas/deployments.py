import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DeploymentStatus(StrEnum):
    PENDING = "pending"

    # Pipeline steps, in order
    CLONING = "cloning"
    BUILDING = "building"
    PUSHING = "pushing"  # To an image registry; optional
    DEPLOYING = "deploying"  # Starting the container
    HEALTH_CHECKING = "health_checking"

    # Terminal states
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"  # By the user


class DeploymentBase(BaseModel):
    id: uuid.UUID
    status: DeploymentStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    commit_hash: str | None = None


class DeploymentCreate(BaseModel):
    application_id: uuid.UUID


class DeploymentResponse(DeploymentBase, DeploymentCreate):
    pass
