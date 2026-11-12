#!/usr/bin/env bash
# Compress the freshly-built static QEMU binary into this build context so it can
# be committed to git (~13 MB vs ~54 MB) and decompressed by the Dockerfile.
# Re-run after rebuilding QEMU.
set -euo pipefail

SRC="${1:-/home/madrat/projects/qemu-sas-26/build/qemu-system-riscv64}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/qemu-system-riscv64.7z"

if [ ! -f "$SRC" ]; then
    echo "QEMU binary not found at: $SRC" >&2
    echo "build it first (see ../BUILDING.md) or pass the path as \$1" >&2
    exit 1
fi

# The archive must store the member as exactly "qemu-system-riscv64" (the
# Dockerfile extracts it by that name), so compress from the source directory.
rm -f "$OUT"
( cd "$(dirname "$SRC")" && 7z a -t7z -mx=9 "$OUT" "$(basename "$SRC")" >/dev/null )
echo "compressed $(du -h "$SRC" | cut -f1) -> $(du -h "$OUT" | cut -f1)  ($OUT)"
