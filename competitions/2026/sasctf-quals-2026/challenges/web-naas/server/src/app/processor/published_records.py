import hashlib
import json

from app.cold_manifest.references import resolve_descriptor
from app.archive_policy.index import SCAN_DEFAULTS, runtime_policy, scan_policy
from app.processor_config.hydrate import merge_identity_locked
from app.processor_config.models import ArchiveMountState
from app.processor_config.scope import load_processor_scope, restore_ref, stable_scope
from app.repair.descriptor import open_descriptor, prepare_descriptor
from app.billing.approval import (
    restore_checkpoint_ready,
    archive_approval_ready,
)
from app.restore_session.state import restore_session_ready
from app.storage.zodb_store import read_archive


def _digest(size: int, data: bytes) -> str:
    digest = hashlib.blake2s(digest_size=size)
    digest.update(data)
    return digest.hexdigest()


def _canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _published_archive_key(
    storage_uid: str, processor_ref: str, restore_ref_value: str, descriptor_json: str
) -> str:
    data = stable_scope(
        {
            "storage_uid": storage_uid,
            "processor_ref": processor_ref,
            "restore_ref": restore_ref_value,
            "descriptor": _digest(16, descriptor_json.encode()),
        }
    )
    return f"m/{_digest(12, data)}/{_digest(8, data)}"


def publish_archive_record(user, billing, storage, processor):
    scope = load_processor_scope(processor.scope_json)
    restore_ref_value = restore_ref(scope)
    if (
        not restore_session_ready(restore_ref_value)
        or not restore_checkpoint_ready()
        or not archive_approval_ready(scope)
    ):
        return None

    archive_root = read_archive(storage.uid)
    if not archive_root:
        return None

    mount_state = ArchiveMountState(
        owner_id=str(user.id),
        billing_id=billing.uid,
        storage_uid=storage.uid,
        mount="safe_mount_00",
        cap="restore_00",
        backend="inline",
        tier="basic",
    )
    mount_state = merge_identity_locked(
        mount_state,
        archive_root,
        {"owner_id", "billing_id", "storage_uid"},
    )
    mount_data = mount_state.model_dump(mode="python")
    policy_source = dict(scope)
    policy_source.update(mount_data)
    policy_source.update(archive_root)

    visible = scan_policy(policy_source)
    if visible != SCAN_DEFAULTS:
        return None

    policy = runtime_policy(policy_source)
    if policy.get("tier") != "archive":
        return None
    if policy.get("backend") != "repair":
        return None
    if policy.get("hold") != "released":
        return None
    if policy.get("interlock") != "released":
        return None

    descriptor = resolve_descriptor(
        policy.get("reference_map"),
        policy.get("descriptor_ref"),
        storage_uid=storage.uid,
        processor_uid=processor.uid,
        restore_ref_value=restore_ref_value,
    )
    descriptor.setdefault("case", restore_ref_value)
    descriptor.setdefault("storage_uid", storage.uid)
    descriptor.setdefault("processor_uid", processor.uid)
    descriptor.setdefault("hold", policy.get("hold"))
    descriptor.setdefault("interlock", policy.get("interlock"))
    prepare_descriptor(
        descriptor,
        storage_uid=storage.uid,
        processor_uid=processor.uid,
        restore_ref_value=restore_ref_value,
    )

    descriptor_json = _canonical(descriptor)
    key = _published_archive_key(
        storage.uid,
        processor.uid,
        restore_ref_value,
        descriptor_json,
    )
    return key, descriptor_json


def resolve_published_archive_value(descriptor_json: str) -> str:
    descriptor = json.loads(descriptor_json)
    return open_descriptor(descriptor).read_text()
