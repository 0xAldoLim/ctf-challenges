from arq.worker import func

from app.background.jobs import (
    health_check,
    public_archive_approval_receipt,
    restore_checkpoint,
)
from app.background.queue import (
    PUBLIC_QUEUE,
    compressed_snapshot_deserializer,
    compressed_snapshot_serializer,
    redis_settings,
)


class WorkerSettings:
    functions = [
        health_check,
        restore_checkpoint,
        func(public_archive_approval_receipt, name="archive_approval_receipt"),
    ]
    queue_name = PUBLIC_QUEUE
    redis_settings = redis_settings()
    job_serializer = compressed_snapshot_serializer
    job_deserializer = compressed_snapshot_deserializer
    keep_result = 60
    max_jobs = 10
    job_timeout = 5
    log_results = False
