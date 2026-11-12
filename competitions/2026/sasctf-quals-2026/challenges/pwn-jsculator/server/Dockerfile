FROM ubuntu:26.04@sha256:0a8aa7e675b331b09dfe80f7a44a02642035aefca58b0034ad17ca2db8f952e6 AS ubuntu

ARG QJS_URL=https://github.com/quickjs-ng/quickjs/releases/download/v0.15.0/qjs-linux-x86_64
ARG QJS_SHA256=6f87100b30b2212d529b2024213d27c3ea8082d8b4ec5aec0f01e8a0824c4e1d

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app \
    && curl -fsSL "${QJS_URL}" -o /app/qjs-linux-x86_64 \
    && printf '%s  %s\n' "${QJS_SHA256}" "/app/qjs-linux-x86_64" | sha256sum -c - \
    && chmod 0555 /app/qjs-linux-x86_64

COPY --chmod=555 jsculator.js /app/jsculator.js
COPY --chmod=555 run.sh /app/run
COPY flag.txt /app/flag.txt

FROM pwn.red/jail

COPY --from=ubuntu / /srv
