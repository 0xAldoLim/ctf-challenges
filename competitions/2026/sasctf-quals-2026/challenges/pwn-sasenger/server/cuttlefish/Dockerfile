FROM debian:12

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg sudo \
        socat iproute2 iptables iputils-ping \
        python3 procps psmisc netcat-openbsd unzip \
        libasound2 libpulse0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://us-apt.pkg.dev/doc/repo-signing-key.gpg \
        -o /etc/apt/trusted.gpg.d/artifact-registry.asc \
    && chmod a+r /etc/apt/trusted.gpg.d/artifact-registry.asc \
    && echo "deb https://us-apt.pkg.dev/projects/android-cuttlefish-artifacts android-cuttlefish main" \
        > /etc/apt/sources.list.d/artifact-registry.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cuttlefish-base cuttlefish-user \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/lib/cuttlefish-common/bin:${PATH}"

WORKDIR /cf
