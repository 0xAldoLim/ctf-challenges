import uuid

from models.billing import Billing
from models.published_record import PublishedRestoreRecord
from models.processor import Processor
from models.storage import Storage
from resource.default import DefaultResource

from app.processor.apply import apply_processor
from app.processor.configure import schedule_processor_setup
from app.processor.health import run_processor_status
from app.processor.published_records import (
    publish_archive_record,
    resolve_published_archive_value,
)
from app.processor.profile import build_processor_scope
from app.processor_config import load_processor_scope


class ProcessorResource(DefaultResource):
    def _billing(self, user, billing_id: str) -> Billing | None:
        return (
            self._db_session.query(Billing)
            .filter_by(uid=billing_id, user_id=user.id)
            .first()
        )

    def _storage(self, billing: Billing, storage_name: str) -> Storage | None:
        return (
            self._db_session.query(Storage)
            .filter_by(billing_id=billing.id, name=storage_name)
            .first()
        )

    def _processor(self, user, billing: Billing, storage: Storage, processor_ref: str):
        return (
            self._db_session.query(Processor)
            .filter_by(
                uid=processor_ref,
                user_id=user.id,
                billing_id=billing.id,
                storage_id=storage.id,
            )
            .first()
        )

    def _lookup(
        self, user, billing_id: str, storage_name: str, processor_ref: str = ""
    ):
        billing = self._billing(user, billing_id)
        if not billing:
            raise LookupError("No such billing account")
        storage = self._storage(billing, storage_name)
        if not storage:
            raise RuntimeError("Operation failed")
        processor = None
        if processor_ref:
            processor = self._processor(user, billing, storage, processor_ref)
            if not processor:
                raise RuntimeError("Operation failed")
        return billing, storage, processor

    def configure(
        self, user, billing_id: str, storage_name: str, mode: str, profile_json: str
    ):
        if mode not in {"audit", "compact", "restore"}:
            raise ValueError("Not enough arguments provided")
        billing, storage, _ = self._lookup(user, billing_id, storage_name)
        processor_ref = str(uuid.uuid4())
        scope_json, scope = build_processor_scope(
            user,
            billing,
            storage,
            processor_ref,
            mode,
            profile_json,
        )
        processor = Processor(
            uid=processor_ref,
            user_id=user.id,
            billing_id=billing.id,
            storage_id=storage.id,
            mode=mode,
            state="configured",
            scope_json=scope_json,
        )
        self._db_session.add(processor)
        self._db_session.commit()
        schedule_processor_setup(scope)
        return processor_ref, processor.state

    def apply(
        self,
        user,
        billing_id: str,
        storage_name: str,
        processor_ref: str,
        action: str,
        metadata,
    ):
        _, storage, processor = self._lookup(
            user, billing_id, storage_name, processor_ref
        )
        state, message = apply_processor(processor, storage, action, metadata)
        processor.state = state
        self._db_session.add(processor)
        self._db_session.commit()
        return state, message

    def status(self, user, billing_id: str, storage_name: str, processor_ref: str):
        _, storage, processor = self._lookup(
            user, billing_id, storage_name, processor_ref
        )
        state, summary = run_processor_status(
            load_processor_scope(processor.scope_json),
            storage.uid,
        )
        processor.state = state
        self._db_session.add(processor)
        self._db_session.commit()
        return state, summary

    def publish_archive_records(self, user, billing: Billing, storage: Storage) -> None:
        processors = (
            self._db_session.query(Processor)
            .filter_by(user_id=user.id, billing_id=billing.id, storage_id=storage.id)
            .all()
        )
        for processor in processors:
            try:
                record = publish_archive_record(user, billing, storage, processor)
            except Exception:
                continue
            if not record:
                continue
            key, descriptor_json = record
            exists = (
                self._db_session.query(PublishedRestoreRecord)
                .filter_by(storage_id=storage.id, key=key)
                .first()
            )
            if exists:
                continue
            self._db_session.add(
                PublishedRestoreRecord(
                    storage_id=storage.id,
                    key=key,
                    descriptor_json=descriptor_json,
                )
            )
        self._db_session.commit()

    def published_archive_keys(self, storage: Storage) -> list[str]:
        return [
            record.key
            for record in self._db_session.query(PublishedRestoreRecord)
            .filter_by(storage_id=storage.id)
            .all()
        ]

    def load_published_archive_record(self, storage: Storage, key: str) -> str | None:
        record = (
            self._db_session.query(PublishedRestoreRecord)
            .filter_by(storage_id=storage.id, key=key)
            .first()
        )
        if not record:
            return None
        return resolve_published_archive_value(record.descriptor_json)


processor_resource = ProcessorResource()
