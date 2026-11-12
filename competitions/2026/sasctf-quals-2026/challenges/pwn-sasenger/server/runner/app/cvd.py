import json
import logging
import secrets
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field

from env import require, require_int

_log = logging.getLogger("runner.cvd")

CF_IMAGE = require("CF_IMAGE")
DOCKER = require("DOCKER_BIN")
IMAGES_HOST_DIR = require("IMAGES_HOST_DIR")
SCRIPTS_HOST_DIR = require("SCRIPTS_HOST_DIR")
APK_HOST_PATH = require("APK_HOST_PATH")
KERNEL_HOST_PATH = require("KERNEL_HOST_PATH")

MAX_INSTANCES = require_int("MAX_INSTANCES")
INSTANCE_TTL_S = require_int("INSTANCE_TTL_S")
IDLE_TTL_S = require_int("IDLE_TTL_S")
FAILED_GRACE_S = require_int("FAILED_GRACE_S")
BOOT_TIMEOUT_S = require_int("BOOT_TIMEOUT_S")
CF_CPUS = require_int("CF_CPUS")
CF_MEM_MB = require_int("CF_MEM_MB")

EXPOSE_CONSOLE = require_int("EXPOSE_CONSOLE") != 0
CONSOLE_BIND = require("CONSOLE_BIND")
_CONSOLE_GUEST_PORT = 1080

RELAY_ADMIN_URL = require("RELAY_ADMIN_URL")
RELAY_PUBLIC_URL = require("RELAY_PUBLIC_URL")
RELAY_INTERNAL_HOSTPORT = require("RELAY_INTERNAL_HOSTPORT")
RELAY_ADMIN_KEY = require("RELAY_ADMIN_KEY")
FLAG = require("FLAG")


class CapacityError(RuntimeError):
    pass


@dataclass
class Instance:
    id: str
    container: str
    created: float
    expires: float
    ready_at: float = 0.0
    slot: int = 1
    status: str = "booting"
    error: str = ""
    relay_last_inbound: float = 0.0
    extra: dict = field(default_factory=dict)

    def _lease_base(self) -> float:
        return self.ready_at or self.created

    def _last_activity(self) -> float:
        return max(self._lease_base(), self.relay_last_inbound)

    def _lease_deadline(self) -> float:
        return min(
            self._lease_base() + INSTANCE_TTL_S, self._last_activity() + IDLE_TTL_S
        )

    def public(self) -> dict:
        now = time.time()
        d = {"instance_id": self.id, "status": self.status}
        if self.status == "failed":
            d["error"] = self.error or "boot failed"
            d["ttl_seconds"] = max(0, int(self.expires - now))
            return d
        deadline = self._lease_deadline()
        d["expires_at"] = int(deadline)
        d["ttl_seconds"] = max(0, int(deadline - now))
        d["idle_seconds"] = max(0, int(now - self._last_activity()))
        d["idle_window_seconds"] = IDLE_TTL_S
        hard = int(self._lease_base() + INSTANCE_TTL_S)
        d["max_expires_at"] = hard
        d["max_ttl_seconds"] = max(0, int(hard - now))
        if self.status == "ready":
            d["relay_url"] = self.extra.get("relay_url", "")
            d["target_username"] = self.extra.get("target_username", "")
        return d


class InstanceManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: dict[str, Instance] = {}
        self._sweep_orphans()
        self._reaper = threading.Thread(target=self._reap_loop, daemon=True)
        self._reaper.start()

    def _sweep_orphans(self) -> None:
        out = self._run(
            [DOCKER, "ps", "-aq", "--filter", "name=^cf-inst-"],
            "docker ps orphans",
            check=False,
        )
        ids = [x for x in (out or "").split() if x]
        for cid in ids:
            self._run([DOCKER, "rm", "-f", cid], "docker rm orphan", check=False)
        if ids:
            _log.warning("swept %d orphaned instance container(s) at startup", len(ids))

    def create(self) -> Instance:
        with self._lock:
            used = {v.slot for v in self._instances.values() if v.status != "failed"}
            free = next((n for n in range(1, MAX_INSTANCES + 1) if n not in used), None)
            if free is None:
                raise CapacityError("all instance slots in use")
            iid = secrets.token_hex(8)
            now = time.time()
            inst = Instance(
                id=iid,
                container=f"cf-inst-{iid}",
                created=now,
                expires=now + INSTANCE_TTL_S,
                slot=free,
                status="booting",
            )
            self._instances[iid] = inst

        threading.Thread(
            target=self._boot, args=(inst,), daemon=True, name=f"boot-{iid}"
        ).start()
        return inst

    def _boot(self, inst: Instance) -> None:
        t0 = time.time()
        try:
            _log.info(
                "instance %s booting (slot %d, container %s)",
                inst.id,
                inst.slot,
                inst.container,
            )
            self._docker_run(inst)
            _log.info(
                "instance %s container up; waiting for boot (timeout %ds)",
                inst.id,
                BOOT_TIMEOUT_S,
            )
            self._wait_ready(inst)
            _log.info(
                "instance %s booted in %ds; provisioning victim",
                inst.id,
                int(time.time() - t0),
            )
            self._provision(inst)
            inst.ready_at = time.time()
            inst.status = "ready"
            _log.info(
                "instance %s ready in %ds (victim=%s)%s",
                inst.id,
                int(time.time() - t0),
                inst.extra.get("target_username"),
                (
                    f" console={inst.extra['console_url']}"
                    if "console_url" in inst.extra
                    else ""
                ),
            )
        except Exception as exc:
            _log.warning(
                "instance %s boot failed after %ds: %s",
                inst.id,
                int(time.time() - t0),
                exc,
            )
            inst.error = str(exc)[:300]
            inst.status = "failed"
            self._teardown_container(inst)
            inst.expires = time.time() + FAILED_GRACE_S

    def stop(self, iid: str) -> bool:
        return self._destroy(iid)

    def get(self, iid: str) -> Instance | None:
        with self._lock:
            return self._instances.get(iid)

    def count(self) -> int:
        with self._lock:
            return sum(1 for v in self._instances.values() if v.status != "failed")

    def _docker_run(self, inst: Instance) -> None:
        cmd = [
            DOCKER,
            "run",
            "-d",
            "--rm",
            "--name",
            inst.container,
            "--privileged",
            "--device",
            "/dev/kvm",
            "--add-host",
            "host.docker.internal:host-gateway",
            "-v",
            f"{IMAGES_HOST_DIR}:/cf/image-ro:ro",
            "-v",
            "/cf/overlay",
            "-e",
            f"CF_CPUS={CF_CPUS}",
            "-e",
            f"CF_MEM_MB={CF_MEM_MB}",
            "-e",
            f"BOOT_TIMEOUT_S={BOOT_TIMEOUT_S}",
            "-e",
            f"CF_BASE_INSTANCE_NUM={inst.slot}",
            "-e",
            f"CF_WEBRTC={1 if EXPOSE_CONSOLE else 0}",
        ]
        if EXPOSE_CONSOLE:
            host_port = _CONSOLE_GUEST_PORT + inst.slot - 1
            cmd += ["-p", f"{CONSOLE_BIND}:{host_port}:{_CONSOLE_GUEST_PORT}"]
            inst.extra["console_url"] = f"http://{CONSOLE_BIND}:{host_port}"
        cmd += ["-v", f"{SCRIPTS_HOST_DIR}/cf_entrypoint.sh:/cf/cf_entrypoint.sh:ro"]
        cmd += [
            "-v",
            f"{SCRIPTS_HOST_DIR}/provision_guest.sh:/cf/provision_guest.sh:ro",
        ]
        cmd += ["-v", f"{APK_HOST_PATH}:/cf/app.apk:ro"]
        cmd += ["-v", f"{KERNEL_HOST_PATH}:/cf/bzImage:ro"]
        cmd += [CF_IMAGE, "/cf/cf_entrypoint.sh"]
        _log.debug("instance %s docker run: %s", inst.id, " ".join(cmd))
        out = self._run(cmd, "docker run")
        _log.debug("instance %s container id %s", inst.id, (out or "").strip()[:12])

    def _container_logs(self, inst: Instance, tail: int) -> str:
        return (
            self._run(
                [DOCKER, "logs", "--tail", str(tail), inst.container],
                "docker logs",
                check=False,
                merge_stderr=True,
            )
            or ""
        ).strip()

    def _wait_ready(self, inst: Instance) -> None:
        deadline = time.time() + BOOT_TIMEOUT_S + 30
        t0 = time.time()
        last_line = last_beat = None
        while time.time() < deadline:
            if not self._container_running(inst.container):
                _log.warning(
                    "instance %s container exited during boot; last logs:\n%s",
                    inst.id,
                    self._container_logs(inst, 30),
                )
                raise RuntimeError("instance container exited during boot")
            logs = self._container_logs(inst, 5)
            if "[cf_entrypoint] ready" in logs:
                return
            now = time.time()
            cur = logs.splitlines()[-1] if logs else ""
            if last_beat is None or now - last_beat >= 15 or cur != last_line:
                _log.debug(
                    "instance %s booting (%ds): %s",
                    inst.id,
                    int(now - t0),
                    cur or "(no container output yet)",
                )
                last_beat, last_line = now, cur
            time.sleep(3)
        elapsed = int(time.time() - t0)
        _log.warning(
            "instance %s boot timed out after %ds; last logs:\n%s",
            inst.id,
            elapsed,
            self._container_logs(inst, 30),
        )
        raise RuntimeError(f"device did not finish booting within {elapsed}s")

    def _provision(self, inst: Instance) -> None:
        victim = self._relay_admin(
            "POST", "/admin/victim", body={"flag": FLAG, "flag_from": "sasctf"}
        )
        if not victim or not victim.get("username"):
            raise RuntimeError("relay admin: failed to create victim account")
        _log.debug(
            "instance %s victim=%s created; running provision_guest.sh",
            inst.id,
            victim["username"],
        )

        self._run(
            [
                DOCKER,
                "exec",
                "-d",
                inst.container,
                "socat",
                "TCP-LISTEN:8080,fork,reuseaddr",
                f"TCP:{RELAY_INTERNAL_HOSTPORT}",
            ],
            "docker exec socat",
            check=False,
        )

        self._run(
            [
                DOCKER,
                "exec",
                "-e",
                f"ADB_PORT={6520 + inst.slot - 1}",
                "-e",
                f"VICTIM_USER={victim['username']}",
                "-e",
                f"VICTIM_TOKEN={victim['token']}",
                "-e",
                f"VICTIM_ACC={victim.get('account_id', '')}",
                "-e",
                f"FLAG={FLAG}",
                inst.container,
                "/cf/provision_guest.sh",
            ],
            "provision_guest",
            merge_stderr=True,
            timeout=180,
            log_output=True,
        )

        inst.extra["target_username"] = victim["username"]
        inst.extra["relay_url"] = RELAY_PUBLIC_URL

    def _relay_admin(
        self, method: str, path: str, body: dict | None = None
    ) -> dict | None:
        if not (RELAY_ADMIN_URL and RELAY_ADMIN_KEY):
            return None
        data = json.dumps(body).encode() if body is not None else None
        headers = {"X-Admin-Key": RELAY_ADMIN_KEY}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            RELAY_ADMIN_URL.rstrip("/") + path,
            method=method,
            data=data,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                resp = r.read()
                return json.loads(resp) if resp else {}
        except Exception as exc:
            _log.warning("relay admin %s %s failed: %s", method, path, exc)
            return None

    def _container_running(self, name: str) -> bool:
        out = self._run(
            [DOCKER, "inspect", "-f", "{{.State.Running}}", name],
            "docker inspect",
            check=False,
        )
        return (out or "").strip() == "true"

    def _teardown_container(self, inst: Instance) -> None:
        victim = inst.extra.get("target_username")
        if victim:
            self._relay_admin("DELETE", f"/admin/victim/{victim}")
        self._run([DOCKER, "rm", "-f", inst.container], "docker rm", check=False)

    def _destroy(self, iid: str) -> bool:
        with self._lock:
            inst = self._instances.pop(iid, None)
        if inst is None:
            return False
        self._teardown_container(inst)
        _log.info(
            "instance %s destroyed (victim=%s)", iid, inst.extra.get("target_username")
        )
        return True

    def _reap_loop(self) -> None:
        while True:
            now = time.time()
            with self._lock:
                ready = [
                    (i, v.extra.get("target_username"))
                    for i, v in self._instances.items()
                    if v.status == "ready" and v.extra.get("target_username")
                ]
            for iid, victim in ready:
                act = self._relay_admin("GET", f"/admin/victim/{victim}")
                if act and act.get("last_inbound"):
                    inst = self._instances.get(iid)
                    if inst:
                        inst.relay_last_inbound = float(act["last_inbound"])

            with self._lock:
                to_reap = set()
                for i, v in self._instances.items():
                    if v.status == "failed":
                        if now > v.expires:
                            to_reap.add(i)
                    elif v.status == "ready":
                        if now > v._lease_deadline() or not self._container_running(
                            v.container
                        ):
                            to_reap.add(i)
            for iid in to_reap:
                self._destroy(iid)
            time.sleep(15)

    @staticmethod
    def _run(
        cmd: list[str],
        what: str,
        check: bool = True,
        merge_stderr: bool = False,
        timeout: float = 60,
        log_output: bool = False,
    ) -> str:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            partial = ((e.stdout or "") + (e.stderr or "")).strip()
            if log_output and partial:
                _log.debug(
                    "%s (timed out after %ss) output:\n%s", what, timeout, partial
                )
            if check:
                raise RuntimeError(f"{what} timed out after {timeout}s")
            return ""
        combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if log_output and combined:
            _log.debug("%s output:\n%s", what, combined)
        if proc.returncode != 0:
            if check:
                detail = "see runner log" if log_output else proc.stderr.strip()[:200]
                raise RuntimeError(f"{what} failed (rc {proc.returncode}): {detail}")
            return ""
        out = proc.stdout or ""
        if merge_stderr:
            out += proc.stderr or ""
        return out.strip()
