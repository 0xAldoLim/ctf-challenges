FROM oliver006/redis_exporter:latest AS source

FROM alpine:3.22

RUN apk add --no-cache \
    ca-certificates \
    netcat-openbsd \
    salt-minion

ENV PYTHONWARNINGS=ignore::DeprecationWarning

COPY --from=source /redis_exporter /redis_exporter
COPY salt/minion-entrypoint.sh /usr/local/bin/minion-entrypoint.sh
COPY --chmod=755 exporter/entrypoint.sh /entrypoint.sh

RUN chmod +x /usr/local/bin/minion-entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
