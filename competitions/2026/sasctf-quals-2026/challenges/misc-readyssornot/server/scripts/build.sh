#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
docker build \
  --platform linux/amd64 \
  --build-arg "BASE_IMAGE=${BASE_IMAGE:-ubuntu:24.04}" \
  --build-arg "VALKEY_VERSION=${VALKEY_VERSION:-7.2.11}" \
  --build-arg "VALKEY_PLATFORM=${VALKEY_PLATFORM:-noble-x86_64}" \
  --build-arg "VALKEY_SHA256=${VALKEY_SHA256:-0e26bf927d7c4c10f3f5afdf258cd1fea83bfaa56f598d45b5336d0a96bae94b}" \
  -t "${IMAGE_NAME:-valkey-systemd-node:local}" .
