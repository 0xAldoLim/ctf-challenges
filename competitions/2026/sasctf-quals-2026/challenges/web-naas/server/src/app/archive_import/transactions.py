from contextlib import contextmanager
from dataclasses import dataclass
import os
import tempfile
from typing import Iterator

import transaction
import ZODB
from ZODB.FileStorage import FileStorage


@dataclass
class SourceRecord:
    oid: bytes
    tid: bytes
    data: bytes
    version: bytes = b""
    data_txn: bytes | None = None


@dataclass
class SourceTransaction:
    tid: bytes
    user: bytes
    description: bytes
    extension_bytes: bytes
    records: list[SourceRecord]
    status: bytes = b" "

    def __iter__(self):
        return iter(self.records)


class SourceFeed:
    def __init__(self, transactions: list[SourceTransaction]):
        self.transactions = transactions

    def iterator(self):
        return iter(self.transactions)


def _clear(path: str) -> None:
    for suffix in ("", ".index", ".lock", ".tmp", ".old"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


@contextmanager
def _temporary_path() -> Iterator[str]:
    fd, path = tempfile.mkstemp(suffix=".fs")
    os.close(fd)
    os.remove(path)
    try:
        yield path
    finally:
        _clear(path)


def _snapshot(path: str) -> SourceFeed:
    storage = FileStorage(path, read_only=True)
    try:
        transactions: list[SourceTransaction] = []
        for entry in storage.iterator():
            records = [
                SourceRecord(
                    oid=record.oid,
                    tid=record.tid,
                    data=record.data,
                    version=record.version,
                    data_txn=record.data_txn,
                )
                for record in entry
            ]
            transactions.append(
                SourceTransaction(
                    tid=entry.tid,
                    user=entry.user,
                    description=entry.description,
                    extension_bytes=entry.extension_bytes,
                    records=records,
                )
            )
        return SourceFeed(transactions)
    finally:
        storage.close()


def from_mapping(mapping: dict) -> SourceFeed:
    with _temporary_path() as path:
        storage = FileStorage(path)
        db = ZODB.DB(storage)
        conn = db.open()
        try:
            root = conn.root()
            root.clear()
            for key, value in mapping.items():
                root[str(key)] = value
            transaction.commit()
        finally:
            conn.close()
            db.close()
            storage.close()
        return _snapshot(path)


def from_storage_bytes(data: bytes) -> SourceFeed:
    with _temporary_path() as path:
        with open(path, "wb") as handle:
            handle.write(data)
        return _snapshot(path)


def combine_sources(sources: list[SourceFeed]) -> SourceFeed:
    transactions: list[SourceTransaction] = []
    for source in sources:
        transactions.extend(source.transactions)
    return SourceFeed(transactions)


def copy_to_path(source: SourceFeed, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _clear(path)
    storage = FileStorage(path)
    try:
        getattr(storage, "copy" + "TransactionsFrom")(source)
    finally:
        storage.close()


def read_path(path: str) -> dict:
    storage = FileStorage(path)
    db = ZODB.DB(storage)
    conn = db.open()
    try:
        data = dict(conn.root().items())
        transaction.abort()
        return data
    finally:
        conn.close()
        db.close()
        storage.close()


def read_source(source: SourceFeed) -> dict:
    with _temporary_path() as path:
        copy_to_path(source, path)
        return read_path(path)
