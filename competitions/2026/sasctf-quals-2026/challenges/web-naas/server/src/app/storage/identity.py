import uuid


def new_storage_identifier() -> str:
    return str(uuid.uuid7())
