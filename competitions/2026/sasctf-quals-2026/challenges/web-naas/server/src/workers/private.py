from arq.cron import cron
from arq.worker import func

from app.background.jobs import (
    billing_preview_check,
    close_restore_session,
    prepare_restore_session,
    private_archive_approval_receipt,
    restore_audit,
)
from app.background.queue import (
    PRIVATE_QUEUE,
    compressed_snapshot_deserializer,
    compressed_snapshot_serializer,
    redis_settings,
)


class WorkerSettings:
    functions = [
        prepare_restore_session,
        close_restore_session,
        billing_preview_check,
        func(private_archive_approval_receipt, name="archive_approval_receipt"),
        restore_audit,
    ]
    cron_jobs = [
        cron(
            close_restore_session,
            name="restore.session.close",
            second={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            keep_result=0,
        )
    ]
    queue_name = PRIVATE_QUEUE
    redis_settings = redis_settings()
    job_serializer = compressed_snapshot_serializer
    job_deserializer = compressed_snapshot_deserializer
    keep_result = 120
    max_jobs = 10
    job_timeout = 12
    log_results = False
