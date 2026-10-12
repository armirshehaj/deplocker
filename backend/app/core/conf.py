import os
from typing import Literal
from urllib.parse import urlparse

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    TEST_DB: str

    # Picks each URL pair's value and whether cookies require HTTPS
    ENVIRONMENT: Literal["dev", "production"]

    # CORS allows both, whatever the environment
    DEV_FRONTEND_URL: str
    PROD_FRONTEND_URL: str

    # The API's own external origin. OAuth2 providers redirect back to it, so it
    # must match the callback URL registered with each of them.
    DEV_PUBLIC_URL: str = "http://localhost:8080"
    PROD_PUBLIC_URL: str

    # JWT signing for email confirmation links
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRES_MINUTES: int

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    # The SMTP account that sends confirmation emails
    SMTP_HOST: str
    SMTP_PORT: int
    SENDER_EMAIL_ADDRESS: str
    EMAIL_HOST_PASSWORD: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_AUTH_URL: str
    GOOGLE_TOKEN_URL: str
    GOOGLE_USER_INFO_URL: str

    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    GITHUB_AUTH_URL: str
    GITHUB_TOKEN_URL: str
    GITHUB_USER_INFO_URL: str
    GITHUB_USER_EMAILS_URL: str

    # The Relying Party ID scopes passkeys to a domain: the frontend's host, or a
    # registrable suffix of it when the frontend lives on a subdomain.
    WEBAUTHN_RP_NAME: str = "Deplocker"
    WEBAUTHN_RP_ID: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def FRONTEND_URL(self) -> str:
        """The frontend's URL in the active environment."""
        return (
            self.PROD_FRONTEND_URL
            if self.ENVIRONMENT == "production"
            else self.DEV_FRONTEND_URL
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def PUBLIC_URL(self) -> str:
        """The API's URL in the active environment."""
        return (
            self.PROD_PUBLIC_URL
            if self.ENVIRONMENT == "production"
            else self.DEV_PUBLIC_URL
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def RP_ID(self) -> str:
        """Relying Party ID, falling back to the frontend host when unset."""
        return (
            self.WEBAUTHN_RP_ID or urlparse(self.FRONTEND_URL).hostname or "localhost"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return f"{self.PUBLIC_URL}/auth/google/callback"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def GITHUB_REDIRECT_URI(self) -> str:
        return f"{self.PUBLIC_URL}/auth/github/callback"

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"), env_file_encoding="utf-8"
    )


settings = Settings()
