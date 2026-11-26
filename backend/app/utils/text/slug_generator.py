from typing import Annotated

from pydantic import AfterValidator
from slugify import slugify


def generate_slug(name: str) -> str:
    """Converts a name into a lowercase, URL-safe slug, raising ValueError when
    no letter or digit survives.

        "Café Médiatech" → "cafe-mediatech"
        "My___Org" → "my-org"
    """

    # Apostrophes join the words around them: "Alice's" gives "alices", not
    # "alice-s".
    slug = slugify(name, replacements=[("'", "")], backend="anyascii")

    if not slug:
        raise ValueError("Name must contain at least one alphanumeric character!")

    return slug


def ensure_sluggable(name: str) -> str:
    generate_slug(name)
    return name


# A name that `generate_slug` accepts. Request schemas use it, so an unusable
# name is rejected as a 422 before it reaches a route.
SluggableName = Annotated[str, AfterValidator(ensure_sluggable)]
