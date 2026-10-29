# Python 3.14 on Debian 13, rebuilt for each Python patch and each update of the
# Debian image; a patch-version tag stops being rebuilt once the next patch ships
FROM python:3.14-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# curl runs the api healthcheck; git clones the repositories deployments build from;
# uv installs every Python package, so pip is removed
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/* \
    && pip uninstall -y pip

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
# Caddy serves the API under /api; the root path makes the docs page fetch its
# schema there
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--root-path", "/api"]