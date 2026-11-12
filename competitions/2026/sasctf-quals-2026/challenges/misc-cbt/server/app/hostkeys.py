from pathlib import Path

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.settings import AppSettings


def _write_ed25519_key(path: Path) -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    data = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(data)
    path.chmod(0o600)


def load_host_keys(settings: AppSettings) -> list[paramiko.PKey]:
    hostkey_dir = settings.hostkey_dir
    hostkey_dir.mkdir(parents=True, exist_ok=True)
    keys: list[paramiko.PKey] = []

    ed_path = hostkey_dir / "ssh_host_ed25519_key"
    if not ed_path.exists():
        _write_ed25519_key(ed_path)
    keys.append(paramiko.Ed25519Key.from_private_key_file(str(ed_path)))

    rsa_path = hostkey_dir / "ssh_host_rsa_key"
    if not rsa_path.exists():
        rsa = paramiko.RSAKey.generate(settings.rsa_key_bits)
        rsa.write_private_key_file(str(rsa_path))
    keys.append(paramiko.RSAKey.from_private_key_file(str(rsa_path)))

    return keys
