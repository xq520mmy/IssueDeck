#!/bin/sh
set -e

# Run database migrations before starting the server
uv run alembic upgrade head

exec uv run "$@"
