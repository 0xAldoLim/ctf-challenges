#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

image="${IMAGE_NAME:-valkey-systemd-node:local}"
name="${CONTAINER_NAME:-valkey-systemd-node}"
redis_port="${REDIS_PORT:-6379}"
ssh_port="${SSH_PORT:-2222}"
base_image="${BASE_IMAGE:-ubuntu:24.04}"
valkey_version="${VALKEY_VERSION:-7.2.11}"
valkey_platform="${VALKEY_PLATFORM:-noble-x86_64}"
valkey_sha256="${VALKEY_SHA256:-0e26bf927d7c4c10f3f5afdf258cd1fea83bfaa56f598d45b5336d0a96bae94b}"

if [ "${NO_BUILD:-0}" != "1" ]; then
  docker build \
    --platform linux/amd64 \
    --build-arg "BASE_IMAGE=${base_image}" \
    --build-arg "VALKEY_VERSION=${valkey_version}" \
    --build-arg "VALKEY_PLATFORM=${valkey_platform}" \
    --build-arg "VALKEY_SHA256=${valkey_sha256}" \
    -t "${image}" .
fi

docker rm -f "${name}" >/dev/null 2>&1 || true

docker run -d \
  --name "${name}" \
  --hostname node \
  --platform linux/amd64 \
  --privileged \
  --cgroupns=host \
  --security-opt apparmor=unconfined \
  --tmpfs /run \
  --tmpfs /run/lock \
  --tmpfs /tmp:rw,exec,suid,nodev,mode=1777 \
  --volume /sys/fs/cgroup:/sys/fs/cgroup:rw \
  --add-host host.docker.internal:host-gateway \
  --publish "${redis_port}:6379" \
  --publish "${ssh_port}:22" \
  --stop-signal SIGRTMIN+3 \
  "${image}"

docker ps --filter "name=^/${name}$"
