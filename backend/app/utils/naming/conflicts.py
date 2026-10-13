from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# The constraints that keep a name or slug unique within its scope (see the
# models). Any other constraint failing is not a naming conflict.
NAME_CONSTRAINTS = frozenset(
    {
        "uq_projects_organization_id_name",
        "uq_projects_organization_id_slug",
        "uq_applications_project_id_name",
        "uq_applications_project_id_slug",
        "ix_organizations_slug",
    }
)


async def commit_unless_name_taken(db_session: AsyncSession, detail: str) -> None:
    """Commit, answering 409 with `detail` if a name or slug is already taken.

    The constraint decides rather than a lookup beforehand, so a concurrent
    request taking the same name in between still gets a 409, not a 500.
    """
    try:
        await db_session.commit()
    except IntegrityError as exc:
        if _violated_constraint(exc) not in NAME_CONSTRAINTS:
            raise

        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=detail
        ) from exc


def _violated_constraint(exc: IntegrityError) -> str | None:
    # asyncpg's own error, which names the constraint, is the DBAPI error's cause.
    cause = exc.orig.__cause__ if exc.orig is not None else None
    return getattr(cause, "constraint_name", None)
