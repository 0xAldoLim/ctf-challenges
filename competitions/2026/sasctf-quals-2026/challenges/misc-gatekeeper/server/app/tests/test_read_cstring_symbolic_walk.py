"""Regression tests for the `%s` walk over symbolic (e.g. read_file_plain) content.

A symbolic byte whose concrete *model* value happens to be 0 is **not** a
provable string terminator: at runtime it may be non-zero, so `mini_printf`
would walk (and read) further than a naive "stop at the first zero" verifier
ever validated. `_read_cstring` must therefore keep validating bytes -- each one
proven defined + readable -- until it reaches a *concrete* (non-symbolic) zero,
or refuse outright when the walk first runs into undefined/forbidden memory.

The runtime walk stops at or before the first concrete zero, so as long as the
verifier validates every byte up to that concrete NUL, it never under-validates.
"""
import pytest
from triton import Instruction, MemoryAccess

from verifier.address_space import SPACE
from verifier.engine import Verifier, _Stop

DATA = SPACE.by_name("user-data")
assert DATA is not None


def _primed() -> Verifier:
    # _prime lays down the program image, installs the register aliases and the
    # memory-access guards, and marks the whole stack undefined (tainted).
    v = Verifier()
    v._prime(b"\x00" * 64)
    # fail() reports the in-flight instruction; give it a benign nop to quote.
    nop = Instruction(0x300000, b"\x13\x00\x00\x00")  # addi x0, x0, 0
    v._ctx.disassembly(nop)
    v._cur = nop
    return v


def _mimic_read_file_plain(v: Verifier, addr: int, n: int) -> None:
    """Reproduce shim_read_file_plain's effect on its output buffer: `n` *defined*
    (untainted) bytes that are symbolic with concrete value 0."""
    ctx = v._ctx
    for off in range(n):
        ctx.untaintMemory(addr + off)
        ctx.setConcreteMemoryValue(MemoryAccess(addr + off, 1), 0, True)
        ctx.symbolizeMemory(MemoryAccess(addr + off, 1), f"file_b{off}")


def test_symbolic_zeros_then_concrete_zero_is_accepted():
    # 16 symbolic-zero bytes followed by a concrete zero (the untouched, zero-
    # filled .data tail). This is the "10 symbolic bytes, then a concrete zero
    # terminator" case: every byte up to the concrete NUL is validated, so it is
    # admitted -- the fix must not be over-strict.
    v = _primed()
    buf = DATA.base + 0x100
    _mimic_read_file_plain(v, buf, 16)
    out = v._shims._read_cstring(buf)
    assert len(out) == 16  # walked the symbolic prefix, stopped at the concrete NUL


def test_symbolic_walk_into_undefined_is_rejected():
    # The same symbolic buffer at the very end of .data: with no concrete NUL in
    # the buffer, the walk runs past it into the (tainted) stack. At runtime
    # mini_printf could read out of bounds, so the verifier must refuse rather
    # than treat the first symbolic zero as a terminator.
    v = _primed()
    buf = DATA.base + DATA.length - 16  # last 16 bytes of user-data; next byte = stack
    _mimic_read_file_plain(v, buf, 16)
    with pytest.raises(_Stop) as exc:
        v._shims._read_cstring(buf)
    assert "undefined" in exc.value.issue


def test_format_string_path_still_rejects_any_symbolic_byte():
    # The fmt-string read (require_concrete=True) is stricter: a symbolic byte is
    # rejected immediately, even one whose model value is non-zero.
    v = _primed()
    buf = DATA.base + 0x200
    _mimic_read_file_plain(v, buf, 4)
    with pytest.raises(_Stop) as exc:
        v._shims._read_cstring(buf, require_concrete=True)
    assert "symbolic" in exc.value.issue
