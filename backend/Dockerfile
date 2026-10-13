FROM python:3.14.5-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# curl runs the api healthcheck; git clones the repositories deployments build from
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

FROM base AS test
RUN uv sync --frozen
COPY . .
CMD ["uv", "run", "pytest", "tests/", "-v"]


FROM base AS production
RUN uv sync --frozen --no-dev
COPY . .
EXPOSE 8080
ENTRYPOINT ["sh", "./scripts/entrypoint.sh" ]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]