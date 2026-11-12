FROM alpine:3.22 AS builder

RUN apk add --no-cache gcc musl-dev libseccomp-dev

WORKDIR /app
COPY sentinel/sentinel-seccomp.c ./
RUN gcc -O2 -o redis-sentinel-seccomp sentinel-seccomp.c -lseccomp

FROM redis:8.4.4-alpine

RUN apk add --no-cache \
    libseccomp \
    netcat-openbsd \
    salt-minion

ENV PYTHONWARNINGS=ignore::DeprecationWarning

COPY --from=builder /app/redis-sentinel-seccomp /usr/local/bin/redis-sentinel-seccomp
COPY salt/minion-entrypoint.sh /usr/local/bin/minion-entrypoint.sh
ADD sentinel/entry.sh /

RUN chmod +x /entry.sh /usr/local/bin/minion-entrypoint.sh

ENTRYPOINT ["/entry.sh"]
