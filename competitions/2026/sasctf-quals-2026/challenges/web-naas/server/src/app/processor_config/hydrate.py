from collections.abc import Mapping
from typing import Any


def apply_patch(model, patch: Mapping[str, Any]):
    for key, value in patch.items():
        setattr(model, key, value)
    return model


def merge_identity_locked(model, patch: Mapping[str, Any], locked: set[str]):
    original = {key: getattr(model, key) for key in locked}
    for key, value in patch.items():
        setattr(model, key, value)
    for key, value in original.items():
        setattr(model, key, value)
    return model
