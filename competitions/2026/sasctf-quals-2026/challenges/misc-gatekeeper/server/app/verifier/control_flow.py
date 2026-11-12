import enum
import logging
from typing import TYPE_CHECKING, Optional

from triton import OPERAND

from .smt import mkbv, sat, under_pc

if TYPE_CHECKING:
    from triton import Instruction, Register

    from .engine import Verifier

logger = logging.getLogger(__name__)


class TransferKind(enum.Enum):
    SEQUENTIAL = enum.auto()
    BRANCH = enum.auto()
    DIRECT_JUMP = enum.auto()
    INDIRECT_JUMP = enum.auto()


_BRANCH = frozenset(
    {
        "beq",
        "bne",
        "blt",
        "bge",
        "bltu",
        "bgeu",
        "beqz",
        "bnez",
        "blez",
        "bgez",
        "bltz",
        "bgtz",
        "bgt",
        "ble",
        "bgtu",
        "bleu",
    }
)
_DIRECT_JUMP = frozenset({"jal", "j"})
_INDIRECT_JUMP = frozenset({"jalr", "jr", "ret", "call"})


class ControlFlow:
    def __init__(self, engine: "Verifier") -> None:
        self._engine = engine

    @staticmethod
    def classify(disassembly: str) -> TransferKind:
        head = disassembly.lower().split(" ", 1)[0].strip()
        if head in _INDIRECT_JUMP:
            return TransferKind.INDIRECT_JUMP
        if head in _DIRECT_JUMP:
            return TransferKind.DIRECT_JUMP
        if head in _BRANCH:
            return TransferKind.BRANCH
        return TransferKind.SEQUENTIAL

    def resolve(self, inst: "Instruction") -> Optional[int]:
        kind = self.classify(inst.getDisassembly())
        if kind is TransferKind.INDIRECT_JUMP:
            return self._pin_indirect(inst)
        return None

    def _pin_indirect(self, inst: "Instruction") -> Optional[int]:
        ctx, actx = self._engine._ctx, self._engine._actx

        base = self._base_register(inst)
        if base is None:
            return None
        ast = ctx.getSymbolicRegister(base).getAst()
        if not ast.isSymbolized():
            return None

        concrete = ctx.getConcreteRegisterValue(base)
        width = ast.getBitvectorSize()
        below = under_pc(ctx, actx.bvult(ast, mkbv(actx, concrete, width)))
        above = under_pc(ctx, actx.bvugt(ast, mkbv(actx, concrete, width)))
        if sat(ctx, below) or sat(ctx, above):
            logger.debug("indirect target has multiple models; leaving symbolic")
            return None

        imm = 0
        for operand in inst.getOperands():
            if operand.getType() == OPERAND.IMM:
                imm = operand.getValue()
                break
        target = (concrete + imm) & 0xFFFFFFFFFFFFFFFF
        logger.debug("indirect target proven unique = 0x%016x", target)
        ctx.setConcreteRegisterValue(base, concrete)
        return target

    @staticmethod
    def _base_register(inst: "Instruction") -> Optional["Register"]:
        base = None
        for operand in inst.getOperands():
            if operand.getType() == OPERAND.REG:
                base = operand
        return base
