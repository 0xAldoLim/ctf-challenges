from app.background.queue import PRIVATE_QUEUE, pool, run_sync
from app.processor_config.scope import restore_ref


async def _enqueue_processor_setup(scope: dict) -> None:
    if scope.get("mode") != "restore":
        return
    redis = await pool(PRIVATE_QUEUE)
    try:
        await redis.enqueue_job(
            "prepare_restore_session",
            scope,
            _queue_name=PRIVATE_QUEUE,
            _job_id=restore_ref(scope),
            _expires=120,
        )
    finally:
        await redis.close()


def schedule_processor_setup(scope: dict) -> bool:
    try:
        run_sync(_enqueue_processor_setup(scope))
        return True
    except Exception:
        return False
