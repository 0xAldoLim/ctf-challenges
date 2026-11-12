#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
APK="${APK:-$HERE/../sources/sasenger/app/build/outputs/apk/release/app-release.apk}"
KERNEL="${KERNEL:-$HERE/../sources/cf_kernel/bzImage}"
RELAY_GUEST="http://${RELAY_GUEST_HOST:-192.168.97.1}:8080"
PKG="com.sasctf.sasenger"
CF=sas-dev-cf
RELAY=sas-dev-relay
A_PORT=6520
V_PORT=6521
A=/usr/lib/cuttlefish-common/bin/adb
SYSROOT="${SYSROOT:-/tmp/sas-sysroot}"
SCRCPY_VERSION="${SCRCPY_VERSION:-v4.0}"
SCRCPY_CACHE="${SCRCPY_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/sasenger-scrcpy}"
SCRCPY_ADB_PORT="${SCRCPY_ADB_PORT:-5038}"

adbx() { docker exec "$CF" "$A" "$@"; }
adbi() { docker exec -it "$CF" "$A" "$@"; }
port_of() { case "$1" in attacker) echo "$A_PORT";; victim) echo "$V_PORT";; *) echo "$1";; esac; }

require_up() { docker ps --format '{{.Names}}' | grep -qx "$CF" || { echo "dev devices not up — run: $0 up"; exit 1; }; }

reg() {
    python3 - "$1" <<'PY'
import json,sys,urllib.request as u
name=sys.argv[1]
pw="Dev_"+name+"_9xQ!"
def call(p,b):
    rq=u.Request("http://127.0.0.1:8080"+p,data=json.dumps(b).encode(),headers={"Content-Type":"application/json"})
    try:
        with u.urlopen(rq,timeout=5) as r: return json.loads(r.read())
    except u.HTTPError as e:
        return None
j=call("/v1/register",{"username":name,"password":pw}) or call("/v1/login",{"username":name,"password":pw})
print(j["token"],j["account_id"])
PY
}

login() {
    adbx -s "127.0.0.1:$1" shell am start -n "$PKG/.ui.MainActivity" \
        --es relay "$RELAY_GUEST" --es username "$2" --es token "$3" --es account_id "$4" >/dev/null
}

up() {
    command -v docker >/dev/null || { echo "docker required"; exit 1; }
    [ -f "$APK" ] || { echo "APK not found: $APK  (build sources/sasenger first)"; exit 1; }
    [ -f "$KERNEL" ] || { echo "kernel not found: $KERNEL  (sources/cf_kernel/bzImage)"; exit 1; }
    docker image inspect cf-host:sas >/dev/null 2>&1 || { echo "image cf-host:sas missing (build cuttlefish/)"; exit 1; }
    docker image inspect sasenger-relay >/dev/null 2>&1 || docker build -t sasenger-relay "$HERE/relay"

    echo "[dev] starting relay on :8080"
    docker rm -f "$RELAY" >/dev/null 2>&1 || true
    docker run -d --rm --name "$RELAY" -p 8080:8080 \
        -e RELAY_ADMIN_KEY=dev -e RELAY_POLL_WAIT_S=25 \
        -e RELAY_MAX_EVENTS=512 -e RELAY_MAX_PAYLOAD_B64=524288 \
        -e LOG_LEVEL=info sasenger-relay >/dev/null

    echo "[dev] booting 2 devices (~1-2 min); watch: docker logs -f $CF"
    docker rm -f "$CF" >/dev/null 2>&1 || true
    docker run -d --rm --name "$CF" --network host --privileged --device /dev/kvm \
        -v "$HERE/images:/cf/image-ro:ro" \
        -v "$HERE/scripts/cf_dev.sh:/cf/cf_dev.sh:ro" \
        -v /cf/overlay \
        -v "$APK:/cf/app.apk:ro" \
        -v "$KERNEL:/cf/bzImage:ro" \
        -e CF_CPUS="${CF_CPUS:-2}" -e CF_MEM_MB="${CF_MEM_MB:-2048}" \
        cf-host:sas /cf/cf_dev.sh >/dev/null

    for p in $A_PORT $V_PORT; do
        printf '[dev] waiting for boot_completed on :%s ' "$p"
        for _ in $(seq 1 120); do
            adbx connect "127.0.0.1:$p" >/dev/null 2>&1 || true
            [ "$(adbx -s "127.0.0.1:$p" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
            printf '.'; sleep 3
        done; echo " up"
    done

    echo "[dev] installing app on both devices"
    for p in $A_PORT $V_PORT; do adbx -s "127.0.0.1:$p" install -r /cf/app.apk >/dev/null; done

    AMC='service_restart_duration=0,service_reset_run_duration=0,service_min_restart_time_between=0,service_crash_restart_duration=0,service_crash_max_retry=1000000000'
    for p in $A_PORT $V_PORT; do
        adbx -s "127.0.0.1:$p" shell settings put global activity_manager_constants "$AMC"
    done

    echo "[dev] registering accounts + auto-login"
    read -r ATOK AACC < <(reg attacker)
    read -r VTOK VACC < <(reg victim)
    login "$A_PORT" attacker "$ATOK" "$AACC"
    login "$V_PORT" victim   "$VTOK" "$VACC"

    cat <<EOF

[dev] READY
  console : http://localhost:1080   (both devices; local browser)
  attacker: adb 127.0.0.1:$A_PORT   account @attacker
  victim  : adb 127.0.0.1:$V_PORT   account @victim   (polling -> auto-decodes inbound)
  relay   : http://127.0.0.1:8080 (host)  |  guest uses $RELAY_GUEST

Next:
  $0 send "hello" ./payload.bin   # attacker -> victim; victim processes it 0-click
  $0 ui                           # scrcpy window(s) — no arg = both (vs the WebRTC console)
  $0 gdb victim                   # gdbserver attach to the victim's native code
  $0 logcat victim                # watch the app logs
EOF
}

send() {
    require_up
    local text="${1:-debug-probe}" file="${2:-}" b64="" name=""
    if [ -n "$file" ]; then
        [ -f "$file" ] || { echo "attachment not found: $file"; exit 1; }
        b64=$(base64 -w0 "$file"); name=$(basename "$file")
    fi
    python3 - "$text" "$b64" "$name" <<'PY'
import json,sys,urllib.request as u
text,b64,name=sys.argv[1],sys.argv[2],(sys.argv[3] or "attachment.bin")
tok=json.load(u.urlopen(u.Request("http://127.0.0.1:8080/v1/login",
    data=json.dumps({"username":"attacker","password":"Dev_attacker_9xQ!"}).encode(),
    headers={"Content-Type":"application/json"})))["token"]
atts=[{"name":name,"mime":"application/octet-stream","data_b64":b64}] if b64 else []
r=json.load(u.urlopen(u.Request("http://127.0.0.1:8080/v1/send",
    data=json.dumps({"to":"victim","body":text,"attachments":atts}).encode(),
    headers={"Content-Type":"application/json","Authorization":"Bearer "+tok})))
print("[dev] sent", r.get("message_id"), ("with attachment "+name) if b64 else "(text only)")
PY
}

shell_() { require_up; adbi -s "127.0.0.1:$(port_of "${1:-victim}")" shell; }
logcat() { require_up; adbx -s "127.0.0.1:$(port_of "${1:-victim}")" logcat -s Sasenger:V; }

build_sysroot() {
    require_up
    local p; p="$(port_of "${1:-victim}")"; local force="${2:-}"
    if [ -e "$SYSROOT/system/bin/app_process64" ] && [ "$force" != force ]; then
        return 0
    fi
    echo "[dev] building gdb sysroot cache at $SYSROOT (one-time, ~1-2 min)…"
    adbx connect "127.0.0.1:$p" >/dev/null 2>&1 || true
    docker exec "$CF" sh -c 'rm -rf /tmp/sysroot 2>/dev/null; mkdir -p /tmp/sysroot/system' || true
    adbx -s "127.0.0.1:$p" pull /system/bin   /tmp/sysroot/system/ >/dev/null 2>&1 || true
    adbx -s "127.0.0.1:$p" pull /system/lib64 /tmp/sysroot/system/ >/dev/null 2>&1 || true
    for d in $(adbx -s "127.0.0.1:$p" shell 'ls -d /apex/*/lib64 2>/dev/null' | tr -d '\r' | grep -v '@'); do
        local mod; mod=$(echo "$d" | cut -d/ -f3)
        docker exec "$CF" mkdir -p "/tmp/sysroot/apex/$mod"
        adbx -s "127.0.0.1:$p" pull "$d" "/tmp/sysroot/apex/$mod/" >/dev/null 2>&1 || true
    done
    mkdir -p "$SYSROOT"
    docker cp "$CF:/tmp/sysroot/system" "$SYSROOT/" >/dev/null
    docker cp "$CF:/tmp/sysroot/apex"   "$SYSROOT/" >/dev/null 2>&1 || echo "[dev] note: some /apex entries skipped (symlinks) — harmless"
    docker exec "$CF" rm -rf /tmp/sysroot >/dev/null 2>&1 || true
    [ -e "$SYSROOT/system/bin/app_process64" ] || { echo "[dev] ERROR: sysroot build failed (app_process64 missing)"; return 1; }
    echo "[dev] sysroot ready ($SYSROOT)"
}

gdb_() {
    require_up
    local who="${1:-victim}"; local p; p="$(port_of "$who")"; local dbg="${DBG_PORT:-5039}"
    adbx -s "127.0.0.1:$p" connect "127.0.0.1:$p" >/dev/null 2>&1 || true
    adbx -s "127.0.0.1:$p" root >/dev/null 2>&1 || true; sleep 2
    adbx -s "127.0.0.1:$p" connect "127.0.0.1:$p" >/dev/null 2>&1 || true
    local pid; pid=$(adbx -s "127.0.0.1:$p" shell pidof "$PKG" | tr -d '\r')
    [ -n "$pid" ] || { echo "app not running on $who — '$0 send' or open it first"; exit 1; }

    local gs="${GDBSERVER:-}" on_device=0
    adbx -s "127.0.0.1:$p" shell 'ls /data/local/tmp/gdbserver' >/dev/null 2>&1 && on_device=1
    if [ "$on_device" = 0 ]; then
        [ -n "$gs" ] || { [ -f /tmp/sas-gdbserver ] && gs=/tmp/sas-gdbserver; }
        [ -n "$gs" ] || gs=$(find "$HOME/Android/Sdk/ndk" -path '*prebuilt/android-x86_64/gdbserver/gdbserver' 2>/dev/null | head -1)
        [ -n "$gs" ] || { echo "no gdbserver. Build one matched to your gdb: scripts/build_gdbserver.sh (-> /tmp/sas-gdbserver), or set GDBSERVER=/path."; exit 1; }
        echo "[dev] pushing gdbserver ($gs)"
        docker cp "$gs" "$CF:/tmp/gdbserver"
        adbx -s "127.0.0.1:$p" push /tmp/gdbserver /data/local/tmp/gdbserver >/dev/null
        adbx -s "127.0.0.1:$p" shell chmod 755 /data/local/tmp/gdbserver
    fi

    build_sysroot "$who"

    adbx -s "127.0.0.1:$p" forward "tcp:$dbg" "tcp:$dbg" >/dev/null
    echo "[dev] attaching gdbserver to pid $pid on $who (port $dbg)"
    adbx -s "127.0.0.1:$p" shell "nohup /data/local/tmp/gdbserver --attach :$dbg $pid >/dev/null 2>&1 &" >/dev/null 2>&1 || true
    sleep 1

    local symso symdir=""
    symso=$(find "$HERE/../sources/sasenger/app/build/intermediates/cxx" -path '*/obj/x86_64/libsasmedia.so' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
    [ -n "$symso" ] && symdir=$(dirname "$symso")

    local gi="/tmp/sas-gdb-$who.gdb"
    {
      echo "set debuginfod enabled off"
      echo "set auto-solib-add off"
      echo "set emulate off"
      [ -n "$symdir" ] && echo "set solib-search-path $symdir"
      echo "set sysroot $SYSROOT"
      echo "file $SYSROOT/system/bin/app_process64"
      echo "target remote 127.0.0.1:$dbg"
      echo "set scheduler-locking step"
      echo "handle SIG33 SIGPWR nostop noprint pass"
      [ -n "$symdir" ] && echo "sharedlibrary sasmedia"
    } > "$gi"
    cat <<EOF
[dev] gdbserver attached to pid $pid ($who). Connect (fast — local sysroot, no
auto symbol-loading of all the ART libs):
  pwndbg -x $gi        # (or: gdb -x $gi)
$([ -n "$symdir" ] && echo "Decoder symbols auto-loaded from $symso (if libsasmedia is mapped;" \
   && echo "re-run 'sharedlibrary sasmedia' after the app loads it on first decode)." \
   || echo "Build the app to get unstripped libsasmedia.so symbols, then 'sharedlibrary sasmedia'.")
  (pwndbg) sharedlibrary libc    # optionally, libc/heap symbols
EOF
}

ensure_scrcpy() {
    case "$(uname -m)" in
        x86_64) ;;
        *) echo "scrcpy: no Linux prebuilt for $(uname -m) (only linux-x86_64 is published); use snap/apt or build from source"; exit 1 ;;
    esac
    SCRCPY_DIR="$SCRCPY_CACHE/scrcpy-linux-x86_64-$SCRCPY_VERSION"
    if [ ! -x "$SCRCPY_DIR/scrcpy" ]; then
        command -v curl >/dev/null || { echo "curl required to fetch scrcpy"; exit 1; }
        local url="https://github.com/Genymobile/scrcpy/releases/download/$SCRCPY_VERSION/scrcpy-linux-x86_64-$SCRCPY_VERSION.tar.gz"
        echo "[dev] fetching scrcpy $SCRCPY_VERSION (official prebuilt) -> $SCRCPY_CACHE"
        mkdir -p "$SCRCPY_CACHE"
        curl -fL --retry 3 -o "$SCRCPY_CACHE/scrcpy.tgz" "$url" || { echo "scrcpy download failed: $url"; exit 1; }
        tar xzf "$SCRCPY_CACHE/scrcpy.tgz" -C "$SCRCPY_CACHE"
        rm -f "$SCRCPY_CACHE/scrcpy.tgz"
    fi
    [ -x "$SCRCPY_DIR/scrcpy" ] || { echo "scrcpy missing after extract: $SCRCPY_DIR"; exit 1; }
}

_scrcpy_one() {
    local who="$1"; shift; local p; p="$(port_of "$who")"
    "$SCRCPY_ADB" connect "127.0.0.1:$p" >/dev/null 2>&1 || true
    echo "[dev] scrcpy $SCRCPY_VERSION -> $who (127.0.0.1:$p) | adb server :$SCRCPY_ADB_PORT"
    "$SCRCPY_DIR/scrcpy" -s "127.0.0.1:$p" --window-title "sasenger:$who" "$@"
}

ui() {
    require_up
    [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || { echo "no DISPLAY/WAYLAND_DISPLAY set — scrcpy needs a desktop session (or 'ssh -X')"; exit 1; }
    ensure_scrcpy
    export ANDROID_ADB_SERVER_PORT="$SCRCPY_ADB_PORT"
    export SCRCPY_ADB="$SCRCPY_DIR/adb"
    export SCRCPY_SERVER_PATH="$SCRCPY_DIR/scrcpy-server"
    if [ $# -eq 0 ]; then
        echo "[dev] opening both devices (close a window to end it; Ctrl-C ends both)"
        _scrcpy_one attacker & local a=$!
        _scrcpy_one victim   & local v=$!
        wait "$a" "$v" || true
    else
        _scrcpy_one "$@"
    fi
}

down() {
    docker rm -f "$CF" "$RELAY" >/dev/null 2>&1 || true
    echo "[dev] torn down"
}

case "${1:-}" in
    up)     up ;;
    send)   send "${2:-}" ;;
    ui|scrcpy) shift; ui "$@" ;;
    shell)  shell_ "${2:-victim}" ;;
    logcat) logcat "${2:-victim}" ;;
    gdb)    gdb_ "${2:-victim}" ;;
    sysroot) build_sysroot "${2:-victim}" force ;;
    down)   down ;;
    *) echo "usage: $0 {up|send [text] [file]|ui [victim|attacker]|shell [attacker|victim]|logcat [..]|gdb [..]|sysroot|down}"; exit 1 ;;
esac
