import logging
import os

from flask import Flask, jsonify, request, send_from_directory

from env import require
import cvd
import powmod

_runner_log = logging.getLogger("runner")
_LOG_LEVEL = require("LOG_LEVEL").upper()
_gunicorn_handlers = logging.getLogger("gunicorn.error").handlers
if _gunicorn_handlers:
    _runner_log.handlers = _gunicorn_handlers
    _runner_log.propagate = False
else:
    logging.basicConfig()
for _name in ("runner", "gunicorn.error", "gunicorn.access", "werkzeug"):
    logging.getLogger(_name).setLevel(_LOG_LEVEL)

FRONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "front")

app = Flask(__name__, static_folder=None)
manager = cvd.InstanceManager()


@app.get("/")
def index():
    return send_from_directory(FRONT_DIR, "index.html")


@app.get("/status")
def status():
    return jsonify({
        "service": "pwn-android-umode runner",
        "endpoints": {
            "GET /pow": "fetch a proof-of-work challenge",
            "POST /instance": "body {pow:{challenge,exp,difficulty,sig,nonce}} -> boots an instance",
            "GET /instance/<id>": "instance status / remaining TTL",
            "DELETE /instance/<id>": "release an instance early",
        },
        "max_instances": cvd.MAX_INSTANCES,
        "in_use": manager.count(),
    })


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "in_use": manager.count(), "max": cvd.MAX_INSTANCES})


@app.get("/pow")
def get_pow():
    return jsonify(powmod.new_challenge())


def _check_pow(pw: dict) -> tuple[bool, str]:
    return powmod.verify(
        str(pw.get("challenge", "")),
        int(pw.get("exp", 0) or 0),
        int(pw.get("difficulty", 0) or 0),
        str(pw.get("sig", "")),
        str(pw.get("nonce", "")),
    )


@app.post("/instance")
def create_instance():
    body = request.get_json(silent=True) or {}
    ok, msg = _check_pow(body.get("pow") or {})
    if not ok:
        return jsonify({"error": f"pow: {msg}"}), 403

    try:
        inst = manager.create()
    except cvd.CapacityError:
        return jsonify({"error": "all instance slots in use, retry shortly"}), 429
    except Exception as exc:
        return jsonify({"error": f"failed to start instance: {exc}"}), 500

    return jsonify(inst.public()), 202


@app.get("/instance/<iid>")
def instance_status(iid: str):
    inst = manager.get(iid)
    if inst is None:
        return jsonify({"error": "unknown or expired instance"}), 404
    return jsonify(inst.public())


@app.delete("/instance/<iid>")
def instance_delete(iid: str):
    return (jsonify({"released": True}), 200) if manager.stop(iid) \
        else (jsonify({"error": "unknown or expired instance"}), 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=13337, threaded=True)
