RESTORE_REF_KEY = "x-cloud-restore-ref-bin"
RESTORE_SOURCE_URL_KEY = "x-cloud-restore-source-url"
ATTESTATION_KEY = "x-cloud-attestation-bin"
MAX_FRAME_BYTES = 512 * 1024
MAX_ATTESTATION_BYTES = 16 * 1024


def read_binary_value(
    metadata, selected_key: str, limit: int = MAX_FRAME_BYTES
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for key, value in metadata or []:
        if key != selected_key:
            continue
        part = value if isinstance(value, bytes) else str(value).encode()
        total += len(part)
        if total > limit:
            raise ValueError("transport metadata is too large")
        chunks.append(part)
    return b"".join(chunks)


def read_attestation(metadata) -> bytes:
    return read_binary_value(metadata, ATTESTATION_KEY, MAX_ATTESTATION_BYTES)


def read_restore_ref(metadata) -> str:
    value = read_binary_value(metadata, RESTORE_REF_KEY, 4096)
    return value.decode(errors="ignore").strip()


def read_restore_source_url(metadata) -> str:
    value = read_binary_value(metadata, RESTORE_SOURCE_URL_KEY, 4096)
    return value.decode(errors="ignore").strip()
