import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.deployments import DeploymentModel
from app.schemas.deployments import DeploymentCreate, DeploymentResponse
from app.schemas.organizations import OrganizationRole
from app.services.deployment import DeploymentService
from app.utils.auth.shared import get_current_session
from app.utils.organizations.membership import get_member_deployment
from app.utils.organizations.roles import require_role

router = APIRouter()


@router.post(
    "",
    status_code=201,
    summary="Application creation endpoint",
    response_model=DeploymentResponse,
)
async def create_deployment(
    payload: DeploymentCreate,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> DeploymentModel:
    service = DeploymentService(db_session)

    new_deployment = await service.create_deployment(
        auth_session["user_id"], payload.application_id
    )
    return new_deployment


@router.get(
    "/{id}", summary="Get deployment data by ID", response_model=DeploymentResponse
)
async def get_deployment_id(
    id: uuid.UUID,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> DeploymentModel:
    service = DeploymentService(db_session)
    deployment = await service.get_deployment(auth_session["user_id"], id)

    return deployment


@router.get("/", summary="List deployments", response_model=list[DeploymentResponse])
async def list_deployments(
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> Sequence[DeploymentModel]:
    service = DeploymentService(db_session)
    all_deployments = await service.get_all_deployments(auth_session["user_id"])
    return all_deployments


@router.delete("/{id}", status_code=204, summary="Clear up a specific deployment")
async def delete_deployment(
    deployment: DeploymentModel = Depends(
        require_role(get_member_deployment, OrganizationRole.OWNER)
    ),
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    service = DeploymentService(db_session)
    await service.delete_deployment(deployment)
