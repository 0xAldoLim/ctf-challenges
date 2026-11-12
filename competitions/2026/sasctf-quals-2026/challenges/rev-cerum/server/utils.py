import gzip
import hashlib
import hmac
import json
import struct
from pathlib import Path
from typing import Dict, Tuple
from numba import njit
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from Crypto.Hash import SHA256

MASK32 = 0xFFFFFFFF

@njit
def u32(x: int) -> int:
    return x & MASK32

@njit
def i32(x: int) -> int:
    x &= MASK32
    if x >= 0x80000000:
        x -= 0x100000000
    return x

@njit
def hash32(x: int) -> int:
    x = u32(x)
    x ^= x >> 16
    x = u32(x * 0x7FEB352D)
    x ^= x >> 15
    x = u32(x * 0x846CA68B)
    x ^= x >> 16
    return u32(x)

@njit
def ceil_log2_u(x: int) -> int:
    x -= 1
    bits = 0
    while (x > 0):
        x >>= 1
        bits += 1
    return bits

@njit
def round_function(value: int, round_index: int, seed: int) -> int:
    s = u32(seed)
    x = u32(value)
    x ^= s
    x = u32(x)
    x ^= hash32(u32(s + round_index * 0x9E3779B9))
    x = u32(x)
    x ^= u32(round_index * 0xBB67AE85)
    x = u32(x)
    return hash32(x)

@njit
def feistel_pow2(x: int, half_bits: int, seed: int) -> int:
    mask = (1 << half_bits) - 1
    left = x >> half_bits
    right = x & mask
    rounds = 8
    for r in range(rounds - 1, -1, -1):
        prev_right = left
        f = round_function(prev_right, r, seed) & mask
        prev_left = right ^ f
        left, right = prev_left, prev_right
    return u32((left << half_bits) | right)

@njit
def permute_index(index: int, count: int, seed: int) -> int:
    if count <= 1:
        return index
    bits = ceil_log2_u(count)
    if bits & 1:
        bits += 1
    half_bits = bits >> 1
    x = index
    while True:
        x = feistel_pow2(x, half_bits, seed)
        if x < count:
            return x

def hwid_seed_derive(hwid):
    result = 0xFFFFFFFF
    shift = 0
    for ch in hwid:
        result ^= (ord(ch) << (shift * 8))
        shift = (shift + 1) % 4
    return result

def deflate(data: bytes) -> bytes:
    return gzip.compress(data)[10:]

def load_snapshot(path: Path) -> Dict[str, object]:
    encoded = gzip.decompress(path.read_bytes())
    snapshot = json.loads(encoded.decode("utf-8"))
    return snapshot

def serialize_vector(vector, seed):
    vector_data = bytearray()
    for i in range(len(vector)):
        vector_data += struct.pack("<I", vector[permute_index(i, len(vector), seed)])
    return vector_data

def xor_stream_crypt(key: bytes, nonce: bytes, payload: bytes) -> bytes:
    output = bytearray(len(payload))
    counter = 0
    offset = 0
    while offset < len(payload):
        block = hmac.new(key, nonce + counter.to_bytes(4, "little"), hashlib.sha256).digest()
        take = min(len(block), len(payload) - offset)
        for index in range(take):
            output[offset + index] = payload[offset + index] ^ block[index]
        counter += 1
        offset += take
    return bytes(output)


def derive_message_keys(shared_secret: str) -> Tuple[bytes, bytes]:
    secret = shared_secret.encode("utf-8")
    enc_key = hmac.new(secret, b"lic-server-enc", hashlib.sha256).digest()
    mac_key = hmac.new(secret, b"lic-server-mac", hashlib.sha256).digest()
    return enc_key, mac_key

class LicenseSigner:
    def __init__(self, keypath):
        with open(keypath, 'r') as key_source:
            key = key_source.read()
            self.rsakey = RSA.import_key(key)
    
    def hash(self, message):
        return hashlib.sha256(message).digest()
    
    def sign(self, message):
        message_hash = SHA256.new(message)
        return pss.new(self.rsakey).sign(message_hash)
