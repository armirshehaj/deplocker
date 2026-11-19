from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator


def carries_credentials(url: str) -> bool:
    """Whether `url` holds a username, password or token before its host, as
    `https://<token>@github.com/…` does. A URL too malformed to split is left
    for git to refuse."""
    try:
        return urlsplit(url).username is not None
    except ValueError:
        return False


def ensure_no_credentials(url: str) -> str:
    if carries_credentials(url):
        raise ValueError("Repository URL must not carry credentials")
    return url


# A repository URL without credentials, which would otherwise be stored,
# returned by the API and passed on git's command line. Request schemas use it,
# so such a URL is rejected as a 422 before it reaches a route.
RepositoryUrl = Annotated[str, AfterValidator(ensure_no_credentials)]
