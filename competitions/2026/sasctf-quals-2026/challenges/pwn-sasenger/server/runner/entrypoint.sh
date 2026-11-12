#!/bin/sh
set -e
LOG_LEVEL_LC=$(printf '%s' "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
exec gunicorn \
    --workers 1 \
    --threads 16 \
    --timeout 600 \
    --log-level "$LOG_LEVEL_LC" \
    --bind 0.0.0.0:13337 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    service:app
