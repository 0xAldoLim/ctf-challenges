#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import shutil
import subprocess
import threading
from urllib.parse import parse_qs, urlparse

lock = threading.Lock()
LOG_PATH = "/run/paradoxy-bootstrap.log"
TOKEN_DIR = "/root/konnectivity-agent-token"
K0S_PODS_DIR = "/var/lib/k0s/kubelet/pods"


def cmdline_value(key):
    try:
        with open("/proc/cmdline", "r", encoding="utf-8") as fh:
            for item in fh.read().split():
                if item.startswith(key + "="):
                    return item.split("=", 1)[1]
    except OSError:
        return ""
    return ""


def debug_enabled():
    return (
        os.environ.get("PARADOXY_DEBUG_API") == "1"
        or cmdline_value("paradoxy.debug_api") == "1"
    )


def write_console(line):
    for path in ("/dev/console", "/dev/ttyS0"):
        try:
            with open(path, "a", encoding="utf-8", errors="replace") as console:
                console.write(line)
                console.flush()
            return
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._reply(200, b"ok\n")
            return
        if parsed.path == "/konnectivity-ready":
            if self._konnectivity_ready(parsed.query):
                self._reply(200, b"ready\n")
            else:
                self._reply(503, b"not ready\n")
            return
        if parsed.path.startswith("/debug/"):
            if not debug_enabled():
                self._reply(404, b"not found\n")
                return
            if parsed.path == "/debug/bootstrap-log":
                try:
                    with open(LOG_PATH, "rb") as fh:
                        self._reply(200, fh.read()[-65536:])
                except FileNotFoundError:
                    self._reply(404, b"bootstrap log not found\n")
                return
            if parsed.path == "/debug/status":
                self._reply(200, self._status())
                return
        self._reply(404, b"not found\n")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/bootstrap":
            self._reply(404, b"not found\n")
            return

        if not lock.acquire(blocking=False):
            self._reply(409, b"bootstrap already running\n")
            return

        try:
            stream = parse_qs(parsed.query).get("stream", ["0"])[0] == "1"
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            env = os.environ.copy()
            env["PARADOXY_BOOTSTRAP_BODY"] = body
            proc = subprocess.Popen(
                ["/usr/local/sbin/paradoxy-bootstrap"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            chunks = []
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
            with open(LOG_PATH, "w", encoding="utf-8") as log:
                assert proc.stdout is not None
                for line in proc.stdout:
                    chunks.append(line)
                    log.write(line)
                    log.flush()
                    write_console(line)
                    if stream:
                        self.wfile.write(line.encode())
                        self.wfile.flush()
            proc.wait(timeout=30)
            if stream:
                if proc.returncode != 0:
                    line = f"[paradoxy-bootstrap-api] bootstrap exited {proc.returncode}\n"
                    write_console(line)
                    self.wfile.write(line.encode())
                    self.wfile.flush()
                return
            status = 200 if proc.returncode == 0 else 500
            self._reply(status, "".join(chunks).encode())
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or "bootstrap timed out\n"
            if isinstance(output, str):
                output = output.encode()
            self._reply(504, output)
        finally:
            lock.release()

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _konnectivity_ready(self, query):
        expected_addr = parse_qs(query).get("addr", [""])[0]
        self._sync_konnectivity_token(expected_addr)
        try:
            with open(os.path.join(TOKEN_DIR, "token"), "rb") as fh:
                token = fh.read().strip()
            with open(os.path.join(TOKEN_DIR, "addr"), "r", encoding="utf-8") as fh:
                addr = fh.read().strip()
        except FileNotFoundError:
            return False

        return bool(token) and (not expected_addr or addr == expected_addr)

    def _sync_konnectivity_token(self, expected_addr):
        os.makedirs(TOKEN_DIR, exist_ok=True)

        token_file = None
        for root, _, files in os.walk(K0S_PODS_DIR):
            if "konnectivity-agent-token" not in root:
                continue
            for name in files:
                if name in ("token", "konnectivity-agent-token"):
                    token_file = os.path.join(root, name)
                    break
            if token_file:
                break

        if token_file:
            tmp_token = os.path.join(TOKEN_DIR, "token.tmp")
            shutil.copyfile(token_file, tmp_token)
            os.chmod(tmp_token, 0o400)
            os.chown(tmp_token, 0, 0)
            os.replace(tmp_token, os.path.join(TOKEN_DIR, "token"))

        if expected_addr:
            tmp_addr = os.path.join(TOKEN_DIR, "addr.tmp")
            with open(tmp_addr, "w", encoding="utf-8") as fh:
                fh.write(expected_addr + "\n")
            os.chmod(tmp_addr, 0o400)
            os.chown(tmp_addr, 0, 0)
            os.replace(tmp_addr, os.path.join(TOKEN_DIR, "addr"))

    def _status(self):
        commands = [
            ["sh", "-c", "cat /proc/cmdline; hostname; ip -4 addr"],
            ["ps", "-ef"],
            ["ls", "-la", "/root/konnectivity-agent-token", "/etc/systemd/system/k0scontroller.service", "/etc/systemd/system/k0sworker.service", "/run/k0s", "/var/lib/k0s", "/var/lib/k0s/pki"],
            ["sh", "-c", "cat /etc/systemd/system/k0scontroller.service /etc/systemd/system/k0sworker.service 2>/dev/null || true"],
            ["systemctl", "--no-pager", "--plain", "status", "k0scontroller"],
            ["systemctl", "--no-pager", "--plain", "status", "k0sworker"],
            ["k0s", "status"],
            ["k0s", "kubectl", "get", "nodes", "-o", "wide"],
            ["k0s", "kubectl", "get", "pods", "-A", "-o", "wide"],
            ["k0s", "kubectl", "-n", "kube-system", "get", "events", "--sort-by=.lastTimestamp"],
            ["k0s", "kubectl", "-n", "kube-system", "describe", "pods"],
            ["k0s", "kubectl", "-n", "kube-system", "logs", "-l", "k8s-app=kube-router", "--all-containers=true", "--tail=120"],
            ["k0s", "kubectl", "-n", "kube-system", "logs", "-l", "k8s-app=konnectivity-agent", "--all-containers=true", "--tail=120"],
            ["journalctl", "-u", "k0scontroller", "-n", "120", "--no-pager"],
            ["journalctl", "-u", "k0sworker", "-n", "160", "--no-pager"],
            ["df", "-h", "/"],
            ["free", "-h"],
        ]
        output = []
        for cmd in commands:
            output.append("$ " + " ".join(cmd) + "\n")
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=10,
                )
                output.append(proc.stdout)
            except Exception as exc:
                output.append(f"{type(exc).__name__}: {exc}\n")
            output.append("\n")
        return "".join(output).encode()


ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
