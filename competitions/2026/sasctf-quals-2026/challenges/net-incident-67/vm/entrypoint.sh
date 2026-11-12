#!/bin/sh
set -e

if [ -z "${FLAG:-}" ]; then
    echo "ERROR: FLAG environment variable is required" >&2
    exit 1
fi

printf '%s' "$FLAG" > /tmp/flag
chmod 600 /tmp/flag

TLS_KEY=/tmp/ssh-tls.key
TLS_CERT=/tmp/ssh-tls.crt
TLS_PEM=/tmp/ssh-tls.pem
TLS_DOMAIN="${TLS_DOMAIN:-localhost}"

openssl req -x509 -newkey rsa:2048 -nodes \
    -days "${TLS_CERT_DAYS:-7}" \
    -subj "/CN=${TLS_DOMAIN}" \
    -keyout "$TLS_KEY" -out "$TLS_CERT" >/dev/null 2>&1
cat "$TLS_KEY" "$TLS_CERT" > "$TLS_PEM"
chmod 600 "$TLS_KEY" "$TLS_CERT" "$TLS_PEM"

start_tls_proxy() {
    listen_port="$1"
    target_port="$2"

    socat \
        "OPENSSL-LISTEN:${listen_port},bind=0.0.0.0,reuseaddr,fork,cert=${TLS_PEM},verify=0" \
        "TCP:127.0.0.1:${target_port}" &
}

start_tls_proxy 2222 12222
start_tls_proxy 2223 12223
start_tls_proxy 10022 11022

qemu-img create -f qcow2 -b /vm/disk.qcow2 -F qcow2 /tmp/overlay.qcow2

ACCEL="-machine accel=tcg"
[ -e /dev/kvm ] && ACCEL="-machine accel=kvm -cpu host"

exec qemu-system-x86_64 \
    $ACCEL \
    -m "${VM_MEMORY:-2048}" -smp "${VM_CPUS:-2}" \
    -kernel /vm/vmlinuz -initrd /vm/initramfs \
    -append "root=/dev/vda rw rootfstype=ext4 console=ttyS0 modules=virtio_pci,virtio_blk,ext4" \
    -drive file=/tmp/overlay.qcow2,if=virtio,format=qcow2 \
    -fw_cfg name=opt/net-incident-67/flag,file=/tmp/flag \
    -netdev user,id=net0,hostfwd=tcp:127.0.0.1:12222-:2222,hostfwd=tcp:127.0.0.1:12223-:2223,hostfwd=tcp:127.0.0.1:11022-:22 \
    -device virtio-net-pci,netdev=net0 \
    -nographic -no-reboot
