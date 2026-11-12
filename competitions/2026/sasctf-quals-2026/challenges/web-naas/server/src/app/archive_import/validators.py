from app.archive_policy.index import scan_policy

from .bundle import RestoreBundle, RestorePlan


def _as_marker(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode()
    return bytes(value)


def _state_marker(value) -> None:
    marker = _as_marker(value)
    if marker == b" ":
        return
    raise ValueError("record is not available")


def _check_mapping(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("record is not available")
    visible = scan_policy(data)
    if visible.get("backend") not in {None, "inline"}:
        raise ValueError("record is not available")
    if visible.get("tier") not in {None, "basic"}:
        raise ValueError("record is not available")
    if visible.get("hold") not in {None, "pending"}:
        raise ValueError("record is not available")
    if visible.get("interlock") not in {None, "closed"}:
        raise ValueError("record is not available")


def validate_manifest(bundle: RestoreBundle, scope: dict) -> None:
    manifest = bundle.manifest
    if not isinstance(manifest.get("version", 1), int):
        raise ValueError("restore bundle is not available")
    mode = manifest.get("mode")
    if mode is not None and str(mode) != str(scope.get("mode") or ""):
        raise ValueError("restore bundle is not available")


def validate_catalog(bundle: RestoreBundle, plan: RestorePlan) -> None:
    _check_mapping(bundle.catalog_policy)
    for item in bundle.objects:
        if item.segment not in bundle.segments:
            raise ValueError("restore bundle is not available")
    for item in plan.source.transactions:
        _state_marker(item.status)
