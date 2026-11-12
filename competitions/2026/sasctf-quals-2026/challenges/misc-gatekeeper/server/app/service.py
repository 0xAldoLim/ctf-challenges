import base64
import json
import os
import queue
import subprocess
import threading
import time

from flask import Flask, jsonify, send_from_directory
from flask_sock import Sock

import powmod
import runner

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
MAX_QUEUE = int(os.getenv("MAX_QUEUE", str(2 * MAX_CONCURRENT)))
MAX_PROGRAM_BYTES = int(os.getenv("MAX_PROGRAM_BYTES", str(128 * 1024)))
WS_HANDSHAKE_TIMEOUT_S = int(os.getenv("WS_HANDSHAKE_TIMEOUT_S", "30"))

FRONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "front")

app = Flask(__name__, static_folder=None)
app.config["SOCK_SERVER_OPTIONS"] = {"max_message_size": 1 << 20}
sock = Sock(app)

_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_pending_lock = threading.Lock()
_pending = 0


@app.get("/")
def index():
    return send_from_directory(FRONT_DIR, "index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/config")
def get_config():
    return jsonify({"max_program_bytes": MAX_PROGRAM_BYTES})


@app.get("/pow")
def get_pow():
    return jsonify(powmod.new_challenge())


def _validate_submission(program_b64, pw) -> tuple[bytes | None, str]:
    if not program_b64:
        return None, "missing program"
    ok, msg = powmod.verify(
        str(pw.get("challenge", "")),
        int(pw.get("exp", 0) or 0),
        int(pw.get("difficulty", 0) or 0),
        str(pw.get("sig", "")),
        str(pw.get("nonce", "")),
    )
    if not ok:
        return None, f"pow: {msg}"
    try:
        program = base64.b64decode(program_b64, validate=True)
    except Exception:
        return None, "invalid base64 program"
    if len(program) > MAX_PROGRAM_BYTES:
        return None, "program too large"
    return program, ""


def _ws_send_json(ws, obj) -> None:
    ws.send(json.dumps(obj))


@sock.route("/ws/run")
def ws_run(ws):
    global _pending

    try:
        raw = ws.receive(timeout=WS_HANDSHAKE_TIMEOUT_S)
    except Exception:
        return
    if not raw:
        return
    try:
        body = json.loads(raw)
    except Exception:
        _ws_send_json(ws, {"type": "error", "message": "bad handshake"})
        return

    program, err = _validate_submission(body.get("program"), body.get("pow") or {})
    if program is None:
        _ws_send_json(ws, {"type": "error", "message": err})
        return

    with _pending_lock:
        if _pending >= MAX_QUEUE:
            _ws_send_json(ws, {"type": "busy", "message": "server busy, retry shortly"})
            return
        _pending += 1
    try:
        with _slots:
            passed, issue = runner.verify(program)
            if not passed:
                _ws_send_json(ws, {"type": "rejected", "issue": issue})
                return
            _ws_send_json(ws, {"type": "running"})
            _run_interactive(ws, program)
    finally:
        with _pending_lock:
            _pending -= 1


def _run_interactive(ws, program: bytes) -> None:
    sent = 0
    fed = bytearray()
    captured = bytearray()
    code = -1
    with runner.qemu_session(program, subprocess.PIPE) as proc:
        out_q: queue.Queue = queue.Queue()

        def pump_stdout():
            try:
                while True:
                    chunk = proc.stdout.read1(4096)
                    if not chunk:
                        break
                    out_q.put(chunk)
            except Exception:
                pass
            finally:
                    out_q.put(None)

        threading.Thread(target=pump_stdout, daemon=True).start()

        deadline = time.time() + runner.QEMU_TIMEOUT_S
        while True:
            eof = False
            try:
                while True:
                    chunk = out_q.get_nowait()
                    if chunk is None:
                        eof = True
                        break
                    if sent < runner.QEMU_MAX_OUTPUT:
                        piece = chunk[: runner.QEMU_MAX_OUTPUT - sent]
                        if piece:
                            ws.send(piece)
                            captured += piece
                            sent += len(piece)
            except queue.Empty:
                pass
            if eof:
                break

            if time.time() > deadline:
                proc.kill()
                try:
                    _ws_send_json(ws, {"type": "timeout"})
                except Exception:
                    pass
                break

            try:
                msg = ws.receive(timeout=0.05)
            except Exception:
                break
            if msg is None:
                continue
            if isinstance(msg, (bytes, bytearray)):
                fed += msg
                try:
                    proc.stdin.write(msg)
                    proc.stdin.flush()
                except (BrokenPipeError, ValueError, OSError):
                    pass
            elif isinstance(msg, str):
                try:
                    if json.loads(msg).get("type") == "eof" and proc.stdin:
                        proc.stdin.close()
                except Exception:
                    pass

        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        code = proc.poll()
        try:
            _ws_send_json(
                ws, {"type": "exit", "code": code if code is not None else -1}
            )
        except Exception:
            pass

    runner.archive_submission(
        program, bytes(fed), mode="interactive", stdout=bytes(captured), exit_code=code
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2048, threaded=True)
