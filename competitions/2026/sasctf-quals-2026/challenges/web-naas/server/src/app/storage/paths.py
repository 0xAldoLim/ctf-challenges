import os
import uuid


def _storage_root() -> str:
    return os.environ.get("APP_STORAGE_ROOT", os.path.abspath("storages"))


def _uid(value: str) -> str:
    return str(uuid.UUID(str(value)))


def storage_dir(uid: str) -> str:
    return os.path.join(_storage_root(), _uid(uid))


def storage_file(uid: str) -> str:
    return os.path.join(storage_dir(uid), "Data.fs")


def archive_file(uid: str) -> str:
    return os.path.join(storage_dir(uid), "Archive.fs")
