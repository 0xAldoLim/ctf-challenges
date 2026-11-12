#!/usr/bin/env bash
set -euo pipefail

CF_CPUS="${CF_CPUS:-2}"
CF_MEM_MB="${CF_MEM_MB:-2048}"
BOOT_TIMEOUT_S="${BOOT_TIMEOUT_S:-300}"
log() { echo "[cf_dev] $*" >&2; }

log "overlay over read-only base image"
mkdir -p /cf/overlay/upper /cf/overlay/work /cf/image
mount -t overlay overlay \
    -o "lowerdir=/cf/image-ro,upperdir=/cf/overlay/upper,workdir=/cf/overlay/work" /cf/image

log "host resources + operator (web console on :1080)"
/etc/init.d/cuttlefish-host-resources start || log "WARN: host-resources non-zero"
service cuttlefish-operator start || log "WARN: operator start non-zero"

export HOME=/cf/image
cd /cf/image
log "cvd create x2 (cpus=${CF_CPUS} mem=${CF_MEM_MB}MB each, vmm=qemu_cli) — adb 6520 + 6521"
cvd create \
    --num_instances=2 --base_instance_num=1 \
    --host_path=/cf/image --product_path=/cf/image \
    -cpus="${CF_CPUS}" -memory_mb="${CF_MEM_MB}" \
    -report_anonymous_usage_stats=n \
    -kernel_path=/cf/bzImage \
    --vm_manager=qemu_cli \
    --start_webrtc=true

deadline=$(( $(date +%s) + BOOT_TIMEOUT_S ))
for p in 6520 6521; do
    log "waiting up to ${BOOT_TIMEOUT_S}s for boot_completed on :${p}"
    booted=0
    while [ "$(date +%s)" -lt "${deadline}" ]; do
        adb connect "127.0.0.1:${p}" >/dev/null 2>&1 || true
        if [ "$(adb -s "127.0.0.1:${p}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
            booted=1; break
        fi
        sleep 3
    done
    [ "${booted}" = "1" ] && log "device :${p} booted" || log "WARN: :${p} not booted in time"
done

log "ready -> console http://localhost:1080 | adb 127.0.0.1:6520 (attacker) / :6521 (victim)"
cleanup() { cvd reset -y >/dev/null 2>&1 || true; exit 0; }
trap cleanup TERM INT
sleep infinity &
wait $!
