from arq.jobs import Job

from app.processor_config.scope import stable_token

from app.background.jobs import (
    ARCHIVE_RESTORE_PRICE_CODE,
    PREVIEW_PRICE_CODE,
)
from app.background.queue import (
    PRIVATE_QUEUE,
    PUBLIC_QUEUE,
    compressed_snapshot_deserializer,
    pool,
    run_sync,
)
from app.restore_session.state import cron_refs

JOB_EXPIRES_SECONDS = 0.5
PUBLIC_RECEIPT_DEFER_SECONDS = 0.65
PUBLIC_RECEIPT_LEASE_SECONDS = 0.25
PRIVATE_APPROVAL_NOT_BEFORE_SECONDS = 1.0
PRIVATE_APPROVAL_LEASE_SECONDS = 5


def billing_identity_scope(scope: dict) -> dict:
    return {
        key: value
        for key, value in scope.items()
        if key
        not in {
            "billing_class",
            "authorization_amount",
            "price_code",
        }
    }


def preview_job_id(scope: dict) -> str:
    return stable_token("billing.preview", billing_identity_scope(scope))


def archive_approval_job_id(scope: dict) -> str:
    return stable_token("billing.approval", billing_identity_scope(scope))


async def _request_billing_preview(scope: dict) -> bool:
    redis = await pool(PRIVATE_QUEUE)
    try:
        job = await redis.enqueue_job(
            "billing_preview_check",
            scope,
            PREVIEW_PRICE_CODE,
            _queue_name=PRIVATE_QUEUE,
            _job_id=preview_job_id(scope),
            _expires=JOB_EXPIRES_SECONDS,
        )
        if job is None:
            return False
        try:
            result = await job.result(timeout=0.8, poll_delay=0.05)
        except TimeoutError:
            return False
        return bool(result.get("accepted"))
    finally:
        await redis.close()


def request_billing_preview(scope: dict) -> bool:
    return run_sync(_request_billing_preview(scope))


async def _reserve_archive_approval(scope: dict) -> bool:
    redis = await pool(PUBLIC_QUEUE)
    try:
        job = await redis.enqueue_job(
            "archive_approval_receipt",
            scope,
            PREVIEW_PRICE_CODE,
            _queue_name=PUBLIC_QUEUE,
            _job_id=archive_approval_job_id(scope),
            _defer_by=PUBLIC_RECEIPT_DEFER_SECONDS,
            _expires=PUBLIC_RECEIPT_LEASE_SECONDS,
        )
        return job is not None
    finally:
        await redis.close()


def reserve_archive_approval(scope: dict) -> bool:
    return run_sync(_reserve_archive_approval(scope))


async def _authorize_archive_restore(scope: dict) -> bool:
    redis = await pool(PRIVATE_QUEUE)
    try:
        job = await redis.enqueue_job(
            "archive_approval_receipt",
            scope,
            ARCHIVE_RESTORE_PRICE_CODE,
            _queue_name=PRIVATE_QUEUE,
            _job_id=archive_approval_job_id(scope),
            _defer_by=PRIVATE_APPROVAL_NOT_BEFORE_SECONDS,
            _expires=PRIVATE_APPROVAL_LEASE_SECONDS,
        )
        if job is None:
            return False
        try:
            result = await job.result(timeout=7.5, poll_delay=0.05)
        except TimeoutError:
            return False
        return bool(result.get("accepted"))
    finally:
        await redis.close()


def authorize_archive_restore(scope: dict) -> bool:
    return run_sync(_authorize_archive_restore(scope))


async def _submit_restore_checkpoint(scope: dict, restore_ref_value: str) -> bool:
    from app.processor_config.scope import restore_ref

    if restore_ref_value != restore_ref(scope):
        return False
    redis = await pool(PUBLIC_QUEUE)
    try:
        jobs = []
        for item_ref in cron_refs(6, back_seconds=6):
            job = await redis.enqueue_job(
                "restore_checkpoint",
                scope,
                restore_ref_value,
                _queue_name=PUBLIC_QUEUE,
                _job_id=item_ref,
                _expires=30,
            )
            if job is not None:
                jobs.append(job)
        if not jobs:
            return await _restore_checkpoint_ready()
        ready = False
        for job in jobs:
            try:
                result = await job.result(timeout=1.5, poll_delay=0.05)
                if result.get("state") == "ready":
                    ready = True
            except Exception:
                continue
        return ready
    finally:
        await redis.close()


def submit_restore_checkpoint(scope: dict, restore_ref_value: str) -> bool:
    return run_sync(_submit_restore_checkpoint(scope, restore_ref_value))


async def _restore_checkpoint_ready() -> bool:
    redis = await pool(PUBLIC_QUEUE)
    try:
        for item_ref in cron_refs(45, back_seconds=45):
            try:
                job = Job(
                    item_ref,
                    redis,
                    _queue_name=PUBLIC_QUEUE,
                    _deserializer=compressed_snapshot_deserializer,
                )
                result = await job.result(timeout=0.2, poll_delay=0.02)
                if result:
                    return True
            except Exception:
                continue
        return False
    finally:
        await redis.close()


def restore_checkpoint_ready() -> bool:
    return run_sync(_restore_checkpoint_ready())


def archive_approval_ready(scope: dict) -> bool:
    async def _check() -> bool:
        redis = await pool(PRIVATE_QUEUE)
        try:
            job = Job(
                archive_approval_job_id(scope),
                redis,
                _queue_name=PRIVATE_QUEUE,
                _deserializer=compressed_snapshot_deserializer,
            )
            result = await job.result(timeout=0.2, poll_delay=0.02)
            return bool(result and result.get("accepted"))
        except Exception:
            return False
        finally:
            await redis.close()

    return run_sync(_check())
