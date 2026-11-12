from app.storage import create_storage, get_key, list_keys, set_key


class Storage:
    def create(self, storage_id: str, name: str | None = None) -> None:
        create_storage(storage_id)

    def get_keys(self, storage_id: str) -> list[str]:
        return list_keys(storage_id)

    def set(self, storage_id: str, key: str, value: str) -> None:
        set_key(storage_id, key, value)

    def get(self, storage_id: str, key: str) -> str:
        value = get_key(storage_id, key)
        if value is None:
            raise Exception("No such key")
        return value


storage_util = Storage()
