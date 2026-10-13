from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core import redis
from app.core.conf import settings
from app.utils.auth.shared import get_current_session

from . import router


@router.get("/session/check")
async def validate_session(
    session: dict = Depends(get_current_session),
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=session,
    )


@router.post("/logout", summary="Logout user and invalidate session")
async def logout_user(request: Request) -> JSONResponse:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session found! Logout failed.",
        )

    await redis.client.delete(f"session:{session_id}")
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "User successfully logged out!"},
    )
    response.delete_cookie(
        "session_id",
        httponly=True,
        secure=settings.ENVIRONMENT != "dev",
        samesite="strict",
    )
    return response
