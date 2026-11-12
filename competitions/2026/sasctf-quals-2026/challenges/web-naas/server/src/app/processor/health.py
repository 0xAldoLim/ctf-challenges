import hashlib

from arq.worker import FailedJobs, Worker

from app.background.jobs import health_check
from app.background.queue import (
    compressed_snapshot_deserializer,
    compressed_snapshot_serializer,
    pool,
    redis_settings,
    run_sync,
)
from app.storage import storage_report

from .formatting import format_size

DIAGNOSTIC_QUEUE = "queue:public:diagnostic"


def _clean(message: str) -> str:
    return " ".join(message.splitlines()).strip()[:96]


def _digest(message: str) -> str:
    return hashlib.blake2s(_clean(message).encode(), digest_size=8).hexdigest()


def degraded_summary(message: str) -> str:
    return f"provider diagnostics degraded: {_digest(message)}"


async def _check(scope: dict):
    redis = await pool(DIAGNOSTIC_QUEUE)
    try:
        await redis.enqueue_job(
            "health_check",
            scope,
            _queue_name=DIAGNOSTIC_QUEUE,
            _job_id=None,
            _expires=30,
        )
        worker = Worker(
            [health_check],
            queue_name=DIAGNOSTIC_QUEUE,
            redis_settings=redis_settings(),
            redis_pool=redis,
            burst=True,
            handle_signals=False,
            max_burst_jobs=1,
            job_timeout=2,
            keep_result=60,
            job_serializer=compressed_snapshot_serializer,
            job_deserializer=compressed_snapshot_deserializer,
            log_results=False,
        )
        try:
            await getattr(worker, "run_" + "check")()
            return "ready", "processor diagnostics completed"
        except FailedJobs as exc:
            return "degraded", degraded_summary(str(exc))
        finally:
            await worker.close()
    finally:
        await redis.close()


def run_channel_check(scope: dict):
    try:
        return run_sync(_check(scope))
    except Exception as exc:
        return "degraded", degraded_summary(exc.__class__.__name__)


def run_processor_status(scope: dict, storage_uid: str):
    mode = str(scope.get("mode") or "")
    if mode == "compact":
        try:
            report = storage_report(storage_uid)
            return (
                "ready",
                "storage compaction status: "
                f"keys={report['keys']} size={format_size(report['size'])}",
            )
        except Exception as exc:
            return "degraded", degraded_summary(exc.__class__.__name__)
    if mode == "restore":
        state, summary = run_channel_check(scope)
        if state == "ready":
            return "ready", "restore diagnostics completed"
        return state, summary
    return run_channel_check(scope)
