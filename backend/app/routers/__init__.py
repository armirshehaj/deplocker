from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.deployments import router as deployments_router
from app.routers.healthcheck import router as healtcheck_router
from app.routers.organizations import router as orgs_router
from app.routers.projects import router as projects_router

__all__ = [
    "applications_router",
    "auth_router",
    "deployments_router",
    "healtcheck_router",
    "orgs_router",
    "projects_router",
]
