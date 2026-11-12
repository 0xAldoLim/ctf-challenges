import asyncio
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from arq.constants import result_key_prefix
from sqlalchemy.orm import Session

from app.processor_config.scope import restore_ref
from models.billing import Billing
from utils.database import Session as SessionFactory

from app.background.queue import PRIVATE_QUEUE
from app.restore_session.state import active_scopes, close_session, cron_refs, open_session

ARCHIVE_RESTORE_PRICE_CODE = "archive.restore.final"
PREVIEW_PRICE_CODE = "archive.trial.preview"
PRICES = {
    ARCHIVE_RESTORE_PRICE_CODE: 7331,
    PREVIEW_PRICE_CODE: 10,
}


async def health_check(ctx, scope: dict[str, Any]):
    return {"state": "observed"}


def _provider_touch(scope: dict[str, Any]) -> str:
    raw_url = scope.get("provider_url")
    if not raw_url:
        return "local"
    parsed = urlparse(str(raw_url))
    if parsed.scheme not in {"http", "https"}:
        return "skipped"
    try:
        request = Request(str(raw_url), headers={"User-Agent": "Archive-Restore"})
        with urlopen(request, timeout=0.75) as response:
            response.read(1024)
            return "observed"
    except Exception:
        return "degraded"


async def _provider_touch_async(scope: dict[str, Any]) -> str:
    return await asyncio.to_thread(_provider_touch, scope)


async def prepare_restore_session(ctx, scope: dict[str, Any]):
    restore_ref_value = restore_ref(scope)
    await open_session(ctx["redis"], restore_ref_value, scope)
    return {
        "state": "pending",
        "provider": await _provider_touch_async(scope),
        "class": scope.get("attestation_class") or "standard",
    }


async def _recent_restore_checkpoint(redis) -> bool:
    for item_ref in cron_refs(6, back_seconds=6):
        if await redis.exists(result_key_prefix + item_ref):
            return True
    return False


async def close_restore_session(ctx, scope: dict[str, Any] | None = None):
    if await _recent_restore_checkpoint(ctx["redis"]):
        return {"state": "observed"}

    if scope is None:
        for restore_ref_value, _item_scope in await active_scopes(ctx["redis"]):
            await close_session(ctx["redis"], restore_ref_value)
        return {"state": "observed"}

    await close_session(ctx["redis"], restore_ref(scope))
    return {"state": "observed"}


async def restore_checkpoint(ctx, scope: dict[str, Any], restore_ref_value: str):
    if restore_ref_value != restore_ref(scope):
        return {"state": "skipped"}
    return {"state": "ready", "ticket": (cron_refs(1) or [""])[0]}


async def _billing_price_check(scope: dict[str, Any], price_code: str):
    price = PRICES.get(price_code, PRICES[ARCHIVE_RESTORE_PRICE_CODE])
    db: Session = SessionFactory()
    try:
        billing = (
            db.query(Billing)
            .filter_by(
                uid=str(scope.get("billing_id")), user_id=int(scope.get("owner_id"))
            )
            .first()
        )
        return {
            "accepted": bool(billing and billing.balance >= price),
            "price_code": price_code,
        }
    finally:
        db.close()


async def billing_preview_check(ctx, scope: dict[str, Any], price_code: str):
    return await _billing_price_check(scope, price_code)


async def public_archive_approval_receipt(
    ctx, scope: dict[str, Any], price_code: str
):
    return {
        "accepted": bool(scope.get("mode") == "restore" and price_code in PRICES),
        "price_code": price_code,
    }


async def private_archive_approval_receipt(
    ctx, scope: dict[str, Any], price_code: str
):
    await _provider_touch_async(scope)
    return await _billing_price_check(scope, price_code)


async def restore_audit(ctx, scope: dict[str, Any], storage_uid: str):
    return {"state": "ready", "storage": str(storage_uid)}
