#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
NAME="cf-interactive"

docker rm -f "${NAME}" >/dev/null 2>&1 || true
docker run -d --rm --name "${NAME}" \
    --network host \
    --privileged --device /dev/kvm \
    -v "${HERE}/images:/cf/image-ro:ro" \
    -v "${HERE}/scripts/cf_interactive.sh:/cf/cf_interactive.sh:ro" \
    -v "${HERE}/../sources/cf_kernel/bzImage:/cf/bzImage:ro" \
    -v /cf/overlay \
    -e CF_CPUS="${CF_CPUS:-4}" -e CF_MEM_MB="${CF_MEM_MB:-4096}" \
    cf-host:sas /cf/cf_interactive.sh >/dev/null

echo "[interactive] booting '${NAME}' (~1 min)…"
echo "[interactive] web console: http://localhost:1080   (open in a local browser)"
echo "[interactive] watch boot:  docker logs -f ${NAME}"
echo "[interactive] adb shell:   docker exec -it ${NAME} adb -s 127.0.0.1:6520 shell"
echo "[interactive] stop:        docker rm -f ${NAME}"
