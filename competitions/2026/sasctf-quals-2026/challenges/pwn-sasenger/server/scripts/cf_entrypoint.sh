#!/usr/bin/env bash
set -euo pipefail

CF_CPUS="${CF_CPUS}"
CF_MEM_MB="${CF_MEM_MB}"
BOOT_TIMEOUT_S="${BOOT_TIMEOUT_S}"
CF_BASE_INSTANCE_NUM="${CF_BASE_INSTANCE_NUM}"
ADB_INTERNAL_PORT=$(( 6520 + CF_BASE_INSTANCE_NUM - 1 ))
CF_WEBRTC="${CF_WEBRTC}"

log() { echo "[cf_entrypoint] $*" >&2; }

log "mounting overlay over read-only base image"
mkdir -p /cf/overlay/upper /cf/overlay/work /cf/image
mount -t overlay overlay \
    -o "lowerdir=/cf/image-ro,upperdir=/cf/overlay/upper,workdir=/cf/overlay/work" \
    /cf/image

log "starting cuttlefish-host-resources"
/etc/init.d/cuttlefish-host-resources start || log "WARN: host-resources start returned non-zero"

export HOME=/cf/image
cd /cf/image
WEBRTC_ARG="--start_webrtc=false"
if [ "${CF_WEBRTC}" = "1" ]; then
    log "starting cuttlefish-operator (WebRTC console on :1080)"
    service cuttlefish-operator start || log "WARN: operator start returned non-zero"
    WEBRTC_ARG="--start_webrtc=true"
fi

log "cvd create (instance=${CF_BASE_INSTANCE_NUM} adb=${ADB_INTERNAL_PORT} webrtc=${CF_WEBRTC} cpus=${CF_CPUS} mem=${CF_MEM_MB}MB, vmm=qemu_cli)"
cvd create \
    --num_instances=1 --base_instance_num="${CF_BASE_INSTANCE_NUM}" \
    --host_path=/cf/image --product_path=/cf/image \
    -cpus="${CF_CPUS}" -memory_mb="${CF_MEM_MB}" \
    -report_anonymous_usage_stats=n \
    -kernel_path=/cf/bzImage \
    --vm_manager=qemu_cli \
    "${WEBRTC_ARG}"

SERIAL="127.0.0.1:${ADB_INTERNAL_PORT}"
adb connect "${SERIAL}" >/dev/null 2>&1 || true
log "waiting up to ${BOOT_TIMEOUT_S}s for boot_completed"
deadline=$(( $(date +%s) + BOOT_TIMEOUT_S ))
booted=0
while [ "$(date +%s)" -lt "${deadline}" ]; do
    adb connect "${SERIAL}" >/dev/null 2>&1 || true
    if [ "$(adb -s "${SERIAL}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
        booted=1
        break
    fi
    sleep 3
done
if [ "${booted}" != "1" ]; then
    log "ERROR: device did not boot within ${BOOT_TIMEOUT_S}s"
    cvd fleet >&2 || true
    exit 1
fi
log "device booted"

cleanup() {
    log "stopping"
    cvd reset -y >/dev/null 2>&1 || true
    exit 0
}
trap cleanup TERM INT
log "ready"
sleep infinity &
wait $!
