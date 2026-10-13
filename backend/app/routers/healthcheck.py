from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import redis
from app.core.database import get_db_session

router = APIRouter()


@router.get("/health", summary="Platform operational status information endpoint")
async def healthcheck(
    db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    checks = {}
    overall_ok = True

    try:
        await db_session.execute(text("SELECT 1"))
        checks["database"] = "ok"

    except Exception as e:
        checks["database"] = f"Error: {e!s}"
        overall_ok = False

    try:
        await redis.client.ping()  # type: ignore[misc]
        checks["cache"] = "ok"

    except Exception as e:
        checks["cache"] = f"Error: {e!s}"
        overall_ok = False

    status_code = (
        status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if overall_ok else "degraded", "checks": checks},
    )
