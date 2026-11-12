FROM alpine:3.21 AS rootfs

RUN apk add --no-cache \
    alpine-base openrc \
    docker docker-cli-compose \
    openssh-server \
    linux-virt mkinitfs \
    e2fsprogs util-linux \
    bash curl wget iptables ip6tables iproute2

RUN for svc in devfs dmesg mdev hwdrivers modules sysctl hostname bootmisc syslog; do \
        rc-update add $svc sysinit 2>/dev/null || true; \
    done && \
    for svc in networking docker sshd local; do \
        rc-update add $svc default 2>/dev/null || true; \
    done && \
    for svc in mount-ro killprocs savecache; do \
        rc-update add $svc shutdown 2>/dev/null || true; \
    done && \
    rc-update add modules boot 2>/dev/null || true

RUN echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    mkdir -p /root/.ssh /run/sshd

RUN sed -i 's|^tty1|#tty1|' /etc/inittab && \
    echo 'ttyS0::respawn:/sbin/getty -L ttyS0 115200 vt100' >> /etc/inittab

RUN printf 'auto lo\niface lo inet loopback\n\nauto eth0\niface eth0 inet dhcp\n' \
        > /etc/network/interfaces && \
    printf 'nameserver 10.0.2.3\n' > /etc/resolv.conf.head

RUN mkdir -p /etc/docker && \
    printf '{\n  "storage-driver": "overlay2",\n  "log-driver": "json-file",\n  "log-opts": {"max-size": "10m", "max-file": "3"}\n}\n' \
        > /etc/docker/daemon.json

RUN printf 'qemu_fw_cfg\nvirtio_pci\nvirtio_blk\nvirtio_net\next4\n' > /etc/modules

RUN printf '/dev/vda\t/\text4\trw,relatime\t0\t1\n' > /etc/fstab

RUN echo 'ctf-vm' > /etc/hostname

COPY server/ /opt/task/

COPY vm/scripts/init.sh /etc/local.d/task.start
RUN chmod +x /etc/local.d/task.start

RUN ls -la /boot/initramfs* /boot/vmlinuz*

RUN rm -rf /var/cache/apk/* /tmp/* /usr/share/man /usr/share/doc


FROM alpine:3.21 AS diskbuilder

RUN apk add --no-cache qemu-img e2fsprogs

COPY --from=rootfs / /rootfs/

RUN rm -rf /rootfs/proc/* /rootfs/sys/* /rootfs/dev/*
RUN mkdir -p /rootfs/proc /rootfs/sys /rootfs/dev /rootfs/tmp /rootfs/run

RUN cp /rootfs/boot/vmlinuz-virt /vmlinuz && \
    cp /rootfs/boot/initramfs-virt /initramfs

RUN mke2fs -d /rootfs -t ext4 -F /disk.raw 10G && \
    qemu-img convert -f raw -O qcow2 -c /disk.raw /disk.qcow2 && \
    rm -f /disk.raw



FROM alpine:3.21

RUN apk add --no-cache qemu-system-x86_64 qemu-img bash openssl socat

RUN mkdir -p /vm

COPY --from=diskbuilder /disk.qcow2 /vm/disk.qcow2
COPY --from=diskbuilder /vmlinuz /vm/vmlinuz
COPY --from=diskbuilder /initramfs /vm/initramfs

COPY vm/entrypoint.sh /vm/entrypoint.sh
RUN chmod +x /vm/entrypoint.sh

EXPOSE 2222 2223 10022

ENTRYPOINT ["/vm/entrypoint.sh"]
