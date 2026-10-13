import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployments import DeploymentModel
from app.utils.organizations.membership import (
    get_member_application,
    get_member_deployment,
    select_member_deployments,
)


class DeploymentService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def create_deployment(
        self, user_id: int, application_id: uuid.UUID
    ) -> DeploymentModel:
        await get_member_application(self.db_session, user_id, application_id)

        new_deployment = DeploymentModel(application_id=application_id)
        self.db_session.add(new_deployment)
        await self.db_session.commit()
        await self.db_session.refresh(new_deployment)
        return new_deployment

    async def get_deployment(self, user_id: int, id: uuid.UUID) -> DeploymentModel:
        return await get_member_deployment(self.db_session, user_id, id)

    async def get_all_deployments(self, user_id: int) -> Sequence[DeploymentModel]:
        result = await self.db_session.execute(select_member_deployments(user_id))
        return result.scalars().all()

    async def delete_deployment(self, deployment: DeploymentModel) -> None:
        await self.db_session.delete(deployment)
        await self.db_session.commit()
