#!/usr/bin/env bash
set -euo pipefail

CF_CPUS="${CF_CPUS:-4}"
CF_MEM_MB="${CF_MEM_MB:-4096}"
BOOT_TIMEOUT_S="${BOOT_TIMEOUT_S:-300}"
log() { echo "[cf_interactive] $*" >&2; }

log "overlay over read-only base image"
mkdir -p /cf/overlay/upper /cf/overlay/work /cf/image
mount -t overlay overlay \
    -o "lowerdir=/cf/image-ro,upperdir=/cf/overlay/upper,workdir=/cf/overlay/work" /cf/image

log "host resources + operator (web console on :1080)"
/etc/init.d/cuttlefish-host-resources start || log "WARN: host-resources non-zero"
service cuttlefish-operator start || log "WARN: operator start non-zero"

export HOME=/cf/image
cd /cf/image
KERNEL_ARG=""; [ -f /cf/bzImage ] && KERNEL_ARG="-kernel_path=/cf/bzImage"
log "cvd create with WebRTC (cpus=${CF_CPUS} mem=${CF_MEM_MB}MB) kernel='${KERNEL_ARG}'"
cvd create \
    --num_instances=1 --base_instance_num=1 \
    --host_path=/cf/image --product_path=/cf/image \
    -cpus="${CF_CPUS}" -memory_mb="${CF_MEM_MB}" \
    -report_anonymous_usage_stats=n \
    ${KERNEL_ARG} \
    --start_webrtc=true

SERIAL="127.0.0.1:6520"
adb connect "${SERIAL}" >/dev/null 2>&1 || true
deadline=$(( $(date +%s) + BOOT_TIMEOUT_S )); booted=0
while [ "$(date +%s)" -lt "${deadline}" ]; do
    adb connect "${SERIAL}" >/dev/null 2>&1 || true
    if [ "$(adb -s "${SERIAL}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
        booted=1; break
    fi
    sleep 3
done
[ "${booted}" = "1" ] || { log "ERROR: boot timed out"; cvd fleet >&2 || true; exit 1; }

log "ready -> open the WebRTC console at  http://localhost:1080"
log "adb is also up inside this container: adb -s ${SERIAL} shell"
cleanup() { cvd reset -y >/dev/null 2>&1 || true; exit 0; }
trap cleanup TERM INT
sleep infinity &
wait
