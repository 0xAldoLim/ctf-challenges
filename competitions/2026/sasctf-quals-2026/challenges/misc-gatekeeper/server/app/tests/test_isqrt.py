"""Boundary-value safeness tests for the isqrt ABI shim.

These drive ``shim_isqrt`` directly and assert:
  - a concrete argument yields EXACTLY math.isqrt(n) at the edges (it must stay
    bit-identical to the trusted-lib blob), and
  - a symbolic argument yields a result soundly capped at [0, 2^32-1] (the true
    range of floor(sqrt(u64))).
"""

import math

from verifier.engine import Verifier
from verifier.smt import mkbv, sat, under_pc


def _boundary_values() -> list[int]:
    U64 = 1 << 64
    vals = {
        0, 1, 2, 3, 4,
        (1 << 32) - 1, (1 << 32), (1 << 32) + 1,        # the 2^32 result step
        (1 << 63) - 1, (1 << 63), (1 << 63) + 1,        # mid-range
        U64 - 2, U64 - 1,                                # top of u64
        ((1 << 32) - 1) ** 2,                            # largest perfect square <= u64 max
    }
    for k in (0, 1, 2, 3, 255, 256, 0xFFFF, 0x10000, 0x7FFFFFFF, (1 << 32) - 1):
        sq = k * k
        for n in (sq - 1, sq, sq + 1):
            if 0 <= n < U64:
                vals.add(n)
    return sorted(vals)


def test_isqrt_concrete_boundary_values_are_exact():
    engine = Verifier()
    ctx = engine._ctx
    ctx.registers.a0 = ctx.registers.x10  # ABI alias (normally set while priming)

    for n in _boundary_values():
        ctx.setConcreteRegisterValue(ctx.registers.a0, n)  # concrete write clears symbolization
        engine._shims.shim_isqrt()
        got = ctx.getConcreteRegisterValue(ctx.registers.a0)
        assert got == math.isqrt(n), f"isqrt(0x{n:x}) = 0x{got:x}, want 0x{math.isqrt(n):x}"


def test_isqrt_symbolic_result_is_soundly_bounded():
    engine = Verifier()
    ctx = engine._ctx
    actx = ctx.getAstContext()
    ctx.registers.a0 = ctx.registers.x10

    ctx.symbolizeRegister(ctx.registers.a0, "isqrt_arg")
    engine._shims.shim_isqrt()

    a0 = ctx.registers.a0
    assert ctx.isRegisterSymbolized(a0)
    ast = ctx.getSymbolicRegister(a0).getAst()
    can_exceed = sat(
        ctx, under_pc(ctx, actx.bvugt(ast, mkbv(actx, 0xFFFFFFFF, ast.getBitvectorSize())))
    )
    assert not can_exceed, "symbolic isqrt result can exceed its sound bound 2^32-1"
