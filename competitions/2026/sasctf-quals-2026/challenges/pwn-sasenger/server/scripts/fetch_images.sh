#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
IMAGES_DIR="${HERE}/images"
BUILD="${CF_BUILD:-15357239}"
TARGET="${CF_TARGET:-aosp_cf_x86_64_only_phone-userdebug}"
CF_IMAGE="${CF_IMAGE:-cf-host:sas}"

mkdir -p "${IMAGES_DIR}"
echo "Fetching ${BUILD}/${TARGET} -> ${IMAGES_DIR}"
docker run --rm \
    -v "${IMAGES_DIR}:/cf/images" \
    "${CF_IMAGE}" \
    cvd fetch --target_directory=/cf/images --default_build="${BUILD}/${TARGET}"
echo "Done. Image tree in ${IMAGES_DIR}"
