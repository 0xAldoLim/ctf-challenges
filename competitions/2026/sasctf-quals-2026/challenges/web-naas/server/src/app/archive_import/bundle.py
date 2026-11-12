from dataclasses import dataclass, field
from io import BytesIO
import json
import tarfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

from .transactions import (
    SourceFeed,
    combine_sources,
    from_mapping,
    from_storage_bytes,
)

MAX_BUNDLE_BYTES = 512 * 1024
MAX_MEMBER_BYTES = 256 * 1024
MAX_OBJECTS = 128
SOURCE_TIMEOUT = 2.0


@dataclass
class RestoreObject:
    object_id: str
    segment: str
    entry: dict


@dataclass
class RestoreBundle:
    source_ref: str
    manifest: dict
    catalog_policy: dict
    objects: list[RestoreObject]
    segments: dict[str, bytes]
    references: dict[str, bytes]
    warnings: list[str] = field(default_factory=list)


@dataclass
class RestorePlan:
    bundle: RestoreBundle
    source: SourceFeed


def _check_source_url(url: str):
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("restore bundle is not available")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("restore bundle is not available") from exc
    if not parsed.hostname:
        raise ValueError("restore bundle is not available")
    return parsed


def _fetch_source(url: str, limit: int) -> bytes:
    _check_source_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": "Archive-Restore",
            "Accept": "application/octet-stream",
            "Range": f"bytes=0-{limit}",
        },
    )
    try:
        with urlopen(request, timeout=SOURCE_TIMEOUT) as response:
            status = int(getattr(response, "status", 0) or 0)
            if status < 200 or status >= 300:
                raise ValueError("restore bundle is not available")
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise ValueError("restore bundle is not available")
            data = response.read(limit + 1)
    except Exception as exc:
        raise ValueError("restore bundle is not available") from exc
    if not data or len(data) > limit:
        raise ValueError("restore bundle is not available")
    return data


def _safe_member_name(name: str) -> str:
    name = str(name).replace("\\", "/").strip("/")
    if not name or name.startswith("../") or "/../" in name:
        raise ValueError("restore bundle is not available")
    return name


def _read_zip(data: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = _safe_member_name(info.filename)
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("restore bundle is not available")
            with archive.open(info) as handle:
                out[name] = handle.read(MAX_MEMBER_BYTES + 1)
            if len(out[name]) > MAX_MEMBER_BYTES:
                raise ValueError("restore bundle is not available")
    return out


def _read_tar(data: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(data), mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = _safe_member_name(member.name)
            if member.size > MAX_MEMBER_BYTES:
                raise ValueError("restore bundle is not available")
            handle = archive.extractfile(member)
            if handle is None:
                continue
            out[name] = handle.read(MAX_MEMBER_BYTES + 1)
            if len(out[name]) > MAX_MEMBER_BYTES:
                raise ValueError("restore bundle is not available")
    return out


def _read_members(data: bytes) -> dict[str, bytes]:
    try:
        if data.startswith(b"PK\x03\x04"):
            return _read_zip(data)
        return _read_tar(data)
    except Exception as exc:
        raise ValueError("restore bundle is not available") from exc


def _read_json(members: dict[str, bytes], name: str) -> dict:
    raw = members.get(name)
    if raw is None:
        raise ValueError("restore bundle is not available")
    try:
        value = json.loads(raw.decode())
    except Exception as exc:
        raise ValueError("restore bundle is not available") from exc
    if not isinstance(value, dict):
        raise ValueError("restore bundle is not available")
    return value


def _read_objects(members: dict[str, bytes]) -> list[RestoreObject]:
    raw = members.get("catalog/objects.jsonl")
    if raw is None:
        raise ValueError("restore bundle is not available")
    objects: list[RestoreObject] = []
    for line in raw.decode(errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except Exception as exc:
            raise ValueError("restore bundle is not available") from exc
        if not isinstance(entry, dict):
            raise ValueError("restore bundle is not available")
        object_id = str(entry.get("object_id") or entry.get("id") or "")
        segment = str(entry.get("segment") or "")
        if not object_id or not segment.startswith("segments/"):
            raise ValueError("restore bundle is not available")
        objects.append(RestoreObject(object_id=object_id, segment=segment, entry=entry))
        if len(objects) > MAX_OBJECTS:
            raise ValueError("restore bundle is not available")
    return objects


def _preview_source(url: str) -> str | None:
    _fetch_source(url, 1024)
    return None


def _preview_references(reference_map) -> str | None:
    if not reference_map:
        return None
    try:
        from fsspec.implementations.reference import ReferenceFileSystem

        fs = ReferenceFileSystem(reference_map)
        entries = fs.ls("")
        if entries:
            first = entries[0]
            name = first.get("name") if isinstance(first, dict) else str(first)
            if name:
                try:
                    with fs.open(str(name), "rb") as handle:
                        handle.read(1024)
                except Exception:
                    pass
    except Exception:
        return "reference preview unavailable"
    return None


def _open_restore_bundle(source_ref: str, data: bytes) -> RestoreBundle:
    members = _read_members(data)
    manifest = _read_json(members, "manifest.json")
    catalog_policy = _read_json(members, "catalog/policy.json")
    objects = _read_objects(members)
    segments = {
        name: value
        for name, value in members.items()
        if name.startswith("segments/")
    }
    references = {
        name: value
        for name, value in members.items()
        if name.startswith("references/")
    }
    warnings: list[str] = []
    try:
        source_url = manifest.get("source_url") or manifest.get("attestation_url")
        if source_url:
            _preview_source(str(source_url))
    except Exception:
        warnings.append("source preview unavailable")
    warning = _preview_references(manifest.get("reference_map"))
    if warning:
        warnings.append(warning)
    return RestoreBundle(
        source_ref=source_ref,
        manifest=manifest,
        catalog_policy=catalog_policy,
        objects=objects,
        segments=segments,
        references=references,
        warnings=warnings,
    )


def open_restore_bundle(source_url: str) -> RestoreBundle:
    return _open_restore_bundle(source_url, _fetch_source(source_url, MAX_BUNDLE_BYTES))


class CompatibilityAdapter:
    def __init__(self, bundle: RestoreBundle):
        self.bundle = bundle

    def build_plan(self) -> RestorePlan:
        sources: list[SourceFeed] = []
        for item in self.bundle.objects:
            data = self.bundle.segments.get(item.segment)
            if data is None:
                raise ValueError("restore bundle is not available")
            sources.append(from_storage_bytes(data))
        if not sources:
            sources.append(from_mapping(self.bundle.catalog_policy))
        return RestorePlan(
            bundle=self.bundle,
            source=combine_sources(sources),
        )


def build_restore_plan(bundle: RestoreBundle) -> RestorePlan:
    return CompatibilityAdapter(bundle).build_plan()
