import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from app.utils.text.slug_generator import SluggableName


class ProjectStatus(Enum):
    CREATED = "created"
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"


class ProjectBase(BaseModel):
    id: uuid.UUID
    slug: str
    created_at: datetime
    updated_at: datetime
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectFields(BaseModel):
    name: SluggableName
    description: str


class ProjectCreate(ProjectFields):
    organization_id: uuid.UUID


class ProjectUpdate(BaseModel):
    name: SluggableName | None = None
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectResponse(ProjectBase, ProjectCreate):
    pass
