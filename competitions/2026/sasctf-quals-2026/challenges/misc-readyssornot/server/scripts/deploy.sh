#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  printf 'usage: %s user@host [remote_dir]\n' "$0" >&2
  exit 2
fi

target="$1"
remote_dir="${2:-~/service_image}"
root_dir="$(cd "$(dirname "$0")/.." && pwd)"
archive="$(mktemp -t service_image.XXXXXX.tar.gz)"

cleanup() {
  rm -f "$archive"
}
trap cleanup EXIT

COPYFILE_DISABLE=1 tar -C "$root_dir" \
  --no-xattrs \
  --no-acls \
  --exclude='.DS_Store' \
  --exclude='**/.DS_Store' \
  --exclude='docker-compose.yml' \
  --exclude='src/agent/agent' \
  --exclude='src/agent/rev_agent' \
  --exclude='src/agent/agent.o' \
  -czf "$archive" .

ssh "$target" "rm -rf $remote_dir && mkdir -p $remote_dir"
scp "$archive" "$target:$remote_dir/service_image.tar.gz"
ssh "$target" "cd $remote_dir && tar --no-same-owner -xzf service_image.tar.gz && rm service_image.tar.gz && chmod +x start.sh scripts/*.sh && ./start.sh"
