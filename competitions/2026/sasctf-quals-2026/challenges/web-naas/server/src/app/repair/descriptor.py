import json
from dataclasses import dataclass
from typing import Any

from app.processor_config.scope import stable_token


@dataclass
class RepairDescriptor:
    descriptor: dict[str, Any]

    def read_text(self) -> str:
        report = {
            "case": str(self.descriptor.get("case") or ""),
            "probe": str(self.descriptor.get("probe") or ""),
            "hold": str(self.descriptor.get("hold") or ""),
            "interlock": str(self.descriptor.get("interlock") or ""),
            "status": "ready",
        }
        return json.dumps(report, sort_keys=True, separators=(",", ":"))[:4096]


def prepare_descriptor(
    descriptor: dict,
    *,
    storage_uid: str,
    processor_uid: str,
    restore_ref_value: str,
) -> RepairDescriptor:
    if not isinstance(descriptor, dict):
        raise ValueError("repair unavailable")
    probe = "archive-integrity"
    allowed = {
        "case",
        "hold",
        "interlock",
        "kind",
        "probe",
        "processor_uid",
        "storage_uid",
        "token",
    }
    if any(key not in allowed for key in descriptor):
        raise ValueError("repair unavailable")
    expected = stable_token(
        "repair.v3",
        {
            "case": restore_ref_value,
            "storage_uid": storage_uid,
            "processor_uid": processor_uid,
            "probe": probe,
        },
    )
    if descriptor.get("kind") != "archive-repair":
        raise ValueError("repair unavailable")
    if descriptor.get("probe") != probe:
        raise ValueError("repair unavailable")
    if descriptor.get("hold") != "released":
        raise ValueError("repair unavailable")
    if descriptor.get("interlock") != "released":
        raise ValueError("repair unavailable")
    if descriptor.get("case") != restore_ref_value:
        raise ValueError("repair unavailable")
    if descriptor.get("storage_uid") != storage_uid:
        raise ValueError("repair unavailable")
    if descriptor.get("processor_uid") != processor_uid:
        raise ValueError("repair unavailable")
    if descriptor.get("token") != expected:
        raise ValueError("repair unavailable")
    return RepairDescriptor(descriptor)


def open_descriptor(descriptor: dict) -> RepairDescriptor:
    return prepare_descriptor(
        descriptor,
        storage_uid=str(descriptor.get("storage_uid") or ""),
        processor_uid=str(descriptor.get("processor_uid") or ""),
        restore_ref_value=str(descriptor.get("case") or ""),
    )
