#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-${SCRIPT_DIR}/build}"
ARTIFACT_DIR="${BUILD_DIR}/artifacts"
ROOTFS_IMAGE="${ROOTFS_IMAGE:-keyval/qemu-rootfs:build}"
FINAL_IMAGE="${FINAL_IMAGE:-keyval-qemu:latest}"
DISK_SIZE="${DISK_SIZE:-4G}"
PUSH="${PUSH:-0}"
PLATFORM="${PLATFORM:-linux/amd64}"

mkdir -p "${BUILD_DIR}" "${ARTIFACT_DIR}"

docker build \
  --platform "${PLATFORM}" \
  -f "${SCRIPT_DIR}/rootfs.Dockerfile" \
  -t "${ROOTFS_IMAGE}" \
  "${DEPLOY_DIR}"

cid="$(docker create "${ROOTFS_IMAGE}")"
trap 'docker rm "${cid}" >/dev/null 2>&1 || true' EXIT
docker export "${cid}" -o "${BUILD_DIR}/rootfs.tar"
docker rm "${cid}" >/dev/null
trap - EXIT

docker run --rm --privileged \
  -v "${BUILD_DIR}:/build" \
  ubuntu:24.04 \
  bash -euxo pipefail -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends e2fsprogs qemu-utils tar coreutils findutils

    rm -f /build/disk.raw /build/artifacts/disk.qcow2
    truncate -s "'"${DISK_SIZE}"'" /build/disk.raw
    mkfs.ext4 -F -L rootfs /build/disk.raw

    mkdir -p /mnt/rootfs
    mount -o loop /build/disk.raw /mnt/rootfs
    tar -xf /build/rootfs.tar -C /mnt/rootfs
    sync
    umount /mnt/rootfs

    mkdir -p /build/artifacts /build/kernel
    qemu-img convert -f raw -O qcow2 /build/disk.raw /build/artifacts/disk.qcow2
    rm -f /build/disk.raw

    vmlinuz="$(tar -tf /build/rootfs.tar | grep "^boot/vmlinuz-" | sort -V | tail -n 1)"
    initrd="$(tar -tf /build/rootfs.tar | grep "^boot/initrd.img-" | sort -V | tail -n 1)"
    test -n "${vmlinuz}"
    test -n "${initrd}"
    rm -rf /build/kernel/root
    mkdir -p /build/kernel/root
    tar -xf /build/rootfs.tar -C /build/kernel/root "${vmlinuz}" "${initrd}"
    cp "/build/kernel/root/${vmlinuz}" /build/artifacts/vmlinuz
    cp "/build/kernel/root/${initrd}" /build/artifacts/initrd.img
  '

docker build \
  --platform "${PLATFORM}" \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${FINAL_IMAGE}" \
  "${DEPLOY_DIR}"

if [[ "${PUSH}" == "1" ]]; then
  docker push "${FINAL_IMAGE}"
fi

echo "${FINAL_IMAGE}"
