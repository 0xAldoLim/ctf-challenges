#!/bin/sh
set -e
LOG_LEVEL_LC=$(printf '%s' "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
exec gunicorn \
    --workers 1 \
    --threads 512 \
    --timeout 120 \
    --log-level "$LOG_LEVEL_LC" \
    --bind 0.0.0.0:8080 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    relay:app
