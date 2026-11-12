import hashlib
import secrets
import string

from app.settings import get_settings


def make_resource() -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))


def verify_hashcash(stamp, resource, bits=30) -> bool:
    if not stamp.startswith("1:"):
        return False

    try:
        claim, _date, res, _ext, _rand, _counter = stamp[2:].split(":")
        claim_bits = int(claim)
    except (ValueError, TypeError):
        return False

    if claim_bits < bits or res != resource:
        return False

    digest = hashlib.sha1(stamp.encode("utf-8")).digest()
    full_bytes, remaining_bits = divmod(bits, 8)
    if digest[:full_bytes] != b"\x00" * full_bytes:
        return False
    if remaining_bits == 0:
        return True
    mask = 0xFF << (8 - remaining_bits) & 0xFF
    return digest[full_bytes] & mask == 0


def run_pow_challenge(channel, settings, bits=30) -> tuple[bool, bytes]:
    resource = make_resource()
    channel.sendall(
        (
            "Proof of work required.\r\n"
            f"Run: hashcash -mb{bits} {resource}\r\n"
            "stamp> "
        ).encode("ascii")
    )

    line, leftover = _read_echoed_line(channel, settings)
    if line is None:
        return False, b""
    stamp = line.decode("utf-8", "replace").strip()
    if stamp == get_settings().pass_pow_phrase:
        return True, leftover
    if not stamp.startswith("1:"):
        channel.sendall(b"only hashcash v1 supported\r\n")
        return False, b""
    if not verify_hashcash(stamp, resource=resource, bits=bits):
        channel.sendall(b"invalid\r\n")
        return False, b""
    channel.sendall(b"Proof accepted.\r\n")
    return True, leftover


def _read_echoed_line(channel, settings, max_bytes=4096):
    line = bytearray()
    while True:
        data = channel.recv(settings.recv_buffer_size)
        if not data:
            return None, b""
        for index, byte in enumerate(data):
            if byte in (10, 13):
                end = index + 1
                if byte == 13 and end < len(data) and data[end] == 10:
                    end += 1
                channel.sendall(b"\r\n")
                return bytes(line), bytes(data[end:])
            if byte == 3:
                channel.sendall(b"^C\r\n")
                return None, b""
            if byte in (8, 127):
                if line:
                    line.pop()
                    channel.sendall(b"\b \b")
                continue
            if byte < 32:
                continue
            if len(line) >= max_bytes:
                channel.sendall(b"\r\ninput too long\r\n")
                return None, b""
            line.append(byte)
            channel.sendall(bytes([byte]))
