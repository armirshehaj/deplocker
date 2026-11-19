import re
import uuid

import pytest

from app.utils.docker.names import image_tag

COMMIT = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

# Docker's grammar for an image's repository and tag
IMAGE_REFERENCE = re.compile(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*:\w[\w.-]{0,127}")


def test_tag_of_a_commit() -> None:
    application_id = uuid.uuid4()

    tag = image_tag(application_id, COMMIT)

    assert tag == f"deplocker-app-{application_id}:{COMMIT}"
    assert IMAGE_REFERENCE.fullmatch(tag)


def test_applications_never_share_a_tag() -> None:
    assert image_tag(uuid.uuid4(), COMMIT) != image_tag(uuid.uuid4(), COMMIT)


@pytest.mark.parametrize(
    "commit_hash", ["7fd1a60", COMMIT.upper(), f"{COMMIT}0", "main"]
)
def test_not_a_full_commit_hash(commit_hash: str) -> None:
    with pytest.raises(ValueError, match="Not a full commit hash"):
        image_tag(uuid.uuid4(), commit_hash)
