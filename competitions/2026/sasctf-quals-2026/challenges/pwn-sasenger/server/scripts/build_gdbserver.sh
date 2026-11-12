#!/usr/bin/env bash
set -euo pipefail

VER="${GDB_VERSION:-17.1}"
OUT="${OUT:-/tmp/sas-gdbserver}"
SRC="/tmp/gdb-${VER}-src"
BLD="/tmp/gdb-${VER}-build"

cd /tmp
[ -f "gdb-${VER}.tar.xz" ] || curl -fL -o "gdb-${VER}.tar.xz" "https://ftp.gnu.org/gnu/gdb/gdb-${VER}.tar.xz"
rm -rf "$SRC" "$BLD"; mkdir -p "$SRC" "$BLD"
tar xf "gdb-${VER}.tar.xz" -C "$SRC" --strip-components=1

cd "$BLD"
"$SRC/configure" --disable-gdb --disable-binutils --disable-ld --disable-gas \
    --disable-sim --disable-gprof --enable-gdbserver --disable-inprocess-agent \
    LDFLAGS="-static"
make -j"$(nproc)" all-gdbserver

cp "$BLD/gdbserver/gdbserver" "$OUT"
echo "[build_gdbserver] $OUT"
file "$OUT"
