import argparse
import hashlib
import hmac
import json
import logging
import sys
import secrets
import socket
import ssl
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Tuple

from utils import *


MAGIC = b"cLIC"
VERSION = 1
HEADER_STRUCT = struct.Struct("<4sBBHI16sI")
TYPE_ERROR = 0
TYPE_ACTIVATE = 1
TOKEN_MAC_SIZE = 32
LOGGER = logging.getLogger("licsrv")
SUPPORTED_HOSTS = [
    "juce audio plugin host",
    "audiopluginhost",
    "carla-bridge-win64",
    "reaper",
    "protools",
    "cubase",
    "nuendo",
    "cakewalk",
    "vegas",
    "fruity wrapper",
    "samplitude",
    "live",
    "tracktion",
    "ntracks",
    "melodyne",
    "vstmanlib",
    "aulab",
    "forte",
    "chainer",
    "audition",
    "orion",
    "bias",
    "sawstudio",
    "logic",
    "garageband",
    "digital",
    "audiomulch",
    "presonus",
    "vst3plugintesthost",
    "ardour",
    "renoise",
    "openmpt",
    "wavelab elements",
    "wavelab",
    "twistedwave",
    "bitwig studio",
    "reason",
    "gwvst",
    "waveform",
    "audacity",
    "acoustica",
    "plugindoctor",
    "izotope rx",
    "savihost",
    "blue cat's vst host",
    "mixbus",
    "standalone"
]

@dataclass(frozen=True)
class Frame:
    msg_type: int
    request_id: int
    nonce: bytes
    ciphertext: bytes
    mac: bytes


@dataclass(frozen=True)
class ActivationRequestPayload:
    vst_host: int
    license_key: str
    hwid: str


@dataclass(frozen=True)
class ActivationSystem:
    dimensions: int
    matrix_gzip: bytes
    rhs_gzip: bytes


def _recv_exact(sock: ssl.SSLSocket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("peer closed the connection")
        chunks.extend(chunk)
    return bytes(chunks)


class BinaryReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def read_u32(self) -> int:
        return self._read_struct("<I")

    def read_i64(self) -> int:
        return self._read_struct("<q")

    def read_bytes(self) -> bytes:
        size = self.read_u32()
        return self.read_exact(size)

    def read_string(self) -> str:
        return self.read_bytes().decode("utf-8")

    def read_exact(self, size: int) -> bytes:
        if self._offset + size > len(self._data):
            raise ValueError("truncated binary payload")
        chunk = self._data[self._offset : self._offset + size]
        self._offset += size
        return chunk

    def ensure_consumed(self) -> None:
        if self._offset != len(self._data):
            raise ValueError("unexpected trailing payload bytes")

    def _read_struct(self, fmt: str) -> int:
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.read_exact(size))[0]


def _pack_u32(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


def _pack_bytes(value: bytes) -> bytes:
    return _pack_u32(len(value)) + value


def parse_activation_request(payload: bytes) -> ActivationRequestPayload:
    reader = BinaryReader(payload)
    vst_host = reader.read_string()
    license_key = reader.read_string()
    hwid = reader.read_string()
    reader.ensure_consumed()
    return ActivationRequestPayload(vst_host=vst_host, license_key=license_key, hwid=hwid)

def build_activation_response(
    snapshot: Mapping[str, object],
    hwid: str,
    signer: LicenseSigner
) -> bytes:
    buffer = bytearray()
        
    sys1 = snapshot["?1"]
    sys2 = snapshot["?2"]
    
    hwid_seed = hwid_seed_derive(hwid)
    
    serial1 = serialize_vector(sys1["r"], hwid_seed)
    serial2 = serialize_vector(sys2["r"], hwid_seed)

    buffer.extend(_pack_u32(int(sys1["d"])))
    buffer.extend(_pack_bytes(deflate(serial1)))
    buffer.extend(_pack_bytes(deflate(serial2)))
    
    offline_check = signer.hash(serial1 + serial2)
    signature = signer.sign(offline_check)
    
    buffer.extend(_pack_bytes(offline_check))
    buffer.extend(_pack_bytes(signature))
    
    return bytes(buffer)

def format_peer(peer: Tuple[str, int]) -> str:
    return f"{peer[0]}:{peer[1]}"

def summarize_certificate(cert: Mapping[str, object] | None) -> Dict[str, object]:
    if not cert:
        return {}
    return {
        "sub": cert.get("subject", ())[0][0][1],
        "iss": cert.get("issuer", ())[0][0][1],
        "sn": cert.get("serialNumber"),
        "nb": cert.get("notBefore"),
        "na": cert.get("notAfter"),
    }


def pack_frame(msg_type: int, request_id: int, payload: bytes, enc_key: bytes, mac_key: bytes) -> bytes:
    nonce = secrets.token_bytes(16)
    ciphertext = xor_stream_crypt(enc_key, nonce, payload)
    header = HEADER_STRUCT.pack(MAGIC, VERSION, msg_type, 0, request_id, nonce, len(ciphertext))
    mac = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    return header + ciphertext + mac


def unpack_frame(sock: ssl.SSLSocket, enc_key: bytes, mac_key: bytes) -> Tuple[Frame, bytes]:
    header = _recv_exact(sock, HEADER_STRUCT.size)
    magic, version, msg_type, _flags, request_id, nonce, payload_len = HEADER_STRUCT.unpack(header)
    if magic != MAGIC:
        raise ValueError("bad frame magic")
    if version != VERSION:
        raise ValueError(f"unsupported frame version: {version}")

    ciphertext = _recv_exact(sock, payload_len)
    mac = _recv_exact(sock, TOKEN_MAC_SIZE)
    expected_mac = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("frame MAC verification failed")

    payload = xor_stream_crypt(enc_key, nonce, ciphertext)
    return Frame(msg_type=msg_type, request_id=request_id, nonce=nonce, ciphertext=ciphertext, mac=mac), payload

def validate_vst_host(host: str):
    lhost = host.lower()
    return any([(sh in lhost) for sh in SUPPORTED_HOSTS])

class LicenseServer:
    def __init__(self, config: Mapping[str, object]) -> None:
        self.config = config
        self.snapshot = load_snapshot(Path(config["snapshot_path"]))
        self.enc_key, self.mac_key = derive_message_keys(str(config["shared_secret"]))
        self.license_key = config["license"]
        self.logger = LOGGER.getChild("server")

    def handle_activate(self, payload: ActivationRequestPayload, signer: LicenseSigner) -> bytes:
        vst_host = payload.vst_host
        if not validate_vst_host(vst_host):
            raise ValueError(f"unknown vst host: {vst_host}")

        self.logger.info(
            "activate payload vst_host='%s' license=%s hwid=(%s)",
            vst_host,
            payload.license_key,
            payload.hwid
        )

        if payload.license_key != self.license_key:
            raise ValueError("invalid license key")

        return build_activation_response(
            snapshot=self.snapshot,
            hwid=payload.hwid,
            signer=signer
        )

    def handle_client(self, conn: ssl.SSLSocket, peer: Tuple[str, int], signer: LicenseSigner) -> None:
        peer_label = format_peer(peer)
        thread_name = threading.current_thread().name
        request_count = 0
        tls_version = None
        cipher = None
        certificate = None
        try:
            tls_version = conn.version()
            cipher = conn.cipher()
            certificate = conn.getpeercert()
            self.logger.info(
                "access connect peer=%s thread=%s tls_version=%s cipher=%s client_cert=%s",
                peer_label,
                thread_name,
                tls_version,
                cipher[0] if cipher else None,
                summarize_certificate(certificate),
            )
            while True:
                frame, payload = unpack_frame(conn, self.enc_key, self.mac_key)
                request_count += 1
                self.logger.info(
                    "access request peer=%s request_id=%d msg_type=%d payload_len=%d nonce=%s ciphertext_len=%d",
                    peer_label,
                    frame.request_id,
                    frame.msg_type,
                    len(payload),
                    frame.nonce.hex(),
                    len(frame.ciphertext),
                )
                if frame.msg_type == TYPE_ACTIVATE:
                    response = self.handle_activate(parse_activation_request(payload), signer)
                    msg_type = TYPE_ACTIVATE
                else:
                    raise ValueError(f"unsupported message type {frame.msg_type}")

                conn.sendall(pack_frame(msg_type, frame.request_id, response, self.enc_key, self.mac_key))
                self.logger.info(
                    "access response peer=%s request_id=%d msg_type=%d response_len=%d",
                    peer_label,
                    frame.request_id,
                    msg_type,
                    len(response),
                )
        except ConnectionError as exc:
            self.logger.info("access disconnect peer=%s requests=%d reason=%s", peer_label, request_count, exc)
        except Exception as exc:
            self.logger.exception(
                "access error peer=%s requests=%d tls_version=%s cipher=%s error=%s",
                peer_label,
                request_count,
                tls_version,
                cipher[0] if cipher else None,
                exc,
            )
        finally:
            conn.close()
            self.logger.info("access close peer=%s requests=%d", peer_label, request_count)


def build_ssl_context(config: Mapping[str, object]) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config["tls_cert_path"], config["tls_key_path"])
    context.load_verify_locations(config.get("client_ca_path"))
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def serve(config: Mapping[str, object]) -> None:
    server = LicenseServer(config)
    signer = LicenseSigner(config["lic_sign_key"])
    context = build_ssl_context(config)
    bind_host = config.get("bind_host", "0.0.0.0")
    bind_port = int(config.get("bind_port", 44330))
    
    LOGGER.info(
        "server start bind=%s:%d backlog=%d snapshot=%s",
        bind_host,
        bind_port,
        int(config.get("backlog", 32)),
        config["snapshot_path"]
    )

    with socket.create_server((bind_host, bind_port), reuse_port=False) as sock:
        sock.listen(int(config.get("backlog", 32)))
        while True:
            client, peer = sock.accept()
            peer_label = format_peer(peer)
            LOGGER.info("access accept peer=%s", peer_label)
            try:
                tls_client = context.wrap_socket(client, server_side=True)
            except Exception:
                LOGGER.exception("access tls-handshake-failed peer=%s", peer_label)
                client.close()
                continue
            thread = threading.Thread(target=server.handle_client, args=(tls_client, peer, signer), daemon=True)
            thread.start()
            LOGGER.debug("access thread-start peer=%s thread=%s", peer_label, thread.name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="license server")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--log-level", default=None)
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def configure_logging(level_name: str, log_file_path: str) -> None:
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"unsupported log level: {level_name}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    log_level = args.log_level or str(config.get("stdout_log_level", "INFO"))
    configure_logging(log_level, config["log_file_path"])
    serve(config)


if __name__ == "__main__":
    main()
