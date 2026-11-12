FROM --platform=linux/amd64 golang:1.24-bookworm AS web-build

WORKDIR /src
COPY web/go.mod web/go.sum ./
RUN go mod download
COPY web/ ./
RUN CGO_ENABLED=0 go build -o /out/paradoxy-web .

FROM --platform=linux/amd64 debian:bookworm-slim AS k0s-official-bins

ARG K0S_VERSION=v1.25.16+k0s.0
ARG K0S_VERSION_URL=v1.25.16%2Bk0s.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl findutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSLf \
      "https://github.com/k0sproject/k0s/releases/download/${K0S_VERSION_URL}/k0s-${K0S_VERSION}-amd64" \
      -o /usr/local/bin/k0s && \
    chmod 0755 /usr/local/bin/k0s && \
    mkdir -p /extract/controller /extract/single /official-k0s-bin && \
    timeout 90s k0s controller \
      --data-dir /extract/controller \
      --disable-components metrics-server >/tmp/k0s-controller-extract.log 2>&1 || true && \
    timeout 180s k0s controller --single \
      --data-dir /extract/single \
      --disable-components metrics-server >/tmp/k0s-single-extract.log 2>&1 || true && \
    cp -a /extract/controller/bin/. /official-k0s-bin/ && \
    cp -a /extract/single/bin/. /official-k0s-bin/ && \
    chmod 0555 /official-k0s-bin/* && \
    for bin in \
      containerd \
      containerd-shim \
      containerd-shim-runc-v1 \
      containerd-shim-runc-v2 \
      etcd \
      kine \
      konnectivity-server \
      kube-apiserver \
      kube-controller-manager \
      kubelet \
      kube-scheduler \
      runc \
      xtables-legacy-multi \
      xtables-nft-multi; do \
        test -x "/official-k0s-bin/${bin}" || { \
          tail -n 160 /tmp/k0s-controller-extract.log; \
          tail -n 160 /tmp/k0s-single-extract.log; \
          ls -la /official-k0s-bin; \
          exit 1; \
        }; \
    done

FROM --platform=linux/amd64 ubuntu:22.04 AS vm-build

ARG K0S_VERSION=v1.25.16+k0s.0
ARG K0S_VERSION_URL=v1.25.16%2Bk0s.0

ENV DEBIAN_FRONTEND=noninteractive
ENV UBUNTU_RELEASE=jammy

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      debootstrap \
      e2fsprogs \
      qemu-utils \
      xz-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN debootstrap --variant=minbase --components=main,universe \
      --include=systemd,systemd-sysv,udev,dbus,dbus-user-session,policykit-1,ca-certificates,curl,bash,conntrack,findutils,iproute2,iptables,iputils-ping,jq,kmod,less,libcap2-bin,lsof,netcat-openbsd,procps,python3,socat,sudo,uidmap,util-linux,linux-image-generic \
      "${UBUNTU_RELEASE}" /rootfs http://archive.ubuntu.com/ubuntu

COPY --from=k0s-official-bins /usr/local/bin/k0s /rootfs/usr/local/bin/k0s
COPY --from=k0s-official-bins /official-k0s-bin/ /rootfs/opt/paradoxy/k0s-bin/

RUN mkdir -p /rootfs/opt/paradoxy/k0s-images && \
    curl -sSLf \
      "https://github.com/k0sproject/k0s/releases/download/${K0S_VERSION_URL}/k0s-airgap-bundle-${K0S_VERSION}-amd64" \
      -o "/rootfs/opt/paradoxy/k0s-images/k0s-airgap-bundle-${K0S_VERSION}-amd64" && \
    chmod 0644 "/rootfs/opt/paradoxy/k0s-images/k0s-airgap-bundle-${K0S_VERSION}-amd64"

RUN chmod 0755 /rootfs/usr/local/bin/k0s && \
    chmod 0555 /rootfs/opt/paradoxy/k0s-bin/*

RUN chroot /rootfs apt-get update && \
    chroot /rootfs apt-get install -y --no-install-recommends initramfs-tools && \
    kernel_version="$(basename "$(find /rootfs/lib/modules -mindepth 1 -maxdepth 1 -type d | sort | tail -n1)")" && \
    chroot /rootfs update-initramfs -c -k "${kernel_version}" && \
    rm -rf /rootfs/var/lib/apt/lists/*

COPY --from=web-build /out/paradoxy-web /rootfs/opt/paradoxy/web/paradoxy-web
COPY web/templates /rootfs/opt/paradoxy/web/templates
COPY deploy.yml /rootfs/opt/paradoxy/deploy.yml
COPY qemu/paradoxy-bootstrap /rootfs/usr/local/sbin/paradoxy-bootstrap
COPY qemu/paradoxy-bootstrap-api.py /rootfs/usr/local/sbin/paradoxy-bootstrap-api.py
COPY qemu/paradoxy-web.service /rootfs/etc/systemd/system/paradoxy-web.service
COPY qemu/paradoxy-bootstrap-api.service /rootfs/etc/systemd/system/paradoxy-bootstrap-api.service

RUN chmod 0755 \
      /rootfs/opt/paradoxy/web/paradoxy-web \
      /rootfs/usr/local/sbin/paradoxy-bootstrap \
      /rootfs/usr/local/sbin/paradoxy-bootstrap-api.py && \
    mkdir -p /rootfs/etc/systemd/network /rootfs/etc/k0s /rootfs/root/konnectivity-agent-token /rootfs/opt/paradoxy/web && \
    printf '%s\n' \
      '[Match]' \
      'MACAddress=52:54:00:aa:00:01' \
      '' \
      '[Network]' \
      'DHCP=yes' \
      > /rootfs/etc/systemd/network/10-controller-wan.network && \
    printf '%s\n' \
      '[Match]' \
      'MACAddress=52:54:00:aa:00:02' \
      '' \
      '[Network]' \
      'DHCP=yes' \
      > /rootfs/etc/systemd/network/10-worker-wan.network && \
    printf '%s\n' \
      '[Match]' \
      'MACAddress=52:54:00:aa:00:11' \
      '' \
      '[Network]' \
      'Address=172.31.0.10/24' \
      > /rootfs/etc/systemd/network/20-controller-lan.network && \
    printf '%s\n' \
      '[Match]' \
      'MACAddress=52:54:00:aa:00:12' \
      '' \
      '[Network]' \
      'Address=172.31.0.11/24' \
      > /rootfs/etc/systemd/network/20-worker-lan.network && \
    rm -f /rootfs/etc/resolv.conf && \
    printf '%s\n' \
      'nameserver 10.0.2.3' \
      'nameserver 1.1.1.1' \
      'nameserver 8.8.8.8' \
      'options timeout:2 attempts:3' \
      > /rootfs/etc/resolv.conf && \
    printf '%s\n' '/dev/vda / ext4 defaults 0 1' > /rootfs/etc/fstab && \
    printf '%s\n' \
      'apiVersion: v1' \
      'kind: Config' \
      'clusters: []' \
      'contexts: []' \
      'current-context: ""' \
      'users: []' \
      > /rootfs/opt/paradoxy/web/config && \
    chroot /rootfs useradd -u 994 -m -s /bin/bash ubb && \
    chroot /rootfs useradd -u 1200 -m -d /var/lib/paradoxy-web -s /usr/sbin/nologin paradoxy-web && \
    chroot /rootfs chown -R paradoxy-web:paradoxy-web /opt/paradoxy/web /var/lib/paradoxy-web && \
    chroot /rootfs systemctl set-default multi-user.target && \
    chroot /rootfs systemctl enable systemd-networkd.service dbus.service systemd-logind.service paradoxy-web.service paradoxy-bootstrap-api.service && \
    chroot /rootfs systemctl disable systemd-resolved.service >/dev/null 2>&1 || true && \
    ln -sf /dev/null /rootfs/etc/systemd/system/systemd-resolved.service && \
    chroot /rootfs systemctl disable systemd-networkd-wait-online.service >/dev/null 2>&1 || true && \
    ln -sf /dev/null /rootfs/etc/systemd/system/systemd-networkd-wait-online.service

RUN mkdir -p /vm && \
    kernel="$(find /rootfs/boot -maxdepth 1 -type f -name 'vmlinuz-*' | sort | tail -n1)" && \
    initrd="$(find /rootfs/boot -maxdepth 1 -type f -name 'initrd.img-*' | sort | tail -n1)" && \
    if [ -z "${kernel}" ] && [ -e /rootfs/vmlinuz ]; then kernel=/rootfs/vmlinuz; fi && \
    if [ -z "${initrd}" ] && [ -e /rootfs/initrd.img ]; then initrd=/rootfs/initrd.img; fi && \
    if [ -z "${kernel}" ] || [ -z "${initrd}" ]; then \
      find /rootfs /rootfs/boot -maxdepth 2 \( -name 'vmlinuz*' -o -name 'initrd*' \) -print; \
      exit 1; \
    fi && \
    cp -L "${kernel}" /vm/vmlinuz && \
    cp -L "${initrd}" /vm/initrd.img && \
    truncate -s 16G /vm/rootfs.raw && \
    mkfs.ext4 -F -d /rootfs /vm/rootfs.raw && \
    qemu-img convert -f raw -O qcow2 /vm/rootfs.raw /vm/rootfs.qcow2 && \
    rm -f /vm/rootfs.raw

FROM --platform=linux/amd64 debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      qemu-system-x86 \
      qemu-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=vm-build /vm/vmlinuz /opt/paradoxy/vmlinuz
COPY --from=vm-build /vm/initrd.img /opt/paradoxy/initrd.img
COPY --from=vm-build /vm/rootfs.qcow2 /opt/paradoxy/rootfs.qcow2
COPY qemu/qemu-entrypoint /usr/local/bin/qemu-entrypoint

RUN chmod 0755 /usr/local/bin/qemu-entrypoint && \
    chmod 0644 /opt/paradoxy/vmlinuz /opt/paradoxy/initrd.img /opt/paradoxy/rootfs.qcow2

EXPOSE 8080 8081
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/qemu-entrypoint"]
