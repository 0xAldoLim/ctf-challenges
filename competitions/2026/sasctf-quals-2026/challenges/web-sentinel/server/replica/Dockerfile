FROM redis:8.4.4-alpine

RUN apk add --no-cache \
    netcat-openbsd \
    salt-minion

ENV PYTHONWARNINGS=ignore::DeprecationWarning

COPY salt/minion-entrypoint.sh /usr/local/bin/minion-entrypoint.sh

RUN chmod +x /usr/local/bin/minion-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/minion-entrypoint.sh"]
