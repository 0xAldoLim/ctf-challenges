import hashlib
import json
import time
from typing import Any


SESSION_SPAN_MS = 5000


def load_processor_scope(processor_scope_json: str) -> dict[str, Any]:
    if not processor_scope_json:
        return {}
    data = json.loads(processor_scope_json)
    if not isinstance(data, dict):
        return {}
    return data


def stable_scope(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def stable_token(purpose: str, data: dict[str, Any]) -> str:
    digest = hashlib.blake2s(digest_size=16)
    digest.update(purpose.encode())
    digest.update(b"\0")
    digest.update(stable_scope(data))
    return digest.hexdigest()


def maintenance_session_start(now_ms: int | None = None) -> int:
    current = int(now_ms if now_ms is not None else time.time() * 1000)
    return current // SESSION_SPAN_MS * SESSION_SPAN_MS


def restore_ref_subset(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "owner_id": str(scope.get("owner_id") or ""),
        "billing_id": str(scope.get("billing_id") or ""),
        "storage_uid": str(scope.get("storage_uid") or ""),
        "processor_ref": str(scope.get("processor_ref") or ""),
        "mode": str(scope.get("mode") or ""),
        "session_start_ms": int(
            scope.get("session_start_ms") or maintenance_session_start()
        ),
    }


def restore_ref(scope: dict[str, Any]) -> str:
    return stable_token("restore.ref.v1", restore_ref_subset(scope))
