import re
import uuid

# A full commit hash, as deployments.commit_hash stores it
COMMIT_HASH = re.compile(r"[0-9a-f]{40}")


def image_tag(application_id: uuid.UUID, commit_hash: str) -> str:
    """The tag of the image an application builds from a commit. It derives from
    the application's id, unique and fixed unlike its slugs, so no two
    applications share a tag, and the same commit always yields the same one.
    Raises ValueError when `commit_hash` is not a full commit hash."""
    if not COMMIT_HASH.fullmatch(commit_hash):
        raise ValueError(f"Not a full commit hash: {commit_hash!r}")
    return f"deplocker-app-{application_id}:{commit_hash}"


def container_name(application_id: uuid.UUID) -> str:
    """The name of an application's container, by which the other containers on
    the deployed applications' network reach it."""
    return f"deplocker-app-{application_id}"
