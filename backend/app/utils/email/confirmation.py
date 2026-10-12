import logging
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.core import settings
from app.utils.email.templates import get_template

logger = logging.getLogger(__name__)


async def send_confirmation_email(receiver_address: str, token: str) -> None:
    """Email the account activation link, answering 503 when it cannot be sent."""
    message = EmailMessage()

    message["From"] = settings.SENDER_EMAIL_ADDRESS
    message["To"] = receiver_address
    message["Subject"] = "Deplocker account activation request"

    confirmation_url = f"{settings.FRONTEND_URL}/account/confirm?email={receiver_address}&token={token}"
    context_data = {"confirmation_url": confirmation_url}
    html_content = get_template(
        "account_confirmation_email.html", context_data=context_data
    )

    message.set_content(html_content, subtype="html")

    try:
        await run_in_threadpool(_send, message)

    # SMTPException subclasses OSError, so this covers protocol and network failures
    except OSError as exc:
        logger.error(
            "Email confirmation for account activation failed to send!",
            extra={"receiver_address": receiver_address, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The confirmation email could not be sent. Please try again later.",
        ) from exc


def _send(message: EmailMessage) -> None:
    # Bounds the request, which waits on the send
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(settings.SENDER_EMAIL_ADDRESS, settings.EMAIL_HOST_PASSWORD)
        server.send_message(message)
