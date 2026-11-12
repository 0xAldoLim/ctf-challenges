from contextlib import contextmanager
import os
import time
from typing import Iterator

import transaction
import ZODB
from ZODB.FileStorage import FileStorage

from .paths import archive_file, storage_dir, storage_file

CATALOG_KEY = ".catalog"


@contextmanager
def _root(path: str) -> Iterator[object]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fs = FileStorage(path)
    db = ZODB.DB(fs)
    conn = db.open()
    try:
        yield conn.root()
    finally:
        conn.close()
        db.close()
        fs.close()


def create_storage(uid: str) -> None:
    os.makedirs(storage_dir(uid), exist_ok=True)
    with _root(storage_file(uid)) as root:
        if CATALOG_KEY not in root:
            root[CATALOG_KEY] = {}
        transaction.commit()


def read_archive(uid: str) -> dict:
    with _root(archive_file(uid)) as root:
        data = dict(root.items())
        transaction.abort()
        return data


def list_keys(uid: str) -> list[str]:
    with _root(storage_file(uid)) as root:
        keys = [
            key
            for key in root.keys()
            if isinstance(key, str) and not key.startswith(".")
        ]
        transaction.abort()
        return keys


def set_key(uid: str, key: str, value: str) -> None:
    if key.startswith("."):
        raise ValueError("reserved key")
    with _root(storage_file(uid)) as root:
        root[key] = value
        transaction.commit()


def get_key(uid: str, key: str) -> str | None:
    if key.startswith("."):
        return None
    with _root(storage_file(uid)) as root:
        if key not in root:
            transaction.abort()
            return None
        value = root[key]
        transaction.abort()
        return str(value)


def storage_report(uid: str) -> dict[str, int]:
    path = storage_file(uid)
    if not os.path.exists(path):
        create_storage(uid)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    return {"size": size, "keys": len(list_keys(uid))}


def compact_storage(uid: str) -> dict[str, int]:
    path = storage_file(uid)
    if not os.path.exists(path):
        create_storage(uid)
    before = os.path.getsize(path) if os.path.exists(path) else 0
    fs = FileStorage(path)
    db = ZODB.DB(fs)
    try:
        db.pack(time.time())
    finally:
        db.close()
        fs.close()
    after = os.path.getsize(path) if os.path.exists(path) else 0
    return {"before": before, "after": after}
