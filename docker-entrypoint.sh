#!/bin/sh
set -e

# Run database migrations before starting the server
uv run --no-dev alembic upgrade head

exec uv run --no-dev "$@"
