from app.processor_config.scope import load_processor_scope, restore_ref
from app.archive_import.bundle import build_restore_plan, open_restore_bundle
from app.archive_import.materialize import materialize_restore_plan
from app.archive_import.validators import validate_catalog, validate_manifest
from app.billing.approval import (
    authorize_archive_restore,
    request_billing_preview,
    reserve_archive_approval,
    restore_checkpoint_ready,
    submit_restore_checkpoint,
)
from app.restore_session.state import restore_session_ready
from app.storage import compact_storage, storage_report

from .formatting import format_size
from .metadata import read_restore_ref, read_restore_source_url


def _not_available() -> tuple[str, str]:
    return "rejected", "processor action is not available for this mode"


def apply_processor(processor, storage, action: str, metadata):
    scope = load_processor_scope(processor.scope_json)
    mode = str(scope.get("mode") or "")
    action = str(action or "").strip()

    if mode == "audit":
        if action == "dry-run":
            return "ready", "diagnostics preview ready"
        return _not_available()

    if mode == "compact":
        if action == "dry-run":
            report = storage_report(storage.uid)
            return (
                "ready",
                "storage compaction preview: "
                f"keys={report['keys']} size={format_size(report['size'])}",
            )
        if action == "compact":
            result = compact_storage(storage.uid)
            return (
                "ready",
                "storage compaction completed: "
                f"{format_size(result['before'])} -> {format_size(result['after'])}",
            )
        return _not_available()

    if mode != "restore":
        return _not_available()

    if action == "dry-run":
        accepted = request_billing_preview(scope)
        if accepted:
            return "ready", "billing preview ready"
        return "pending", "billing preview pending"

    if action == "authorize":
        accepted = reserve_archive_approval(scope)
        if accepted:
            return "ready", "Archive Pro authorization ready"
        return "pending", "Archive Pro authorization pending"

    if action not in {"sync", "restore"}:
        return _not_available()

    restore_ref_value = read_restore_ref(metadata)
    if action == "sync":
        accepted = submit_restore_checkpoint(scope, restore_ref_value)
        if accepted:
            return "ready", "restore checkpoint ready"
        return "pending", "restore checkpoint pending"

    expected_restore_ref = restore_ref(scope)
    if restore_ref_value != expected_restore_ref:
        return "closed", "restore reference not accepted"

    if not restore_session_ready(expected_restore_ref) or not restore_checkpoint_ready():
        return "closed", "restore session or checkpoint pending"

    if not authorize_archive_restore(scope):
        return "pending", "Archive Pro authorization pending"

    source_url = read_restore_source_url(metadata)
    if not source_url:
        return "pending", "restore source URL required"
    bundle = open_restore_bundle(source_url)
    validate_manifest(bundle, scope)
    plan = build_restore_plan(bundle)
    validate_catalog(bundle, plan)
    materialize_restore_plan(plan, storage.uid)
    return "applied", "restore bundle accepted"
