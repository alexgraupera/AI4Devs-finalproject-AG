#!/bin/sh
# Brings the schema up to date, then becomes the server.
#
# `exec` matters: it replaces this shell with the server, so the server is PID 1 and receives the
# SIGTERM a platform sends on deploy, finishing its requests instead of being killed mid-review.
set -e

# Only the API has a database; the UI container runs the same image without one.
if [ -n "$DATABASE_URL" ]; then
    alembic upgrade head
fi

exec "$@"
