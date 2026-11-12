#!/usr/bin/env python3
import argparse
import asyncio
import base64
import hashlib
import json
import sys
import threading
import urllib.error
import urllib.request

import websockets


def leading_zero_bits(digest: bytes) -> int:
    bits = 0
    for b in digest:
        if b == 0:
            bits += 8
            continue
        bits += 8 - b.bit_length()
        break
    return bits


def solve_pow(challenge: str, difficulty: int) -> str:
    nonce = 0
    while True:
        d = hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()
        if leading_zero_bits(d) >= difficulty:
            return str(nonce)
        nonce += 1


def get_json(url: str, data: bytes | None = None) -> dict:
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        return json.load(exc)


def _ws_url(base: str) -> str:
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/ws/run"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/ws/run"
    return base + "/ws/run"


async def _pump_stdin(ws) -> None:
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    def reader() -> None:
        try:
            while True:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                loop.call_soon_threadsafe(q.put_nowait, line)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=reader, daemon=True).start()
    while True:
        line = await q.get()
        if line is None:
            try:
                await ws.send(json.dumps({"type": "eof"}))
            except Exception:
                pass
            return
        try:
            await ws.send(line)
        except Exception:
            return


async def _pump_output(ws) -> int:
    while True:
        try:
            msg = await ws.recv()
        except websockets.ConnectionClosed:
            return 0
        if isinstance(msg, (bytes, bytearray)):
            sys.stdout.buffer.write(msg)
            sys.stdout.buffer.flush()
            continue
        obj = json.loads(msg)
        if obj.get("type") == "exit":
            return int(obj.get("code", 0) or 0)
        if obj.get("type") == "timeout":
            sys.stderr.write("\n[*] execution timed out\n")
            return 124


async def run_program(ws_url: str, handshake: dict) -> int:
    async with websockets.connect(ws_url, max_size=1 << 20) as ws:
        await ws.send(json.dumps(handshake))

        try:
            while True:
                msg = await ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    sys.stdout.buffer.write(msg)
                    sys.stdout.buffer.flush()
                    continue
                obj = json.loads(msg)
                kind = obj.get("type")
                if kind == "running":
                    break
                sys.stderr.write(json.dumps(obj) + "\n")
                return 1
        except websockets.ConnectionClosed as exc:
            code = getattr(exc, "code", None)
            if code is None and getattr(exc, "rcvd", None) is not None:
                code = exc.rcvd.code
            hint = " (program too large for the server)" if code == 1009 else ""
            sys.stderr.write(f"\n[!] connection closed before a verdict{hint}.\n")
            return 1

        in_task = asyncio.create_task(_pump_stdin(ws))
        try:
            return await _pump_output(ws)
        finally:
            in_task.cancel()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="service base URL, e.g. http://localhost:2048")
    ap.add_argument("program", help="path to the RV64 program image (.bin)")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    with open(args.program, "rb") as fh:
        raw = fh.read()

    try:
        limit = int(get_json(base + "/config").get("max_program_bytes", 128 * 1024))
    except Exception:
        limit = 128 * 1024
    if len(raw) > limit:
        sys.stderr.write(
            f"[!] program too large: {len(raw)} bytes exceeds limit {limit}\n"
        )
        return 1

    pw = get_json(base + "/pow")
    sys.stderr.write(f"[*] solving PoW (difficulty={pw['difficulty']})...\n")
    nonce = solve_pow(pw["challenge"], pw["difficulty"])

    program = base64.b64encode(raw).decode()

    handshake = {
        "program": program,
        "pow": {k: pw[k] for k in ("challenge", "exp", "difficulty", "sig")}
        | {"nonce": nonce},
    }
    return asyncio.run(run_program(_ws_url(base), handshake))


if __name__ == "__main__":
    sys.exit(main())
