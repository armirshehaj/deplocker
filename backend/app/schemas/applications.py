import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, NonNegativeInt

from app.utils.text.slug_generator import SluggableName


class AppStatus(Enum):
    CREATED = "created"
    DEPLOYING = "deploying"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"  # Running, but failing health checks
    STOPPED = "stopped"
    FAILED = "failed"
    DELETING = "deleting"


class ApplicationBase(BaseModel):
    name: SluggableName
    description: str
    git_url: str
    branch: str = "main"
    dockerfile_path: str = "./Dockerfile"
    port: NonNegativeInt = 8000
    env_vars: dict
    domain: str
    desired_replicas: int = 1


class ApplicationCreate(ApplicationBase):
    project_id: uuid.UUID


class ApplicationUpdate(BaseModel):
    name: SluggableName | None = None
    description: str | None = None
    git_url: str | None = None
    branch: str | None = None
    dockerfile_path: str | None = None
    port: int | None = None
    env_vars: dict | None = None
    domain: str | None = None
    desired_replicas: int | None = None


class ApplicationResponse(ApplicationCreate):
    id: uuid.UUID
    slug: str
    status: AppStatus
    created_at: datetime
    updated_at: datetime
    last_deployed_at: datetime | None = None
