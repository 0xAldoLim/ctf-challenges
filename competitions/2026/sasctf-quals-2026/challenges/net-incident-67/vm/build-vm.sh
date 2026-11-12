#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../" && pwd)"
IMAGE_DIR="$ROOT_DIR/server/prebuilt-images"
IMAGE_TAR="$IMAGE_DIR/images.tar"

cleanup() {
    rm -rf "$IMAGE_DIR"
}
trap cleanup EXIT

mkdir -p "$IMAGE_DIR"

echo "Prebuilding challenge service images..."
export FLAG=SAS{temp_flag}
docker compose -f "$ROOT_DIR/server/challenge-compose.yml" build

echo "Saving prebuilt images..."
docker save -o "$IMAGE_TAR" \
    net-incident-67/frr-router:latest \
    net-incident-67/rpki-validator:latest \
    net-incident-67/dns-server:latest \
    net-incident-67/wallet-web:latest \
    net-incident-67/victim-bot:latest \
    net-incident-67/player-tools:latest

cd "$SCRIPT_DIR"
echo "Building VM image..."
docker build -t net-incident-67-vm -f Dockerfile ../
echo "Done. Run with: cd ../server && docker compose up -d"
