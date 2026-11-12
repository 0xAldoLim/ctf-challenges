import hashlib
import hmac
import secrets
import threading
import time

from env import require, require_int

POW_SECRET = require("POW_SECRET").encode()
POW_DIFFICULTY = require_int("POW_DIFFICULTY")
POW_TTL_S = require_int("POW_TTL_S")

_consumed: dict[str, float] = {}
_lock = threading.Lock()


def _sign(challenge: str, exp: int, diff: int) -> str:
    msg = f"{challenge}:{exp}:{diff}".encode()
    return hmac.new(POW_SECRET, msg, hashlib.sha256).hexdigest()


def new_challenge() -> dict:
    challenge = secrets.token_hex(16)
    exp = int(time.time()) + POW_TTL_S
    diff = POW_DIFFICULTY
    return {
        "challenge": challenge,
        "exp": exp,
        "difficulty": diff,
        "sig": _sign(challenge, exp, diff),
        "algorithm": "find nonce s.t. sha256(f'{challenge}:{nonce}') has >= difficulty leading zero bits",
    }


def _leading_zero_bits(digest: bytes) -> int:
    bits = 0
    for b in digest:
        if b == 0:
            bits += 8
            continue
        bits += 8 - b.bit_length()
        break
    return bits


def verify(challenge: str, exp: int, diff: int, sig: str, nonce: str) -> tuple[bool, str]:
    if not (challenge and sig and nonce):
        return False, "missing pow fields"
    if not hmac.compare_digest(sig, _sign(challenge, exp, diff)):
        return False, "invalid pow token"
    if time.time() > exp:
        return False, "pow challenge expired"
    if diff < POW_DIFFICULTY:
        return False, "pow difficulty too low"

    digest = hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()
    if _leading_zero_bits(digest) < diff:
        return False, "pow solution invalid"

    now = time.time()
    with _lock:
        for k in [k for k, v in _consumed.items() if v < now]:
            del _consumed[k]
        if challenge in _consumed:
            return False, "pow challenge already used"
        _consumed[challenge] = exp
    return True, ""
