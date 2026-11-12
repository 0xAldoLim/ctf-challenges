import enum
import logging
from typing import TYPE_CHECKING, List, Optional

from triton import OPERAND, Instruction, MemoryAccess

from .limits import Limits
from .smt import mkbv, sat, under_pc

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from triton import AstNode, Register

    from .engine import Verifier


class AccessKind(enum.Enum):
    READ = enum.auto()
    WRITE = enum.auto()
    EXECUTE = enum.auto()


def _floor_to(value: int, step: int) -> int:
    return (value // step) * step


def _ceil_to(value: int, step: int) -> int:
    return ((value + step - 1) // step) * step


class PointerOracle:
    def __init__(self, engine: "Verifier") -> None:
        self._engine = engine
        self._ctx = engine._ctx
        self._actx = engine._ctx.getAstContext()

    def _bound_edge(self, node: "AstNode", lo: int, hi: int, upper: bool) -> int:
        assert lo <= hi, "bad search interval"
        while lo < hi:
            mid = (lo + hi) // 2
            if upper:
                feasible = sat(
                    self._ctx,
                    under_pc(
                        self._ctx,
                        self._actx.bvuge(
                            node, mkbv(self._actx, mid, node.getBitvectorSize())
                        ),
                    ),
                )
                if feasible:
                    lo = mid + 1
                else:
                    hi = mid
            else:
                feasible = sat(
                    self._ctx,
                    under_pc(
                        self._ctx,
                        self._actx.bvule(
                            node, mkbv(self._actx, mid, node.getBitvectorSize())
                        ),
                    ),
                )
                if feasible:
                    hi = mid
                else:
                    lo = mid + 1
        return lo if upper else hi

    def _aligned_for_all(self, lea: "AstNode", size: int) -> bool:
        assert size in (1, 2, 4, 8)
        bits = lea.getBitvectorSize()
        mask = mkbv(self._actx, size - 1, bits)
        misaligned = under_pc(
            self._ctx,
            self._actx.distinct(self._actx.bvand(lea, mask), mkbv(self._actx, 0, bits)),
        )
        return not sat(self._ctx, misaligned)

    def _select_over(self, lea: "AstNode", size: int, slots: List[int]) -> "AstNode":
        assert slots, "no slots to select over"
        ea_bits = lea.getBitvectorSize()
        val_bits = size * 8
        expr = mkbv(self._actx, 0, val_bits)
        for addr in reversed(slots):
            cond = self._actx.equal(lea, mkbv(self._actx, addr, ea_bits))
            cell = self._ctx.getMemoryAst(MemoryAccess(addr, size))
            assert cell.getBitvectorSize() == val_bits
            expr = self._actx.ite(cond, cell, expr)
        return expr

    def _dest_of_load(self, inst: Instruction) -> Optional["Register"]:
        ops = inst.getOperands()
        if (
            len(ops) >= 2
            and ops[0].getType() == OPERAND.REG
            and ops[1].getType() == OPERAND.MEM
        ):
            return ops[0]
        return None

    def _write_back_load(self, inst: Instruction, value: "AstNode") -> None:
        dst = self._dest_of_load(inst)
        if dst is None:
            self._engine.fail("symbolic load: destination register not found")

        op = inst.getDisassembly().split()[0]
        actx = self._actx
        dst_bits = dst.getBitSize()
        w = value.getBitvectorSize()

        def sext(v):
            return actx.sx(dst_bits - w, v) if dst_bits > w else v

        def zext(v):
            return actx.zx(dst_bits - w, v) if dst_bits > w else v

        if op in ("lb", "lh"):
            value = sext(value)
        elif op in ("lbu", "lhu"):
            value = zext(value)
        elif op == "lw":
            if w != 32:
                value = actx.extract(31, 0, value)
            if dst_bits > 32:
                value = actx.sx(dst_bits - 32, value)
        elif op == "lwu":
            if w != 32:
                value = actx.extract(31, 0, value)
            if dst_bits > 32:
                value = actx.zx(dst_bits - 32, value)
        elif op == "ld":
            if w < dst_bits:
                value = actx.zx(dst_bits - w, value)
        else:
            self._engine.fail("symbolic load: unsupported opcode")

        sexpr = self._ctx.newSymbolicExpression(
            value, f"modeled_symbolic_read_ite_{self._engine._total_executed}"
        )
        self._ctx.assignSymbolicExpressionToRegister(sexpr, dst)

    def resolve_symbolic_loads(self, inst: Instruction) -> None:
        for ma, _ in inst.getLoadAccess():
            lea = ma.getLeaAst()
            if not (lea and lea.isSymbolized()):
                continue

            size = ma.getSize()
            bits = lea.getBitvectorSize()
            anchor = ma.getAddress()

            span = Limits.symbolic_window * size
            hi_limit = anchor + span
            lo_limit = anchor - span if anchor >= span else 0

            if sat(
                self._ctx,
                under_pc(
                    self._ctx, self._actx.bvugt(lea, mkbv(self._actx, hi_limit, bits))
                ),
            ):
                self._engine.fail(
                    f"symbolic load {ma} ranges past the upper bound "
                    f"(>{Limits.symbolic_window} elements)"
                )
            if sat(
                self._ctx,
                under_pc(
                    self._ctx, self._actx.bvult(lea, mkbv(self._actx, lo_limit, bits))
                ),
            ):
                self._engine.fail(
                    f"symbolic load {ma} ranges past the lower bound "
                    f"(>{Limits.symbolic_window} elements)"
                )

            hi_exact = self._bound_edge(lea, anchor, hi_limit, upper=True)
            lo_exact = self._bound_edge(lea, lo_limit, anchor, upper=False)

            if not self._aligned_for_all(lea, size):
                self._engine.fail(
                    f"symbolic load {ma} is not provably {size}-byte aligned"
                )

            lo_exact = _ceil_to(lo_exact, size)
            hi_exact = _floor_to(hi_exact, size)
            if hi_exact < lo_exact:
                self._engine.fail(f"symbolic load {ma}: window empty after alignment")

            logger.debug(
                "0x%016x %s: symbolic load %s over [0x%x, 0x%x]",
                inst.getAddress(),
                inst.getDisassembly(),
                ma,
                lo_exact,
                hi_exact,
            )

            slots = [
                addr
                for addr in range(lo_exact, hi_exact + 1, size)
                if sat(
                    self._ctx,
                    under_pc(
                        self._ctx, self._actx.equal(lea, mkbv(self._actx, addr, bits))
                    ),
                )
            ]
            if not slots:
                self._engine.fail(f"symbolic load {ma}: no reachable concrete slot")

            for addr in slots:
                if self._ctx.isMemoryTainted(MemoryAccess(addr, size)):
                    self._engine.fail(
                        f"symbolic load {ma} may touch undefined memory at 0x{addr:08x}"
                    )
                self._engine.guard_range(addr, size, AccessKind.READ)

            self._write_back_load(inst, self._select_over(lea, size, slots))
