FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TMPDIR=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        qemu-system-x86 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY qemu/build/artifacts/disk.qcow2 /vm/disk.qcow2
COPY qemu/build/artifacts/vmlinuz /vm/vmlinuz
COPY qemu/build/artifacts/initrd.img /vm/initrd.img
COPY qemu/run-qemu.sh /usr/local/bin/run-qemu

RUN chmod 0755 /usr/local/bin/run-qemu \
    && chown -R 1000:1000 /vm

USER 1000:1000
EXPOSE 6379

ENTRYPOINT ["/usr/local/bin/run-qemu"]
