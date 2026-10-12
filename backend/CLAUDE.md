# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Dependency management (uses uv)
uv sync                    # install production deps
uv sync --dev --frozen     # install all deps (locked)

# Run the API (inside container or with env loaded)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Lint and format
ruff check .
ruff format .

# Tests (requires PostgreSQL with TEST_DB database running)
pytest tests/ -v
pytest tests/path/to/test.py::test_name -v   # single test

# Run tests in Docker (no local Postgres needed)
docker compose -f docker-compose.test.yml up

# Alembic migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Environment

Settings come from real environment variables; compose injects them by reading `/etc/deplocker/.env` on the host (`env_file:` in `docker-compose.yml`). `app/core/conf.py` also accepts a dotenv file at `$ENV_FILE`, defaulting to `.env` in the working directory — a fallback for running the app outside compose, since environment variables take precedence. Copy `.env.example` to `/etc/deplocker/.env`. Required variables: Postgres connection, `TEST_DB`, `ENVIRONMENT` (`dev`|`production`), frontend URLs, `SECRET_KEY`/`ALGORITHM`/`ACCESS_TOKEN_EXPIRES_MINUTES`, Redis credentials, and SMTP email credentials.

## Architecture

### Request lifecycle

Routers (`app/routers/`) receive requests and inject dependencies via FastAPI's `Depends`. Simple CRUD is handled directly in routers. Complex domain logic is delegated to service classes (`app/services/`), which accept an `AsyncSession` and encapsulate the DB operations. All database access is async via SQLAlchemy + asyncpg.

### Helpers

Every helper function lives under `app/utils/` — never in a router, model or schema module, even when only one route calls it. Routers keep only path operation functions.

`app/utils/` is split into subdirectories named after the context a helper serves, so the tree reads as a map of the project: `app/utils/auth/` holds authentication helpers, one module per concern (`passkeys.py`, `google_oauth.py`, …) with `shared.py` for what several of them use. Put a new helper in the subdirectory of its context, creating the subdirectory (with an `__init__.py`) when none fits; do not add modules at the top level of `app/utils/`. A helper used across contexts goes in a subdirectory named for what it does (e.g. text formatting), not in a catch-all like `common/` or `misc/`.

### Authentication

Auth is **session-cookie based at the API level** — JWT is only used for email account confirmation links. On login, a UUID `session_id` is stored as a `Set-Cookie` (`httponly`, `samesite=strict`) and the session data is written to Redis with a 1-day TTL. Every protected route depends on `get_current_session` (`app/utils/auth/shared.py`), which reads `session_id` from the cookie and looks up the session in Redis.

Four ways in, all ending at `_login_response`: password, Google OAuth2, GitHub OAuth2, and passkeys (WebAuthn). Each has a router module under `app/routers/auth/` and a matching helper module under `app/utils/auth/`; the routers all register on the single `router` defined in `app/routers/auth/__init__.py`.

Passkeys use discoverable credentials, so `POST /auth/passkeys/login` identifies the account from the credential id alone. Both ceremonies are two calls — options, then verification — and the challenge issued by the first is held in Redis for 5 minutes and deleted on use, keyed by user id when registering (there is a session) and by a `passkey_challenge` cookie when logging in (there is not). `WEBAUTHN_RP_ID` scopes a credential to a domain and defaults to the frontend host; the expected origin is `settings.FRONTEND_URL`.

### Data layer

- `Base` (`app/core/database.py`) is the SQLAlchemy declarative base; all models inherit from it and get a `to_dict()` helper.
- Schemas (`app/schemas/`) are Pydantic models used for request validation and response serialization — they are separate from SQLAlchemy models.
- Slugs are auto-generated via `generate_slug()` (`app/utils/text/slug_generator.py`) when creating Projects, Applications, and Organizations.
- Names and slugs are unique within their parent: a project's per organization, an application's per project. An organization's name is a free display label and its slug a global handle (the default organization's gets a numeric suffix on collision). Request schemas type names as `SluggableName`, so a name `generate_slug()` rejects is a 422.
- Routes that write a name commit through `commit_unless_name_taken` (`app/utils/naming/conflicts.py`), which turns a violation of one of those constraints into a 409 — the constraint decides, not a lookup beforehand, so concurrent requests can't race past it. A new name or slug constraint must be added to its `NAME_CONSTRAINTS`, or its violations surface as 500s.

### Domain model

`Project` → `Application` → `Deployment` → `DeploymentLogs` is the core ownership chain. Applications hold the Docker/Git config (git URL, branch, dockerfile path, port, env vars, domain). A `Deployment` tracks a single deploy lifecycle through states: `pending → cloning → building → pushing → deploying → health_checking → success/failed/cancelled`.

`User` → `Organization` is M2M via `OrganizationMembersModel`. On registration, a default organization is automatically created for the user with `OWNER` role.

A membership's role ranks `OWNER` over `ADMIN` over `MEMBER`, each holding the powers of those below it. Routes reach a resource through `ensure_organization_member` and the `get_member_*` helpers (`app/utils/organizations/membership.py`): 404 outside the caller's organizations, 403 to a member below the `required_role` they're given (any member by default). A route needing more than membership on the resource in its `{id}` path takes it from the `require_role` dependency (`app/utils/organizations/roles.py`); a create route, whose parent is in the body, passes `required_role` to the helper.

- `MEMBER` reads everything and deploys.
- `ADMIN` also creates and updates projects and applications, since an application's config decides what code runs, with which secrets, on which domain.
- `OWNER` also deletes projects, applications and deployments.

### Confirmation emails

`send_confirmation_email` (`app/utils/email/confirmation.py`) sends the activation link within the request, running the SMTP exchange in the threadpool, and answers 503 when the send fails. Registration sends it before committing the new account and rolls back on failure, so the address can sign up again.

A mail server accepts a message for any address and reports a failed delivery later, as a bounce to the sender's mailbox, so a successful send does not mean the address exists. Registration first calls `ensure_deliverable` (`app/utils/email/deliverability.py`), which answers 422 when DNS shows the domain cannot receive email: it does not exist, or has no MX, A or AAAA record. An address at a real domain with a mistyped mailbox still passes; its account stays inactive.

An account must be confirmed within `CONFIRMATION_WINDOW` (24 hours) of signup, and every confirmation link expires with that window (`app/utils/auth/confirmation.py`). Until then, a password login answers 403 with the address on file, so the client can resend the link (`POST /auth/account/confirm/retry`) or move the account to a corrected address (`POST /auth/account/email`, which takes the password as proof of ownership). Past the window the account is released: login, resend and the address change answer 410, `check-username` reports the username free, and registration and the address change call `delete_released_accounts` first, which deletes released accounts with their default organizations. A Google or GitHub login confirms an unconfirmed account with the same email, since the provider verified the address.

The stack runs no task queue or worker. One comes with the first feature that needs work beyond a request, such as deployment builds, with Redis as its broker.

### Redis

`RedisManager` (`app/core/cache.py`) wraps `redis.asyncio` with a connection pool. It is used for session storage and also supports JSON operations (for future use). The `redis` singleton is imported from `app.core`.

### Startup and migrations

Alembic owns the schema. The container entrypoint (`scripts/entrypoint.sh`) runs `alembic upgrade head` before the app starts, and the FastAPI lifespan calls `ensure_schema_is_current` (`app/core/migrations.py`), which refuses to start unless the database is at the migration head — a stale schema fails loudly rather than being patched at runtime. Alembic (`alembic/env.py`) imports all models explicitly and uses the same `DATABASE_URL` from `app.core.database`.

Any model change needs a migration: CI runs `make backend-migrations-ci`, which applies the migrations to an empty database and fails if `alembic check` finds the models drifting from them. The test suite is the one place that still builds tables with `Base.metadata.create_all` (`tests/conftest.py`).

### Testing

Tests are async (`anyio` with asyncio backend). The `test_db_session` fixture connects to `TEST_DB`, wraps each test in a transaction that rolls back on teardown, and the `client` fixture overrides `get_db_session` with that session. Redis is expected to be available during test runs (use `fakeredis` for unit tests of cache-dependent code). In integration tests, the autouse `mock_smtp` fixture stands in for the SMTP server and records the emails sent, and the autouse `mock_dns` fixture stands in for the lookup of an address's mail domain. The `docker-compose.test.yml` provides a self-contained CI environment.
