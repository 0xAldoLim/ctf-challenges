import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NoReturn, Optional

from triton import (
    ARCH,
    CALLBACK,
    EXCEPTION,
    MODE,
    SOLVER,
    Instruction,
    MemoryAccess,
    TritonContext,
)

from .abi_shims import AbiShims
from .address_space import SPACE, Segment
from .control_flow import ControlFlow
from .limits import Limits
from .opcode_policy import POLICY
from .pointer_oracle import AccessKind, PointerOracle

if TYPE_CHECKING:
    from triton import Register

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Verdict:
    passed: bool = field(default=False)
    issue: str = field(default_factory=str)

    def __str__(self) -> str:
        return (
            "Verification passed"
            if self.passed
            else f"Verification failed: {self.issue}"
        )


@dataclass(slots=True)
class _Stop(Exception):
    passed: bool = field(default=False)
    issue: str = field(default_factory=str)

    def __str__(self) -> str:
        return self.issue


_SCRUBBED = (
    "x5",
    "x6",
    "x7",
    *(f"x{i}" for i in range(11, 18)),
    *(f"x{i}" for i in range(28, 32)),
)


class Verifier:
    def __init__(self) -> None:
        self._cur: Optional[Instruction] = None
        self._total_executed = 0
        self._pinned_target: Optional[int] = None

        arch = getattr(ARCH, "RV64", None)
        if arch is None:
            raise RuntimeError("Triton RISCV64 backend not available")

        self._ctx = TritonContext(arch)
        self._actx = self._ctx.getAstContext()
        self._configure(self._ctx)

        self._exec_segments = SPACE.executable()
        trusted = SPACE.by_name("trusted-funcs")
        assert trusted is not None
        self._trusted: Segment = trusted
        self._entry_points = {child.base for child in trusted.children}

        self._shims = AbiShims(self)
        self._oracle = PointerOracle(self)
        self._flow = ControlFlow(self)
        self._shim_by_name = {
            "create_file_plain": self._shims.shim_create_file_plain,
            "isqrt": self._shims.shim_isqrt,
            "read_file_plain": self._shims.shim_read_file_plain,
            "readc": self._shims.shim_readc,
            "mini_printf": self._shims.shim_mini_printf,
        }
        logger.debug("RV64 screening context ready")

    @staticmethod
    def _configure(ctx: TritonContext) -> None:
        for mode in (
            MODE.ALIGNED_MEMORY,
            MODE.CONSTANT_FOLDING,
            MODE.AST_OPTIMIZATIONS,
            MODE.TAINT_THROUGH_POINTERS,
        ):
            ctx.setMode(mode, True)
        ctx.setSolver(SOLVER.BITWUZLA)
        ctx.setSolverTimeout(Limits.solver_ms)
        ctx.setSolverMemoryLimit(Limits.solver_bytes)

    def __repr__(self) -> str:
        return (
            f"<Verifier program_bytes={Limits.program_bytes} "
            f"step_budget={Limits.step_budget}>"
        )

    def fail(self, issue: str, prefix: str = "") -> NoReturn:
        assert self._cur is not None, "no instruction in flight"
        where = f"0x{self._cur.getAddress():016x} ({self._cur.getDisassembly()})"
        raise _Stop(passed=False, issue=f"{prefix}{where}: {issue}")

    def _scrub_caller_saved(self) -> None:
        for reg in self._ctx.getAllRegisters():
            if reg.getName() in _SCRUBBED:
                self._ctx.setConcreteRegisterValue(reg, 0)

    def _clobber_trusted_frame(self) -> None:
        sp = self._ctx.getConcreteRegisterValue(self._ctx.registers.sp)
        window = Limits.trusted_frame_window
        if sp < window:
            return
        for addr in range(sp - window, sp, 64):
            self._ctx.taintMemory(MemoryAccess(addr, 64))

    def _enter_trusted(self, pc: int) -> None:
        if pc not in self._entry_points:
            self.fail("trusted-call entry is not a known routine")
        routine = SPACE.locate(pc).name
        shim = self._shim_by_name.get(routine)
        assert shim is not None, f"no shim registered for {routine}"
        shim()
        self._scrub_caller_saved()
        self._clobber_trusted_frame()

    def _precheck(self, pc: int, disasm: str) -> None:
        if self._ctx.isRegisterSymbolized(self._ctx.registers.pc):
            self.fail("control-flow target is symbolic")

        if disasm not in POLICY:
            self.fail("opcode is not permitted")
        if not any(seg.holds(pc) for seg in self._exec_segments):
            self.fail("fetch outside executable memory")

    def _commit_pinned_target(self) -> None:
        if self._pinned_target is not None:
            self._ctx.setConcreteRegisterValue(
                self._ctx.registers.pc, self._pinned_target
            )
            self._pinned_target = None

    def _step(self, pc: int) -> None:
        word = self._ctx.getConcreteMemoryAreaValue(pc, 4, False)
        self._cur = Instruction(pc, word)
        self._ctx.disassembly(self._cur)
        disasm = self._cur.getDisassembly()

        self._precheck(pc, disasm)

        if self._trusted.holds(pc):
            self._enter_trusted(pc)

        if disasm.startswith("ebreak"):
            logger.info("accepted: reached ebreak")
            raise _Stop(passed=True)

        self._pinned_target = self._flow.resolve(self._cur)

        outcome = self._ctx.processing(self._cur)
        if outcome != EXCEPTION.NO_FAULT:
            self.fail(f"Triton processing fault {outcome}")

        if self._ctx.isRegisterSymbolized(self._ctx.registers.sp):
            self.fail("stack pointer became symbolic (stack-frame checks unsound)")

        self._commit_pinned_target()
        self._oracle.resolve_symbolic_loads(self._cur)

        logger.debug("(%05d) 0x%016x: %s", self._total_executed, pc, disasm)

    def guard_range(
        self, start: int, length: int, kind: AccessKind = AccessKind.READ
    ) -> None:
        for addr in range(start, start + length):
            self._guard_access(MemoryAccess(addr, 1), kind)

    def forbid_callee_frame_alias(self, start: int, length: int) -> None:
        if length == 0:
            return
        if self._ctx.isRegisterSymbolized(self._ctx.registers.sp):
            self.fail(
                "stack pointer is symbolic at a trusted call (frame bounds unsound)"
            )
        sp = self._ctx.getConcreteRegisterValue(self._ctx.registers.sp)
        lo, hi = sp - Limits.trusted_frame_window, sp
        if start < hi and lo < start + length:
            self.fail(
                f"trusted-call buffer [0x{start:016x},0x{start + length:016x}) "
                f"aliases the callee frame [0x{lo:016x},0x{hi:016x})"
            )

    def _guard_access(self, access: MemoryAccess, kind: AccessKind) -> None:
        permit, verb = {
            AccessKind.READ: (SPACE.may_read, "read"),
            AccessKind.WRITE: (SPACE.may_write, "write"),
            AccessKind.EXECUTE: (SPACE.may_exec, "execute"),
        }[kind]

        addr = access.getAddress()
        length = access.getSize()
        assert length in (1, 2, 4, 8), "odd access width"

        if not (permit(addr) and permit(addr + length - 1)):
            self.fail(f"{verb} of forbidden address 0x{addr:016x}")

        if kind == AccessKind.READ and self._ctx.isMemoryTainted(
            MemoryAccess(addr, length)
        ):
            self.fail(f"read of undefined memory at 0x{addr:016x} (size {length})")

        lea = access.getLeaAst()
        if lea and lea.isSymbolized():
            if kind is AccessKind.READ:
                logger.debug("[guard] symbolic read address %s", access)
            else:
                self.fail(f"{verb} to a symbolic address {access}", prefix="[guard] ")

    def _on_mem_read(self, _: TritonContext, access: MemoryAccess) -> None:
        self._guard_access(access, AccessKind.READ)

    def _on_mem_write(self, _: TritonContext, access: MemoryAccess, __: int) -> None:
        self._guard_access(access, AccessKind.WRITE)

    def _on_reg_write(self, _: TritonContext, reg: "Register", new_value: int) -> None:
        if reg != self._ctx.registers.sp:
            return
        old = self._ctx.getConcreteRegisterValue(reg)
        logger.debug("SP 0x%016x -> 0x%016x", old, new_value)
        lo, hi = (new_value, old) if new_value < old else (old, new_value)
        for addr in range(lo, hi):
            self._ctx.taintMemory(addr)

    def _alias_registers(self) -> None:
        regs = self._ctx.registers
        regs.sp = regs.x2
        regs.ra = regs.x1
        regs.a0, regs.a1, regs.a2, regs.a3 = regs.x10, regs.x11, regs.x12, regs.x13
        regs.a4, regs.a5, regs.a6, regs.a7 = regs.x14, regs.x15, regs.x16, regs.x17

    def _prime(self, blob: bytes) -> None:
        self._alias_registers()
        regs = self._ctx.registers

        code = SPACE.by_name("user-code")
        data = SPACE.by_name("user-data")
        stack = SPACE.by_name("stack")
        assert code and data and stack

        self._ctx.setConcreteMemoryAreaValue(
            code.base, blob[: code.length].ljust(code.length, b"\x00")
        )
        self._ctx.setConcreteMemoryAreaValue(
            data.base, blob[code.length :].ljust(data.length, b"\x00")
        )
        self._ctx.setConcreteMemoryAreaValue(stack.base, b"\x00" * stack.length)

        stack_top = stack.base + stack.length
        self._ctx.setConcreteRegisterValue(regs.sp, stack_top)
        self._ctx.setConcreteRegisterValue(regs.pc, code.base)
        self._ctx.setConcreteRegisterValue(regs.ra, code.base)
        self._ctx.setConcreteRegisterValue(regs.x8, stack_top)

        for child in self._trusted.children:
            self._ctx.setConcreteMemoryAreaValue(child.base, bytes.fromhex("67800000"))

        self._ctx.addCallback(CALLBACK.GET_CONCRETE_MEMORY_VALUE, self._on_mem_read)
        self._ctx.addCallback(CALLBACK.SET_CONCRETE_MEMORY_VALUE, self._on_mem_write)
        self._ctx.addCallback(CALLBACK.SET_CONCRETE_REGISTER_VALUE, self._on_reg_write)

        for addr in range(stack.base, stack.base + stack.length):
            self._ctx.taintMemory(addr)

    def _walk(self, blob: bytes) -> None:
        self._prime(blob)
        start = time.time()
        while self._total_executed < Limits.step_budget:
            pc = self._ctx.getConcreteRegisterValue(self._ctx.registers.pc)
            self._step(pc)
            self._total_executed += 1
            if time.time() - start > Limits.wall_clock_s:
                self.fail(f"screening exceeded {Limits.wall_clock_s}s")
        self.fail(f"step budget {Limits.step_budget} exhausted")

    def verify(self, blob: bytes) -> Verdict:
        if len(blob) > Limits.program_bytes:
            return Verdict(
                passed=False,
                issue=f"submission {len(blob)} bytes exceeds the {Limits.program_bytes}-byte limit",
            )

        start = time.time()
        try:
            self._walk(blob)
        except _Stop as stop:
            if stop.passed:
                return Verdict(passed=True)
            return Verdict(passed=False, issue=stop.issue or "rejected")
        except Exception as exc:
            return Verdict(passed=False, issue=f"internal error: {exc!s}")
        finally:
            logger.info(
                "screening done in %.2fs over %d steps",
                time.time() - start,
                self._total_executed,
            )
        return Verdict(passed=False, issue="unknown error")
