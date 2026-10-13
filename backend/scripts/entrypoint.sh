#!/bin/sh
set -e

uv run --no-sync alembic upgrade head
exec "$@"