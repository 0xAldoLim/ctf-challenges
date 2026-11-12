import json
import time
from datetime import datetime, timedelta, timezone

from arq.utils import to_unix_ms

from app.processor_config.scope import restore_ref
from app.background.queue import PRIVATE_QUEUE, pool, run_sync

SESSION_PREFIX = "restore:session:"
SESSION_INDEX = "restore:session:index"

CRON_NAME = "restore.session.close"


def cron_refs(span_seconds: int = 12, back_seconds: int = 0) -> list[str]:
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(seconds=back_seconds)
    end = now + timedelta(seconds=span_seconds)
    current = start.replace(microsecond=123456)
    refs: list[str] = []
    while current <= end:
        if current >= start and current.second % 5 == 0:
            refs.append(f"{CRON_NAME}:{to_unix_ms(current)}")
        current += timedelta(seconds=1)
    return refs


def session_payload(scope: dict) -> dict:
    return {
        "state": "active",
        "scope": scope,
        "opened_at": time.time(),
        "attestation_class": scope.get("attestation_class") or "standard",
        "evidence_hold": scope.get("evidence_hold") or "pending",
    }


async def open_session(redis, restore_ref_value: str, scope: dict) -> None:
    await redis.set(
        SESSION_PREFIX + restore_ref_value,
        json.dumps(session_payload(scope), sort_keys=True),
        ex=300,
    )
    await redis.sadd(SESSION_INDEX, restore_ref_value)


async def close_session(redis, restore_ref_value: str) -> None:
    raw = await redis.get(SESSION_PREFIX + restore_ref_value)
    if not raw:
        return
    data = json.loads(raw)
    data["state"] = "closed"
    await redis.set(
        SESSION_PREFIX + restore_ref_value,
        json.dumps(data, sort_keys=True),
        ex=90,
    )
    await redis.srem(SESSION_INDEX, restore_ref_value)


async def active(redis, restore_ref_value: str) -> bool:
    raw = await redis.get(SESSION_PREFIX + restore_ref_value)
    if not raw:
        return False
    data = json.loads(raw)
    return data.get("state") == "active"


async def ready(redis, restore_ref_value: str) -> bool:
    raw = await redis.get(SESSION_PREFIX + restore_ref_value)
    if not raw:
        return False
    data = json.loads(raw)
    if data.get("state") != "active":
        return False
    opened_at = float(data.get("opened_at") or 0)
    return time.time() - opened_at >= 1.2


async def active_scopes(redis) -> list[tuple[str, dict]]:
    restore_refs = await redis.smembers(SESSION_INDEX)
    entries: list[tuple[str, dict]] = []
    for raw_restore_ref in restore_refs:
        restore_ref_value = (
            raw_restore_ref.decode()
            if isinstance(raw_restore_ref, bytes)
            else str(raw_restore_ref)
        )
        raw = await redis.get(SESSION_PREFIX + restore_ref_value)
        if not raw:
            await redis.srem(SESSION_INDEX, restore_ref_value)
            continue
        data = json.loads(raw)
        if data.get("state") == "active":
            entries.append((restore_ref_value, data.get("scope") or {}))
    return entries


def restore_session_ready(restore_ref_value: str) -> bool:
    async def _check():
        redis = await pool(PRIVATE_QUEUE)
        try:
            return await ready(redis, restore_ref_value)
        finally:
            await redis.close()

    return run_sync(_check())


def restore_ref_for(scope: dict) -> str:
    return restore_ref(scope)
