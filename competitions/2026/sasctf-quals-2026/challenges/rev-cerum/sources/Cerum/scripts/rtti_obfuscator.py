#!/usr/bin/env python3

import argparse
import random
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ASCII_RTTI_RE = re.compile(
    rb"((?:\.\?A[UVW]|PEA[UVW]))([ -~]{1,512}?)(@@)\x00"
)
FUNCTION_RTTI_RE = re.compile(rb"(\.P6[A-Z0-9_?$]{1,32})([ -~]{1,512}?)(@Z)\x00")
LAMBDA_RTTI_RE = re.compile(rb"\.\?AV<lambda[ -~]{0,512}?\x00")
IPLUG_CSTR_RE = re.compile(rb"(?i)(?<![ -~])iplug[ -~]{0,507}\x00")
IPLUG_16_RE = re.compile(
    rb"(?<![\x20-\x7e]\x00)"
    rb"[iI]\x00[pP]\x00[lL]\x00[uU]\x00[gG]\x00"
    rb"(?:\x00\x00){1,3}"
)
IPLUG_WNDCLASS_16_RE = re.compile(
    rb"(?<![\x20-\x7e]\x00)"
    rb"[iI]\x00[pP]\x00[lL]\x00[uU]\x00[gG]\x00"
    rb"[wW]\x00[nN]\x00[dD]\x00[cC]\x00[lL]\x00[aA]\x00[sS]\x00[sS]\x00"
    rb"(?:\x00\x00){1,3}"
)
PDB_PATH_RE = re.compile(
    rb"(?i)(?:[A-Za-z]:\\|\\\\)[^\x00\r\n]{0,1024}\.pdb"
)


@dataclass
class Section:
    name: str
    virtual_address: int
    span: int
    raw_ptr: int


@dataclass
class PEInfo:
    is_pe64: bool
    debug_rva: int
    debug_size: int
    sections: list[Section]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Obfuscate MSVC RTTI type names in a PE file and zero embedded PDB paths."
        )
    )
    parser.add_argument("input", type=Path, help="Input PE file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path. Defaults to <input>.obf<suffix>",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite the input file directly",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="PRNG seed for reproducible RTTI replacements",
    )
    parser.add_argument(
        "--no-rtti",
        action="store_true",
        help="Skip RTTI obfuscation",
    )
    parser.add_argument(
        "--no-pdb",
        action="store_true",
        help="Skip PDB path removal",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create <input>.bak before in-place modification",
    )
    return parser.parse_args()


def parse_pe_info(data: bytes) -> PEInfo:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("Not an MZ/PE file")

    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 0x18 > len(data) or data[pe_off : pe_off + 4] != b"PE\0\0":
        raise ValueError("Missing PE signature")

    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    opt_off = pe_off + 24
    magic = struct.unpack_from("<H", data, opt_off)[0]
    if magic not in (0x10B, 0x20B):
        raise ValueError(f"Unsupported PE optional header magic: 0x{magic:04x}")

    is_pe64 = magic == 0x20B
    data_dir_off = opt_off + (112 if is_pe64 else 96)
    debug_rva, debug_size = struct.unpack_from("<II", data, data_dir_off + 8 * 6)

    sec_off = opt_off + opt_size
    sections = []
    for i in range(num_sections):
        off = sec_off + 40 * i
        name = data[off : off + 8].split(b"\0", 1)[0].decode("latin1", "ignore")
        virtual_size, virtual_address, raw_size, raw_ptr = struct.unpack_from(
            "<IIII", data, off + 8
        )
        sections.append(
            Section(
                name=name,
                virtual_address=virtual_address,
                span=max(virtual_size, raw_size),
                raw_ptr=raw_ptr,
            )
        )

    return PEInfo(
        is_pe64=is_pe64,
        debug_rva=debug_rva,
        debug_size=debug_size,
        sections=sections,
    )


def rva_to_offset(pe: PEInfo, rva: int) -> int | None:
    for section in pe.sections:
        if section.virtual_address <= rva < section.virtual_address + section.span:
            return section.raw_ptr + (rva - section.virtual_address)
    return None


def random_body(length: int, rng: random.Random) -> bytes:
    alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$"
    return bytes(rng.choice(alphabet) for _ in range(length))


def random_utf16le_body(length: int, rng: random.Random) -> bytes:
    ascii_body = random_body(length, rng)
    return b"".join(bytes((byte, 0)) for byte in ascii_body)


def obfuscate_ascii_rtti(data: bytearray, rng: random.Random) -> int:
    matches = list(ASCII_RTTI_RE.finditer(data))
    matches.extend(FUNCTION_RTTI_RE.finditer(data))
    used = set()

    for match in matches:
        prefix = match.group(1)
        body = match.group(2)
        suffix = match.group(3)

        replacement_body = random_body(len(body), rng)
        while replacement_body in used:
            replacement_body = random_body(len(body), rng)
        used.add(replacement_body)

        replacement = prefix + replacement_body + suffix + b"\x00"
        data[match.start() : match.end()] = replacement

    return len(matches)


def obfuscate_iplug_strings(data: bytearray, rng: random.Random) -> int:
    count = 0

    for match in list(IPLUG_CSTR_RE.finditer(data)):
        text = match.group(0)
        body_len = len(text) - 1
        replacement = random_body(body_len, rng) + b"\x00"
        data[match.start() : match.end()] = replacement
        count += 1

    for match in list(IPLUG_WNDCLASS_16_RE.finditer(data)):
        chunk = bytes(match.group(0))

        body_len = 0
        for i in range(0, len(chunk), 2):
            if chunk[i : i + 2] == b"\x00\x00":
                break
            body_len += 1

        replacement = bytearray(chunk)
        replacement[: body_len * 2] = random_utf16le_body(body_len, rng)
        data[match.start() : match.end()] = replacement
        count += 1
    
    for match in list(IPLUG_16_RE.finditer(data)):
        chunk = bytes(match.group(0))

        body_len = 0
        for i in range(0, len(chunk), 2):
            if chunk[i : i + 2] == b"\x00\x00":
                break
            body_len += 1

        replacement = bytearray(chunk)
        replacement[: body_len * 2] = random_utf16le_body(body_len, rng)
        data[match.start() : match.end()] = replacement
        count += 1

    return count


def zero_lambda_rtti(data: bytearray) -> int:
    matches = list(LAMBDA_RTTI_RE.finditer(data))
    for match in matches:
        zero_range(data, match.start(), match.end())
    return len(matches)


def zero_range(data: bytearray, start: int, end: int) -> int:
    for i in range(start, end):
        data[i] = 0
    return max(0, end - start)


def zero_pdb_path_in_codeview_blob(blob: memoryview) -> int:
    if len(blob) < 16:
        return 0

    sig = bytes(blob[:4])
    if sig == b"RSDS":
        path_off = 24
    elif sig == b"NB10":
        path_off = 16
    else:
        return 0

    if path_off >= len(blob):
        return 0

    end = path_off
    while end < len(blob) and blob[end] != 0:
        end += 1

    if end == path_off:
        return 0

    for i in range(path_off, end):
        blob[i] = 0
    return end - path_off


def zero_debug_directory_pdb_paths(data: bytearray, pe: PEInfo) -> tuple[int, int]:
    if not pe.debug_rva or not pe.debug_size:
        return 0, 0

    debug_off = rva_to_offset(pe, pe.debug_rva)
    if debug_off is None:
        return 0, 0

    entries = pe.debug_size // 28
    zeroed_records = 0
    zeroed_bytes = 0

    for idx in range(entries):
        off = debug_off + idx * 28
        if off + 28 > len(data):
            break

        _, _, _, _, typ, size_of_data, _, raw_ptr = struct.unpack_from("<IIHHIIII", data, off)
        if typ != 2 or size_of_data == 0:
            continue
        if raw_ptr + size_of_data > len(data):
            continue

        blob = memoryview(data)[raw_ptr : raw_ptr + size_of_data]
        changed = zero_pdb_path_in_codeview_blob(blob)
        if changed:
            zeroed_records += 1
            zeroed_bytes += changed

    return zeroed_records, zeroed_bytes


def zero_loose_pdb_paths(data: bytearray) -> tuple[int, int]:
    matches = list(PDB_PATH_RE.finditer(data))
    zeroed_bytes = 0
    for match in matches:
        zeroed_bytes += zero_range(data, match.start(), match.end())
    return len(matches), zeroed_bytes


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.obf{input_path.suffix}")


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)

    if args.in_place and args.output:
        print("error: use either --in-place or --output, not both", file=sys.stderr)
        return 2

    input_path = args.input
    if not input_path.is_file():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 2

    output_path = input_path if args.in_place else (args.output or default_output_path(input_path))

    data = bytearray(input_path.read_bytes())
    try:
        pe = parse_pe_info(data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.in_place and args.backup:
        backup_path = input_path.with_name(input_path.name + ".bak")
        shutil.copy2(input_path, backup_path)

    rtti_count = 0
    if not args.no_rtti:
        rtti_count = obfuscate_ascii_rtti(data, rng)
        rtti_count += obfuscate_iplug_strings(data, rng)
        rtti_count += zero_lambda_rtti(data)

    debug_pdb_records = 0
    debug_pdb_bytes = 0
    loose_pdb_count = 0
    loose_pdb_bytes = 0
    if not args.no_pdb:
        debug_pdb_records, debug_pdb_bytes = zero_debug_directory_pdb_paths(data, pe)
        loose_pdb_count, loose_pdb_bytes = zero_loose_pdb_paths(data)

    output_path.write_bytes(data)

    print(f"wrote: {output_path}")
    print(f"rtti_strings_obfuscated: {rtti_count}")
    print(f"pdb_debug_records_zeroed: {debug_pdb_records}")
    print(f"pdb_debug_bytes_zeroed: {debug_pdb_bytes}")
    print(f"loose_pdb_strings_zeroed: {loose_pdb_count}")
    print(f"loose_pdb_bytes_zeroed: {loose_pdb_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
