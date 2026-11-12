#!/usr/bin/env bash
set -euo pipefail

A=/usr/lib/cuttlefish-common/bin/adb
ADB_PORT="${ADB_PORT}"
SERIAL="127.0.0.1:${ADB_PORT}"

$A connect "$SERIAL" >/dev/null 2>&1 || true

GW=""
for _ in $(seq 1 30); do
    GW="$($A -s "$SERIAL" shell 'ip route show table all' 2>/dev/null | awk '/^default via/{print $3; exit}' | tr -d '\r' || true)"
    [ -n "$GW" ] && break
    sleep 1
done
[ -n "$GW" ] || { echo "[provision] ERROR: no default gateway on the guest after 30s" >&2; exit 1; }
RELAY_APP_URL="${RELAY_APP_URL:-http://${GW}:8080}"

AMC='service_restart_duration=0,service_reset_run_duration=0,service_min_restart_time_between=0,service_crash_restart_duration=0,service_crash_max_retry=1000000000'
$A -s "$SERIAL" shell settings put global activity_manager_constants "$AMC"

$A -s "$SERIAL" install -r /cf/app.apk >/dev/null

$A -s "$SERIAL" shell am start -n com.sasctf.sasenger/.ui.MainActivity \
    --es relay "${RELAY_APP_URL}" \
    --es username "${VICTIM_USER}" \
    --es token "${VICTIM_TOKEN}" \
    --es account_id "${VICTIM_ACC}" >/dev/null
sleep 4

iptables  -I FORWARD 1 -j DROP
ip6tables -I FORWARD 1 -j DROP 2>/dev/null || true

echo "[provision] victim ${VICTIM_USER} provisioned (internet isolated)"
