from sqlalchemy import select

from utils.database import Session
from resource.default import DefaultResource
from models.billing import Billing
from models.storage import Storage
from app.storage import (
    create_storage,
    get_key,
    list_keys,
    new_storage_identifier,
    set_key,
)


class StorageResource(DefaultResource):
    def create(self, billing: Billing, _name: str) -> Storage:
        if (
            self._db_session.query(Storage)
            .filter_by(billing_id=billing.id, name=_name)
            .first()
        ):
            raise Exception("Storage with this name already exists")

        _uid = new_storage_identifier()
        new_storage: Storage = Storage(name=_name, billing_id=billing.id, uid=_uid)
        self._db_session.add(new_storage)

        create_storage(_uid)
        self._db_session.commit()
        return new_storage

    def get_storage(self, billing: Billing, _name: str) -> Storage | None:
        return (
            self._db_session.query(Storage)
            .filter_by(billing_id=billing.id, name=_name)
            .first()
        )

    def get_storage_read(self, billing: Billing, _name: str) -> Storage | None:
        session = Session()
        try:
            return (
                session.query(Storage)
                .filter_by(billing_id=billing.id, name=_name)
                .first()
            )
        finally:
            session.close()

    def keys(self, billing: Billing, _name: str) -> list[str]:
        storage: Storage = self.get_storage_read(billing, _name)
        if not storage:
            raise Exception("Storage with this name doesn't exists")

        return list_keys(storage.uid)

    def get(self, billing: Billing, _name: str, _key: str) -> str:
        storage: Storage = self.get_storage_read(billing, _name)
        if not storage:
            raise Exception("Storage with this name doesn't exists")

        value = get_key(storage.uid, _key)
        if value is None:
            raise Exception("No such key")
        return value

    def set(self, billing: Billing, _name: str, _key: str, _value: str) -> str:
        storage: Storage = self.get_storage(billing, _name)
        if not storage:
            raise Exception("Storage with this name doesn't exists")

        return set_key(storage.uid, _key, _value)

    def list(self, billing: Billing) -> list[str]:
        try:
            return self._db_session.scalars(
                select(Storage.name).filter_by(billing_id=billing.id)
            ).all()
        except Exception:
            self._db_session.rollback()
            raise


storage_resource = StorageResource()
