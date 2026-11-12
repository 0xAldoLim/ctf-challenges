import json
import time
from collections.abc import Mapping
from typing import Any

from fsspec.implementations.reference import ReferenceFileSystem

MAX_DESCRIPTOR_BYTES = 16 * 1024


def _descriptor_name(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("active", "current", "primary", "default"):
            try:
                item = value.get(key)
            except Exception:
                item = None
            if item is not None:
                return str(item)
        return str(value)
    return str(value or "")


def _read_from_reference(reference_map, name: str) -> str:
    fs = ReferenceFileSystem(reference_map)
    try:
        data = fs.cat_file(name)
    except Exception:
        with fs.open(name, "rb") as handle:
            data = handle.read(MAX_DESCRIPTOR_BYTES + 1)
    if isinstance(data, str):
        text = data
    else:
        if len(data) > MAX_DESCRIPTOR_BYTES:
            raise ValueError("descriptor unavailable")
        text = bytes(data).decode(errors="ignore")
    if len(text.encode()) > MAX_DESCRIPTOR_BYTES:
        raise ValueError("descriptor unavailable")
    return text


def resolve_descriptor(
    reference_map,
    descriptor_ref,
    *,
    storage_uid: str,
    processor_uid: str,
    restore_ref_value: str,
) -> dict:
    name = _descriptor_name(descriptor_ref)
    try:
        if reference_map is not None:
            raw = _read_from_reference(reference_map, name)
        else:
            raw = name
            if not raw.startswith("{") or len(raw.encode()) > MAX_DESCRIPTOR_BYTES:
                raise ValueError("descriptor unavailable")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("descriptor unavailable")
        data.setdefault("storage_uid", storage_uid)
        data.setdefault("processor_uid", processor_uid)
        data.setdefault("case", restore_ref_value)
        data.setdefault("resolved_at", int(time.time()))
        return data
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("descriptor unavailable") from exc
