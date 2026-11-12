#!/bin/sh
set -e

echo "[init] Waiting for Docker daemon..."
for i in $(seq 1 90); do
    docker info >/dev/null 2>&1 && break
    sleep 1
done

if ! docker info >/dev/null 2>&1; then
    echo "[init] ERROR: Docker daemon did not start"
    exit 1
fi

IMAGE_BUNDLE=/opt/task/prebuilt-images/images.tar
COMPOSE_LOG=/tmp/task-compose.log
FLAG_FWCFG=/sys/firmware/qemu_fw_cfg/by_name/opt/net-incident-67/flag/raw

if [ -r "$FLAG_FWCFG" ]; then
    FLAG="$(cat "$FLAG_FWCFG")"
    export FLAG
fi

if [ -z "${FLAG:-}" ]; then
    echo "[init] ERROR: FLAG environment variable was not passed into the VM"
    exit 1
fi

if [ ! -f "$IMAGE_BUNDLE" ]; then
    echo "[init] ERROR: missing prebuilt challenge images: $IMAGE_BUNDLE"
    echo "[init] Rebuild the VM image with vm/build-vm.sh so Docker images are bundled."
    exit 1
fi

echo "[init] Loading prebuilt challenge images..."
if ! docker load -i "$IMAGE_BUNDLE" >/tmp/task-docker-load.log 2>&1; then
    echo "[init] ERROR: failed to load prebuilt challenge images"
    tail -50 /tmp/task-docker-load.log
    exit 1
fi

echo "[init] Docker is ready, starting challenge..."
cd /opt/task
if ! docker compose -f challenge-compose.yml up -d >"$COMPOSE_LOG" 2>&1; then
    echo "[init] ERROR: docker compose up failed"
    tail -80 "$COMPOSE_LOG"
    exit 1
fi
tail -20 "$COMPOSE_LOG"
echo "[init] Services started:"
docker compose -f challenge-compose.yml ps
