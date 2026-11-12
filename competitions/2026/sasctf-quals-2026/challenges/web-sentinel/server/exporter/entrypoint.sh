#!/bin/sh
set -eu

if [ ! -f /etc/exporter.env ]; then
    /usr/local/bin/minion-entrypoint.sh
fi

until [ -f /etc/exporter.env ]; do
    sleep 1
done

set -a
. /etc/exporter.env
set +a

exec /redis_exporter \
    --redis.addr="$REDIS_ADDR" \
    --redis.password="$REDIS_PASSWORD"
