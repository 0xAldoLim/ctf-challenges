import logging
import math
from typing import TYPE_CHECKING, NoReturn, Tuple

from triton import MemoryAccess

from .limits import Limits
from .pointer_oracle import AccessKind

if TYPE_CHECKING:
    from .engine import Verifier

logger = logging.getLogger(__name__)


class AbiShims:
    def __init__(self, engine: "Verifier") -> None:
        self._engine = engine
        self._ctx = engine._ctx

    def fail(self, why: str) -> NoReturn:
        self._engine.fail(why)

    @property
    def _tag(self) -> int:
        return self._engine._total_executed

    def _read_cstring(
        self, addr: int, cap: int = 4096, *, require_concrete: bool = False
    ) -> bytes:
        sp = self._ctx.getConcreteRegisterValue(self._ctx.registers.sp)
        frame_lo, frame_hi = sp - Limits.trusted_frame_window, sp
        out = bytearray()
        while True:
            if frame_lo <= addr < frame_hi:
                self.fail(
                    f"string argument at 0x{addr:016x} lies in the callee frame "
                    f"[0x{frame_lo:016x},0x{frame_hi:016x})"
                )
            if require_concrete and self._ctx.isMemorySymbolized(MemoryAccess(addr, 1)):
                self.fail(
                    f"format string at 0x{addr:016x} has symbolic (runtime-unknown) bytes"
                )
            byte = self._ctx.getConcreteMemoryValue(addr, True)
            if not byte and not self._ctx.isMemorySymbolized(MemoryAccess(addr, 1)):
                break
            out.append(byte)
            addr += 1
            if len(out) >= cap:
                self.fail(
                    "string argument is not guaranteed to terminate within the cap"
                )
        return bytes(out)

    def _arg_regs(self, count: int, mask: int = 0xFFFFFFFFFFFFFFFF) -> Tuple[int, ...]:
        vals = []
        for i in range(count):
            reg = getattr(self._ctx.registers, f"a{i}", None)
            assert reg is not None, f"register a{i} missing"
            vals.append(self._ctx.getConcreteRegisterValue(reg) & mask)
        return tuple(vals)

    def shim_create_file_plain(self) -> None:
        fbytes, length = self._arg_regs(2)
        logger.debug("create_file_plain(fbytes=0x%016x, len=%u)", fbytes, length)

        if self._ctx.isRegisterSymbolized(self._ctx.registers.a0):
            self.fail("create_file_plain: `fbytes` is symbolic")
        if self._ctx.isRegisterSymbolized(self._ctx.registers.a1):
            self.fail("create_file_plain: `len` is symbolic")

        if length > Limits.file_bytes:
            self.fail(f"create_file_plain: len {length} over the cap")
        elif length % 4 != 0:
            self.fail("create_file_plain: len must be a multiple of 4")
        elif length == 0:
            self.fail("create_file_plain: len must be non-zero")

        self._engine.forbid_callee_frame_alias(fbytes, length)
        self._engine.guard_range(fbytes, length)

        self._ctx.symbolizeRegister(
            self._ctx.registers.a0, f"create_plain_h_{self._tag}"
        )

    def shim_read_file_plain(self) -> None:
        handle, fbytes, len_ptr = self._arg_regs(3)
        self._engine.forbid_callee_frame_alias(len_ptr, 4)
        want = self._ctx.getConcreteMemoryValue(MemoryAccess(len_ptr, 4), True)
        logger.debug(
            "read_file_plain(0x%016x, 0x%016x, *0x%016x=%d)",
            handle,
            fbytes,
            len_ptr,
            want,
        )

        if want > Limits.file_bytes:
            self.fail(f"read_file_plain: len {want} over the cap")
        elif want % 4 != 0:
            self.fail("read_file_plain: len must be a multiple of 4")
        elif want == 0:
            self.fail("read_file_plain: len must be non-zero")

        if self._ctx.isRegisterSymbolized(self._ctx.registers.a1):
            self.fail("read_file_plain: `fbytes` is symbolic")
        if self._ctx.isRegisterSymbolized(self._ctx.registers.a2):
            self.fail("read_file_plain: `len` pointer is symbolic")
        if self._ctx.isMemorySymbolized(MemoryAccess(len_ptr, 4)):
            self.fail("read_file_plain: *len is symbolic")

        self._engine.forbid_callee_frame_alias(fbytes, want)
        self._engine.guard_range(len_ptr, 4)
        self._engine.guard_range(fbytes, want, AccessKind.WRITE)

        for off in range(want):
            self._ctx.untaintMemory(fbytes + off)
            self._ctx.setConcreteMemoryValue(MemoryAccess(fbytes + off, 1), 0, True)
            self._ctx.symbolizeMemory(
                MemoryAccess(fbytes + off, 1), f"read_plain_b{off}_{self._tag}"
            )

        self._ctx.untaintMemory(MemoryAccess(len_ptr, 4))
        self._ctx.setConcreteMemoryValue(MemoryAccess(len_ptr, 4), want, True)
        self._ctx.symbolizeMemory(
            MemoryAccess(len_ptr, 4), f"read_plain_len_{self._tag}"
        )

        actx = self._ctx.getAstContext()
        a0 = self._ctx.registers.a0
        rc = actx.variable(
            self._ctx.newSymbolicVariable(32, f"read_plain_rc_{self._tag}")
        )
        widened = actx.sx(a0.getBitSize() - 32, rc)
        self._ctx.setConcreteRegisterValue(a0, 0)
        self._ctx.assignSymbolicExpressionToRegister(
            self._ctx.newSymbolicExpression(widened, f"read_plain_ret_{self._tag}"), a0
        )
        self._ctx.pushPathConstraint(
            actx.lor(
                [
                    actx.equal(rc, actx.bv(0, 32)),
                    actx.equal(rc, actx.bv(0xFFFFFFFF, 32)),
                ]
            )
        )

    def shim_isqrt(self) -> None:
        a0 = self._ctx.registers.a0

        if not self._ctx.isRegisterSymbolized(a0):
            (n,) = self._arg_regs(1)
            root = math.isqrt(n)
            logger.debug("isqrt(%u) = %u", n, root)
            self._ctx.setConcreteRegisterValue(a0, root)
            return

        actx = self._ctx.getAstContext()
        root = actx.variable(self._ctx.newSymbolicVariable(64, f"isqrt_r_{self._tag}"))
        self._ctx.setConcreteRegisterValue(a0, 0)
        self._ctx.assignSymbolicExpressionToRegister(
            self._ctx.newSymbolicExpression(root, f"isqrt_ret_{self._tag}"), a0
        )
        self._ctx.pushPathConstraint(actx.bvule(root, actx.bv(0xFFFFFFFF, 64)))

    def shim_readc(self) -> None:
        actx = self._ctx.getAstContext()
        a0 = self._ctx.registers.a0
        rc = actx.variable(self._ctx.newSymbolicVariable(32, f"readc_b_{self._tag}"))
        widened = actx.sx(a0.getBitSize() - 32, rc)
        self._ctx.setConcreteRegisterValue(a0, 0)
        self._ctx.assignSymbolicExpressionToRegister(
            self._ctx.newSymbolicExpression(widened, f"readc_ret_{self._tag}"), a0
        )
        self._ctx.pushPathConstraint(
            actx.land(
                [
                    actx.bvsge(rc, actx.bv(0xFFFFFFFF, 32)),
                    actx.bvsle(rc, actx.bv(255, 32)),
                ]
            )
        )

    _CONV1 = frozenset(b"bxdcsp")

    def _format_conversions(self, fmt: bytes) -> list[bytes]:
        out: list[bytes] = []
        i, n = 0, len(fmt)
        while i < n:
            if fmt[i] != 0x25:
                i += 1
                continue
            i += 1
            if i >= n:
                break
            if fmt[i] == 0x25:
                i += 1
                continue
            if fmt[i : i + 3] == b"llx":
                out.append(b"%llx")
                i += 3
                continue
            if fmt[i] in self._CONV1:
                out.append(b"%" + fmt[i : i + 1])
                i += 1
                continue
            i += 1
        return out

    def shim_mini_printf(self) -> None:
        fmt_ptr, *args = self._arg_regs(8)
        fmt = self._read_cstring(fmt_ptr, require_concrete=True)
        logger.debug("mini_printf(fmt=%r, regs=%s)", fmt.decode(errors="replace"), args)

        if self._ctx.isRegisterSymbolized(self._ctx.registers.a0):
            self.fail("mini_printf: format pointer is symbolic")

        conversions = self._format_conversions(fmt)

        if self._ctx.isRegisterSymbolized(self._ctx.registers.sp):
            self.fail("mini_printf: SP is symbolic, cannot fetch stack varargs")
        sp = self._ctx.getConcreteRegisterValue(self._ctx.registers.sp)

        for k in range(len(conversions) - len(args)):
            args.append(
                self._ctx.getConcreteMemoryValue(MemoryAccess(sp + k * 8, 8), True)
            )

        def is_symbolic_arg(idx: int) -> bool:
            if idx < 8:
                return self._ctx.isRegisterSymbolized(
                    getattr(self._ctx.registers, f"a{idx}")
                )
            return self._ctx.isMemorySymbolized(MemoryAccess(sp + (idx - 8) * 8, 8))

        for i, tok in enumerate(conversions):
            if tok in (b"%x", b"%d"):
                args[i] &= 0xFFFFFFFF
                if tok == b"%d" and args[i] & 0x80000000:
                    args[i] -= 0x100000000
            if tok == b"%s":
                if is_symbolic_arg(i + 1):
                    self.fail(
                        f"mini_printf: `%s` pointer 0x{args[i]:016x} (arg {i}) is symbolic"
                    )
                args[i] = self._read_cstring(args[i]).decode("ascii", errors="replace")

        logger.debug(
            "mini_printf -> %d conversion(s): %s",
            len(conversions),
            [t.decode() for t in conversions],
        )

        self._ctx.setConcreteRegisterValue(self._ctx.registers.a0, 0)
