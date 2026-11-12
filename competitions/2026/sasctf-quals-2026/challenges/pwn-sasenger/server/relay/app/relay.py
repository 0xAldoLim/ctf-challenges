import base64
import logging
import secrets
import struct
import threading
import time
from collections import deque

from flask import Flask, jsonify, request

from env import require, require_int

ADMIN_KEY = require("RELAY_ADMIN_KEY")
POLL_WAIT_S = float(require("RELAY_POLL_WAIT_S"))
MAX_EVENTS = require_int("RELAY_MAX_EVENTS")
MAX_PAYLOAD_B64 = require_int("RELAY_MAX_PAYLOAD_B64")

log = logging.getLogger("relay")
_LOG_LEVEL = require("LOG_LEVEL").upper()
_gunicorn_handlers = logging.getLogger("gunicorn.error").handlers
if _gunicorn_handlers:
    log.handlers = _gunicorn_handlers
    log.propagate = False
else:
    logging.basicConfig()
for _name in ("relay", "gunicorn.error", "gunicorn.access", "werkzeug"):
    logging.getLogger(_name).setLevel(_LOG_LEVEL)

FLAG_SENDER = "sasctf"

PASSWORD_MIN_LEN = 12
PASSWORD_MIN_UNIQUE = 6


def _password_issue(pw: str) -> str | None:
    if len(pw) < PASSWORD_MIN_LEN:
        return "password must be at least %d characters" % PASSWORD_MIN_LEN
    classes = sum(
        (
            any(c.islower() for c in pw),
            any(c.isupper() for c in pw),
            any(c.isdigit() for c in pw),
            any(not c.isalnum() for c in pw),
        )
    )
    if classes < 3:
        return (
            "password must mix at least 3 of: lowercase, uppercase, " "digits, symbols"
        )
    if len(set(pw)) < PASSWORD_MIN_UNIQUE:
        return "password is too repetitive (use more distinct characters)"
    return None


def build_text_container(s):
    data = s.encode("utf-8")
    out = bytearray(b"SMC1")
    out += bytes([1, 0])
    out += struct.pack("<H", 1)
    out += bytes([1]) + struct.pack("<I", len(data)) + data
    return bytes(out)


app = Flask(__name__)

_lock = threading.Lock()
_accounts: dict[str, dict] = {}
_by_token: dict[str, str] = {}
_msg_owner: dict[str, str] = {}
_msg_seq = 0


def _new_account(username: str, password: str, ephemeral: bool) -> dict:
    acc = {
        "account_id": "acc_" + secrets.token_hex(6),
        "username": username,
        "password": password,
        "token": secrets.token_urlsafe(24),
        "ephemeral": ephemeral,
        "cond": threading.Condition(),
        "events": deque(maxlen=MAX_EVENTS),
        "seq": 0,
        "last_inbound": time.time(),
    }
    _accounts[username] = acc
    _by_token[acc["token"]] = username
    return acc


def _push(acc: dict, event: dict) -> None:
    with acc["cond"]:
        acc["seq"] += 1
        event["seq"] = acc["seq"]
        event["ts"] = int(time.time())
        acc["events"].append(event)
        if event.get("type") == "message":
            acc["last_inbound"] = time.time()
        acc["cond"].notify_all()


def _events_since(acc: dict, since: int) -> tuple[list[dict], int]:
    events = acc["events"]
    out: list[dict] = []
    for e in reversed(events):
        if e["seq"] <= since:
            break
        out.append(e)
    out.reverse()
    cursor = events[-1]["seq"] if events else since
    return out, cursor


def _auth() -> dict | None:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    with _lock:
        u = _by_token.get(h[7:])
        return _accounts.get(u) if u else None


def _pub(acc: dict) -> dict:
    return {
        "account_id": acc["account_id"],
        "username": acc["username"],
        "token": acc["token"],
    }


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.post("/v1/register")
def register():
    b = request.get_json(silent=True) or {}
    username = str(b.get("username", "")).strip()
    password = str(b.get("password", ""))
    if not (3 <= len(username) <= 32) or not username.replace("_", "").isalnum():
        return jsonify({"error": "username must be 3-32 alphanumeric/underscore"}), 400
    if username.lower() == FLAG_SENDER or username.lower().startswith("ghost_"):
        return jsonify({"error": "username reserved"}), 409
    issue = _password_issue(password)
    if issue:
        return jsonify({"error": issue}), 400
    with _lock:
        if username in _accounts:
            return jsonify({"error": "username taken"}), 409
        acc = _new_account(username, password, ephemeral=False)
        return jsonify(_pub(acc)), 201


@app.post("/v1/login")
def login():
    b = request.get_json(silent=True) or {}
    username = str(b.get("username", "")).strip()
    password = str(b.get("password", ""))
    with _lock:
        acc = _accounts.get(username)
        if not acc or acc["password"] != password:
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify(_pub(acc)), 200


@app.get("/v1/whoami")
def whoami():
    acc = _auth()
    if not acc:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"account_id": acc["account_id"], "username": acc["username"]})


@app.post("/v1/send")
def send():
    global _msg_seq
    acc = _auth()
    if not acc:
        return jsonify({"error": "unauthorized"}), 401
    b = request.get_json(silent=True) or {}
    to = str(b.get("to", "")).strip()
    if to == acc["username"]:
        return jsonify({"error": "cannot message yourself"}), 400
    payload_b64 = str(b.get("payload_b64", ""))
    if len(payload_b64) > MAX_PAYLOAD_B64:
        return jsonify({"error": "payload too large"}), 413

    with _lock:
        dst = _accounts.get(to)
        if not dst:
            return jsonify({"error": "unknown recipient"}), 404
        _msg_seq += 1
        mid = "msg_%d_%s" % (_msg_seq, secrets.token_hex(3))
        _msg_owner[mid] = acc["username"]
        _push(
            dst,
            {
                "type": "message",
                "id": mid,
                "from": acc["username"],
                "to": to,
                "payload_b64": payload_b64,
            },
        )
    return jsonify({"message_id": mid}), 201


@app.post("/v1/receipt")
def receipt():
    acc = _auth()
    if not acc:
        return jsonify({"error": "unauthorized"}), 401
    b = request.get_json(silent=True) or {}
    mid = str(b.get("message_id", ""))
    state = str(b.get("state", ""))
    meta = b.get("meta")
    with _lock:
        sender = _msg_owner.get(mid)
        if sender and sender in _accounts:
            _push(
                _accounts[sender],
                {
                    "type": "receipt",
                    "message_id": mid,
                    "from": acc["username"],
                    "state": state,
                    "meta": meta,
                },
            )
    return jsonify({"ok": True})


@app.get("/v1/poll")
def poll():
    acc = _auth()
    if not acc:
        return jsonify({"error": "unauthorized"}), 401
    try:
        since = int(request.args.get("since", "0") or 0)
    except ValueError:
        since = 0

    deadline = time.time() + POLL_WAIT_S
    cond = acc["cond"]
    with cond:
        while True:
            events, cursor = _events_since(acc, since)
            if events or time.time() >= deadline:
                return jsonify({"events": events, "cursor": cursor})
            cond.wait(timeout=max(0.0, deadline - time.time()))


def _check_admin() -> bool:
    return secrets.compare_digest(request.headers.get("X-Admin-Key", ""), ADMIN_KEY)


@app.post("/admin/victim")
def admin_create_victim():
    if not _check_admin():
        return jsonify({"error": "forbidden"}), 403
    global _msg_seq
    body = request.get_json(silent=True) or {}
    flag = body.get("flag")
    flag_from = str(body.get("flag_from", FLAG_SENDER))
    with _lock:
        while True:
            username = "ghost_" + secrets.token_hex(4)
            if username not in _accounts:
                break
        password = secrets.token_urlsafe(12)
        acc = _new_account(username, password, ephemeral=True)
        if flag:
            _msg_seq += 1
            mid = "msg_%d_%s" % (_msg_seq, secrets.token_hex(3))
            payload_b64 = base64.b64encode(build_text_container(str(flag))).decode()
            _push(
                acc,
                {
                    "type": "message",
                    "id": mid,
                    "from": flag_from,
                    "to": username,
                    "payload_b64": payload_b64,
                },
            )
        out = _pub(acc)
        out["password"] = password
    return jsonify(out), 201


@app.get("/admin/victim/<username>")
def admin_victim_activity(username: str):
    if not _check_admin():
        return jsonify({"error": "forbidden"}), 403
    with _lock:
        acc = _accounts.get(username)
        if not acc:
            return jsonify({"exists": False}), 404
        return jsonify({"exists": True, "last_inbound": int(acc["last_inbound"])})


@app.delete("/admin/victim/<username>")
def admin_delete_victim(username: str):
    if not _check_admin():
        return jsonify({"error": "forbidden"}), 403
    with _lock:
        acc = _accounts.pop(username, None)
        if acc:
            _by_token.pop(acc["token"], None)
            for mid, owner in list(_msg_owner.items()):
                if owner == username:
                    _msg_owner.pop(mid, None)
        return jsonify({"removed": acc is not None})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
