import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import settings
from app.core.cache import redis
from app.core.migrations import ensure_schema_is_current
from app.logging_conf.setup import setup_logging
from app.middlewares.logging_handler import LoggingMiddleware
from app.routers import (
    applications_router,
    auth_router,
    deployments_router,
    healtcheck_router,
    orgs_router,
    projects_router,
)

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from .core.database import async_engine

    logger.info("Application starting up...")

    await ensure_schema_is_current(async_engine)

    yield

    await async_engine.dispose()
    await redis.client.aclose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.DEV_FRONTEND_URL, settings.PROD_FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(projects_router, prefix="/projects", tags=["Projects router"])
app.include_router(
    applications_router, prefix="/applications", tags=["Applications router"]
)
app.include_router(
    deployments_router, prefix="/deployments", tags=["Deployments router"]
)
app.include_router(auth_router, prefix="/auth", tags=["Authentication router"])
app.include_router(orgs_router, prefix="/orgs", tags=["Organizations router"])
app.include_router(healtcheck_router, tags=["Healthcheck endpoint router"])
