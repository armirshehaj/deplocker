FROM python:3.14.5-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# curl runs the api healthcheck; git clones the repositories deployments build from
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# The virtual environment's commands, deplocker among them, run by name
ENV PATH="/app/.venv/bin:$PATH"

# Dependencies install ahead of the source, so code changes don't reinstall them
COPY pyproject.toml uv.lock ./

FROM base AS test
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen
CMD ["uv", "run", "pytest", "tests/", "-v"]


FROM base AS production
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
EXPOSE 8080
ENTRYPOINT ["sh", "./scripts/entrypoint.sh" ]
# Caddy serves the API under /api; the root path makes the docs page fetch its
# schema there
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--root-path", "/api"]