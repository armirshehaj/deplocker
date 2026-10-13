from fastapi import APIRouter

router = APIRouter()

# Imported for their side effect: each module registers its routes on `router`.
from app.routers.auth import (  # noqa: E402
    deplocker_auth,
    github_oauth,
    google_oauth,
    passkeys,
    shared,
)

__all__ = ["router"]
