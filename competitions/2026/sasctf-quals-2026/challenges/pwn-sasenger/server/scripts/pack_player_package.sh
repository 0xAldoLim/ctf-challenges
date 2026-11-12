#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$(cd "$HERE/.." && pwd)"
STATIC="$TASK/static"
NAME="sasenger-player"
OUT="${OUT:-$TASK/$NAME.tar.gz}"

log() { echo "[pack] $*"; }
fail() { echo "[pack] ERROR: $*" >&2; exit 1; }

need() { [ -e "$1" ] || fail "missing $2 (symlink target $1 does not exist) — build it first"; }
need "$STATIC/app-release.apk"        "release APK (run gradlew assembleRelease)"
need "$STATIC/bzImage"                "custom kernel bzImage (sources/cf_kernel)"
need "$STATIC/docker/relay/Dockerfile" "relay source"
need "$STATIC/docker/cf-host/Dockerfile" "cf-host Dockerfile"
need "$STATIC/scripts/cf_dev.sh"      "cf_dev.sh"

command -v rsync >/dev/null || fail "rsync is required"

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
DEST="$STAGE/$NAME"
log "staging dereferenced tree -> $DEST"
rsync -aL \
    --exclude '/images/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.gitignore' \
    "$STATIC/" "$DEST/"

[ -z "$(find "$DEST" -type l)" ] || fail "staged tree still contains symlinks"
[ -s "$DEST/app-release.apk" ]        || fail "app-release.apk did not materialize"
[ -s "$DEST/bzImage" ]                || fail "bzImage did not materialize"

log "creating $OUT"
tar -czf "$OUT" -C "$STAGE" "$NAME"

log "done: $OUT"
du -h "$OUT" | cut -f1 | xargs -I{} echo "[pack] size: {}"
echo "[pack] contents:"
tar -tzf "$OUT" | sed 's,^,  ,'
