#!/usr/bin/env python3

import hashlib
import sys
import time

import urllib.request
import json


def _post(url: str, obj: dict, timeout: int) -> tuple[int, dict]:
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def _leading_zero_bits(d: bytes) -> int:
    bits = 0
    for b in d:
        if b == 0:
            bits += 8
            continue
        return bits + 8 - b.bit_length()
    return bits


def solve(challenge: str, difficulty: int) -> str:
    n = 0
    while True:
        nonce = str(n)
        if _leading_zero_bits(hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()) >= difficulty:
            return nonce
        n += 1


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:13337"

    print(f"[*] GET {base}/pow")
    pw = _get(f"{base}/pow")
    print(f"    challenge={pw['challenge']} difficulty={pw['difficulty']}")

    t0 = time.time()
    pw["nonce"] = solve(pw["challenge"], pw["difficulty"])
    print(f"[*] solved PoW in {time.time()-t0:.1f}s (nonce={pw['nonce']})")

    print("[*] POST /instance …")
    status, body = _post(f"{base}/instance", {"pow": pw}, timeout=30)
    if status not in (201, 202):
        print(f"[!] {status}: {body}")
        return 1
    iid = body["instance_id"]
    print(f"[*] booting instance {iid} (~1-3 min); polling status…")

    deadline = time.time() + 400
    while time.time() < deadline:
        d = _get(f"{base}/instance/{iid}")
        st = d.get("status")
        if st == "ready":
            print(f"[+] instance ready:\n{json.dumps(d, indent=2)}")
            print(f"\n    message @{d.get('target_username')} via {d.get('relay_url')}")
            return 0
        if st == "failed":
            print(f"[!] boot failed: {d.get('error')}")
            return 1
        time.sleep(3)
    print("[!] timed out waiting for instance to become ready")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
