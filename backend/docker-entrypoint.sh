#!/bin/sh
set -e

# Apply schema migrations (including pgvector/code_chunks on PostgreSQL)
# before the API starts. Safe to run on every container start.
alembic upgrade head

exec "$@"
