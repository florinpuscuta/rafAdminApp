#!/bin/sh
# Entrypoint pentru containerul de producție.
# Rulează migrațiile Alembic înainte de server, apoi pornește uvicorn cu argumentele primite.

set -e

echo "[entrypoint] alembic upgrade head..."
alembic upgrade head

echo "[entrypoint] starting uvicorn..."
exec "$@"
