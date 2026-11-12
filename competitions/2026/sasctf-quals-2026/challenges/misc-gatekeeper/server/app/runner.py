import base64
import contextlib
import hashlib
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Iterator

APP_DIR = os.path.dirname(os.path.abspath(__file__))

_log = logging.getLogger("gatekeeper.archive")

ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "/data/programs")

VERIFY_TIMEOUT_S = int(os.getenv("VERIFY_TIMEOUT_S", "35"))

QEMU_BIN = os.getenv("QEMU_BIN", "/opt/gatekeeper/qemu-system-riscv64")
QEMU_TIMEOUT_S = int(os.getenv("QEMU_TIMEOUT_S", "12"))
QEMU_MAX_OUTPUT = int(os.getenv("QEMU_MAX_OUTPUT", str(64 * 1024)))

RUN_DIR_BASE = os.getenv("RUN_DIR_BASE", "/tmp")

FLAG = os.getenv("FLAG", "SAS{example_flag_replace_me}").encode()


def archive_submission(
    program: bytes,
    stdin_data: bytes,
    *,
    mode: str,
    stdout: bytes = b"",
    exit_code: int | None = None,
) -> None:
    if not ARCHIVE_DIR:
        return
    try:
        now = datetime.now(timezone.utc)
        digest = hashlib.sha256(program).hexdigest()
        record = {
            "timestamp": now.isoformat(),
            "mode": mode,
            "program_sha256": digest,
            "program_b64": base64.b64encode(program).decode(),
            "input_b64": base64.b64encode(stdin_data).decode(),
            "stdout_b64": base64.b64encode(stdout).decode(),
            "exit_code": exit_code,
        }
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        stamp = now.strftime("%Y%m%dT%H%M%S")
        name = f"{stamp}-{digest[:12]}-{secrets.token_hex(3)}.json"
        path = os.path.join(ARCHIVE_DIR, name)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=ARCHIVE_DIR)
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(record, fh)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except Exception as exc:
        _log.warning("failed to archive accepted run: %s", exc)


def _flag_gk_bytes() -> bytes:
    flag = FLAG
    if len(flag) % 4:
        flag += b"\x00" * (4 - len(flag) % 4)
    return b"PLA\x00" + flag


def verify(program: bytes) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(suffix=".bin") as tf:
        tf.write(program)
        tf.flush()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "verify_worker", tf.name],
                cwd=APP_DIR,
                capture_output=True,
                text=True,
                timeout=VERIFY_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return False, "verification timed out"

    lines = proc.stdout.strip().splitlines()
    if proc.returncode in (0, 1) and lines:
        try:
            res = json.loads(lines[-1])
            return bool(res["passed"]), res.get("issue", "")
        except Exception:
            pass
    return False, "verification failed (resource limit or internal error)"


@contextlib.contextmanager
def qemu_session(program: bytes, stdin) -> Iterator[subprocess.Popen]:
    run_dir = tempfile.mkdtemp(prefix="gk-run-", dir=RUN_DIR_BASE)
    proc: subprocess.Popen | None = None
    bios = None
    try:
        files_dir = os.path.join(run_dir, "files")
        os.makedirs(files_dir, exist_ok=True)
        name = secrets.token_bytes(8).hex() + secrets.token_bytes(8).hex() + ".gk"
        with open(os.path.join(files_dir, name), "wb") as fh:
            fh.write(_flag_gk_bytes())

        env = {**os.environ, "GATEKEEPER_FILES": files_dir}

        bios = tempfile.NamedTemporaryFile(suffix=".bin", dir=run_dir)
        bios.write(program)
        bios.flush()
        cmd = [
            QEMU_BIN,
            "-machine",
            "gatekeeper",
            "-bios",
            bios.name,
            "-display",
            "none",
            "-serial",
            "none",
            "-monitor",
            "none",
        ]
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        yield proc
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        if bios is not None:
            bios.close()
        shutil.rmtree(run_dir, ignore_errors=True)
