ARG BASE_IMAGE=ubuntu:24.04

FROM ${BASE_IMAGE}

ARG VALKEY_VERSION=7.2.11
ARG VALKEY_PLATFORM=noble-x86_64
ARG VALKEY_SHA256=0e26bf927d7c4c10f3f5afdf258cd1fea83bfaa56f598d45b5336d0a96bae94b
ENV container=docker
ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        cron \
        dbus \
        dbus-user-session \
        gdb \
        libssl3t64 \
        libpam-systemd \
        openssh-server \
        passwd \
        systemd \
        systemd-sysv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://download.valkey.io/releases/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}.tar.gz" -o /tmp/valkey.tar.gz \
    && echo "${VALKEY_SHA256}  /tmp/valkey.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/valkey.tar.gz -C /tmp \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-server" /usr/bin/valkey-server \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-check-rdb" /usr/bin/valkey-check-rdb \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-check-aof" /usr/bin/valkey-check-aof \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-cli" /usr/bin/valkey-cli \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-benchmark" /usr/bin/valkey-benchmark \
    && install -m 0755 "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}/bin/valkey-sentinel" /usr/bin/valkey-sentinel \
    && rm -rf /tmp/valkey.tar.gz "/tmp/valkey-${VALKEY_VERSION}-${VALKEY_PLATFORM}"

RUN getent group valkey || groupadd --system valkey \
    && getent passwd valkey || useradd --system --gid valkey --home-dir /var/lib/valkey --create-home --shell /bin/bash valkey \
    && passwd -d valkey \
    && printf '%s\n' 'ctf{asdfwe343_flagsrgasz}' > /root/flag.txt \
    && chown root:root /root/flag.txt \
    && chmod 0400 /root/flag.txt \
    && install -d -o valkey -g valkey -m 0750 /var/lib/valkey \
    && install -d -o valkey -g valkey -m 0775 /var/cores \
    && install -d -o valkey -g adm -m 2750 /var/log/valkey \
    && install -d -o valkey -g valkey -m 2770 /etc/valkey \
    && install -d -m 0755 /etc/cron.cloud \
    && install -d -m 0755 /run/sshd

COPY config/valkey/valkey.conf /etc/valkey/valkey.conf
COPY config/systemd/valkey-server.service /etc/systemd/system/valkey-server.service
COPY config/ssh/valkey.conf /etc/ssh/sshd_config.d/90-valkey.conf
COPY config/cron/cores-cleanup /etc/cron.d/cores-cleanup
COPY config/cron/cores-cleanup.sh /etc/cron.cloud/cores-cleanup.sh

RUN chown -R valkey:valkey /etc/valkey /var/lib/valkey \
    && chown valkey:valkey /var/cores \
    && chown valkey:adm /var/log/valkey \
    && chmod 2770 /etc/valkey \
    && chmod 0775 /var/cores \
    && chmod 2750 /var/log/valkey \
    && chmod 0644 /etc/systemd/system/valkey-server.service \
    && chmod 0644 /etc/cron.d/cores-cleanup \
    && chmod 0755 /etc/cron.cloud/cores-cleanup.sh \
    && systemctl enable valkey-server.service \
    && systemctl enable ssh.service \
    && systemctl enable cron.service \
    && (systemctl mask getty.target console-getty.service serial-getty@.service || true)

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
