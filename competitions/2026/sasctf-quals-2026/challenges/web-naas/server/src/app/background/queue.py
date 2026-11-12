import asyncio
import pickle
from typing import Any
from urllib.parse import urlparse
import zlib

from arq import create_pool
from arq.connections import RedisSettings
import msgpack

from utils.config import app_config

PUBLIC_QUEUE = "queue:public"
PRIVATE_QUEUE = "queue:private"


def redis_settings() -> RedisSettings:
    parsed = urlparse(app_config.REDIS_URL)
    database = int((parsed.path or "/0").lstrip("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        username=parsed.username,
        password=parsed.password,
    )


def compressed_snapshot_serializer(payload: dict[str, Any]) -> bytes:
    try:
        packed = b"M" + msgpack.packb(payload, use_bin_type=True, strict_types=False)
    except Exception:
        packed = b"P" + pickle.dumps(payload)
    return zlib.compress(packed)


def compressed_snapshot_deserializer(payload: bytes) -> dict[str, Any]:
    packed = zlib.decompress(payload)
    if packed.startswith(b"M"):
        return msgpack.unpackb(packed[1:], raw=False)
    if packed.startswith(b"P"):
        return pickle.loads(packed[1:])
    return msgpack.unpackb(packed, raw=False)


async def pool(queue_name: str):
    return await create_pool(
        redis_settings(),
        job_serializer=compressed_snapshot_serializer,
        job_deserializer=compressed_snapshot_deserializer,
        default_queue_name=queue_name,
    )


def run_sync(coro):
    return asyncio.run(coro)
