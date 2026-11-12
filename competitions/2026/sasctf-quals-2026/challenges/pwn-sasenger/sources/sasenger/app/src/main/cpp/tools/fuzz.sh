#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
CPP=..

CXX=${CXX:-clang++}
OUT=/tmp/fuzz_message
CORPUS=/tmp/smc_corpus
SAN="address,undefined,fuzzer"

GV=$(g++ -dumpversion | cut -d. -f1)
ARCH=$(uname -m)
CXXINC=""
for d in "/usr/include/c++/$GV" "/usr/include/$ARCH-linux-gnu/c++/$GV"; do
    [ -d "$d" ] && CXXINC="$CXXINC -isystem $d"
done
LIBDIR=/tmp/fuzzlib
mkdir -p "$LIBDIR"
so="/usr/lib/$ARCH-linux-gnu/libstdc++.so.6"
[ -e "$so" ] || so=$(ls -U /usr/lib/*/libstdc++.so.6 2>/dev/null | head -1)
[ -n "$so" ] && ln -sf "$so" "$LIBDIR/libstdc++.so"

GUARD="-DSASMEDIA_FUZZ"
MODE="neutralized (hunting UNINTENDED bugs)"
ARGS=("$@")
if [ "${1:-}" = "--reach" ]; then
    GUARD=""; MODE="REACH check (intended bug LIVE — expect a fast crash)"
    ARGS=(-runs=2000000)
fi

echo "[fuzz] building: $MODE"
"$CXX" -g -O1 -std=c++17 -fsanitize=$SAN $GUARD $CXXINC -I"$CPP" \
    "$CPP/message.cpp" fuzz_message.cpp -L"$LIBDIR" -o "$OUT"

mkdir -p "$CORPUS"
python3 - "$CORPUS" <<'PY'
import struct, sys, os
d = sys.argv[1]
def hdr(n): return b"SMC1" + bytes([1, 0]) + struct.pack("<H", n)
def text(t): x=t.encode(); return bytes([1])+struct.pack("<I",len(x))+x
def image(w,h): px=b"\x80\x40\x20\xff"*(w*h); return bytes([2])+struct.pack("<HHII",w,h,w*4,len(px))+px
def sticker(i,c): return bytes([3])+struct.pack("<HH",i,len(c))+b"".join(struct.pack("<I",x) for x in c)
def reply(t): x=t.encode(); return bytes([4])+struct.pack("<I",len(x))+x
def w(name, *parts): open(os.path.join(d,name),"wb").write(hdr(len(parts))+b"".join(parts))
w("text.smc", text("hello"))
w("image.smc", image(8,6))
w("sticker.smc", sticker(1,[0xFFFF7043,0xFFFFCA28]))
w("multi.smc", text("two photos"), image(8,6), image(6,8))
w("reply.smc", reply("orig"), text("re"))
print("[fuzz] wrote %d seeds to %s" % (len(os.listdir(d)), d))
PY

echo "[fuzz] $OUT  corpus=$CORPUS"
if [ ${#ARGS[@]} -eq 0 ]; then ARGS=(-max_total_time="${FUZZ_TIME:-60}"); fi
exec "$OUT" "$CORPUS" "${ARGS[@]}"
