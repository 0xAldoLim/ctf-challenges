#!/bin/sh
# Launch the service. The flag is materialized per QEMU run by runner.execute()
# (fresh files dir + randomized handle + fresh key), so there is nothing to plant
# at startup and participants never share state.
set -e

# One worker process (the heavy work is in subprocesses); many threads since
# requests mostly block on those subprocesses. Concurrency is bounded inside
# the app by MAX_CONCURRENT.
exec gunicorn \
    --workers 1 \
    --threads "${GUNICORN_THREADS:-32}" \
    --timeout "${GUNICORN_TIMEOUT:-90}" \
    --bind 0.0.0.0:2048 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    service:app
