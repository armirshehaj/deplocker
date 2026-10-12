from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool


async def ensure_deliverable(address: str) -> None:
    """Answer 422 when DNS shows the address's domain cannot receive email.

    A lookup that times out or finds no nameserver lets the address through.
    """
    try:
        # Bounds the request, which waits on the lookup
        await run_in_threadpool(
            validate_email, address, check_deliverability=True, timeout=5
        )

    except EmailNotValidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{exc} Please check the email address.",
        ) from exc
