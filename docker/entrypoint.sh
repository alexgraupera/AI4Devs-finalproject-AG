#!/bin/sh
# Brings the schema up to date, then becomes the server.
#
# `exec` matters: it replaces this shell with the server, so the server is PID 1 and receives the
# SIGTERM a platform sends on deploy, finishing its requests instead of being killed mid-review.
set -e

# Only the API has a database; the UI container runs the same image without one.
if [ -n "$DATABASE_URL" ]; then
    alembic upgrade head

    # The corpus is derived data: a new or replaced database is rebuilt from the BOE on start-up.
    # Both steps are idempotent (a second run downloads 5 KB of metadata and embeds nothing), and
    # neither is fatal: a BOE outage must not stop the service from answering with what it has.
    if [ "$BOOTSTRAP_CORPUS" = "true" ]; then
        python -m app.ingestion || echo "corpus bootstrap: the ingestion failed, serving what is stored" >&2
        python -m app.generation.rag.embed || echo "corpus bootstrap: the embedding failed, serving what is stored" >&2
    fi
fi

exec "$@"
