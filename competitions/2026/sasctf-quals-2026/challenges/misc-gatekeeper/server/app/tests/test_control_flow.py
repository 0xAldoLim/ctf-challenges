"""Unit tests for the indirect-transfer resolver (verifier/control_flow.py)."""
from triton import ARCH, OPERAND, Instruction, TritonContext

from verifier.control_flow import ControlFlow, TransferKind
from verifier.engine import Verifier

MASK64 = 0xFFFFFFFFFFFFFFFF
_CTX = TritonContext(ARCH.RV64)


def _decode(word: int, size: int = 4) -> Instruction:
    i = Instruction(0x300000, word.to_bytes(size, "little"))
    _CTX.disassembly(i)
    return i


def _base_name(inst: Instruction):
    b = ControlFlow._base_register(inst)
    return b.getName() if b is not None else None


def _first_imm(inst: Instruction) -> int:
    # Exactly how _pin_indirect picks the displacement.
    for op in inst.getOperands():
        if op.getType() == OPERAND.IMM:
            return op.getValue()
    return 0


def _jalr(rd: int, rs1: int, imm: int) -> int:
    # I-type: imm[11:0] | rs1 | funct3=0 | rd | opcode=0x67
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (rd << 7) | 0x67


def test_classification_of_transfers():
    assert ControlFlow.classify("jalr a5, a4, 0") is TransferKind.INDIRECT_JUMP
    assert ControlFlow.classify("jr a5") is TransferKind.INDIRECT_JUMP
    assert ControlFlow.classify("ret") is TransferKind.INDIRECT_JUMP
    assert ControlFlow.classify("jal 8") is TransferKind.DIRECT_JUMP
    assert ControlFlow.classify("j 8") is TransferKind.DIRECT_JUMP
    assert ControlFlow.classify("beqz a0, 8") is TransferKind.BRANCH
    assert ControlFlow.classify("addi a0, a0, 1") is TransferKind.SEQUENTIAL


# --- each indirect form, named ---------------------------------------------

def test_named_indirect_forms():
    # jalr (3-op and the rd=ra 2-op): base is rs1, the last register operand.
    assert _base_name(_decode(0x000707E7)) == "x14"  # jalr a5, a4, 0   rs1=a4
    assert _base_name(_decode(0x004707E7)) == "x14"  # jalr a5, 4(a4)   rs1=a4
    assert _base_name(_decode(0x000780E7)) == "x15"  # jalr a5          rs1=a5
    assert _base_name(_decode(0xFFF70767)) == "x14"  # jalr a4, a4, -1  rs1=a4
    # jr: explicit base register -> pinned on rs1.
    assert _base_name(_decode(0x00078067)) == "x15"  # jr a5            rs1=a5
    # ret: ra is implicit, there is no register operand -> declined (None).
    assert _base_name(_decode(0x00008067)) is None   # ret


def test_call_and_tail_are_two_instruction_pseudos():
    # 'call'/'tail' are not single instructions; they expand to auipc + an
    # ordinary jalr/jr, so the transfer half is one of the covered forms and no
    # instruction ever has head 'call'/'tail'.
    assert ControlFlow.classify(_decode(0x00000097).getDisassembly()) is TransferKind.SEQUENTIAL  # auipc ra
    call_jalr = _decode(0x000080E7)  # jalr ra, 0(ra)  (call's second half)
    assert ControlFlow.classify(call_jalr.getDisassembly()) is TransferKind.INDIRECT_JUMP
    assert _base_name(call_jalr) == "x1"
    tail_jr = _decode(0x00030067)    # jr t1            (tail's second half)
    assert ControlFlow.classify(tail_jr.getDisassembly()) is TransferKind.INDIRECT_JUMP
    assert _base_name(tail_jr) == "x6"


# --- exhaustive over every jalr operand layout -----------------------------

def test_every_indirect_form_is_pinned_correctly_or_declined():
    # Sweep all rd x all rs1 x a spread of 12-bit displacements (incl. both
    # extremes). The whole jalr encoding space collapses to exactly three heads
    # -- jalr / jr / ret. Whenever the resolver pins (a base register is
    # present, i.e. jalr/jr), the target it builds must be base + displacement:
    # base == rs1 and the single immediate read == the encoded one. The only
    # form without a register operand is ret (implicit ra), which is declined
    # (None) and left to the per-step guard.
    imms = [0, 1, -1, 2, 4, 8, 0x7FF, -0x800, 0x7FC, -0x7FC, 0x555, -0x556]
    heads = set()
    for rd in range(32):
        for rs1 in range(32):
            for imm in imms:
                inst = _decode(_jalr(rd, rs1, imm))
                disasm = inst.getDisassembly()
                heads.add(disasm.split(" ", 1)[0])
                assert ControlFlow.classify(disasm) is TransferKind.INDIRECT_JUMP, disasm
                base = _base_name(inst)
                if base is None:
                    assert disasm == "ret", disasm  # the only register-less form
                    continue
                ctx = f"rd={rd} rs1={rs1} imm={imm} ({disasm})"
                assert base == f"x{rs1}", f"{ctx}: base {base} != x{rs1}"
                assert (_first_imm(inst) & MASK64) == (imm & MASK64), f"{ctx}: bad imm"
    assert heads == {"jalr", "jr", "ret"}, heads


def test_non_jalr_instructions_are_never_classified_indirect():
    # A multi-operand / multi-immediate instruction classified as indirect would
    # reach the displacement extraction; none do.
    for note, word in {
        "addi a0, a1, 7": 0x00758513,
        "add a0, a1, a2": 0x00C58533,
        "lw a0, 8(a1)": 0x0085A503,
        "sw a0, 8(a1)": 0x00A5A423,
        "lui a0, 0x12345": 0x12345537,
        "auipc a0, 0x10": 0x00010517,
        "jal ra, 8": 0x008000EF,
        "beq a0, a1, 8": 0x00B50463,
        "slli a0, a1, 3": 0x00359513,
        "ld a0, 16(a1)": 0x0105B503,
        "sd a0, 16(a1)": 0x00A5B823,
    }.items():
        kind = ControlFlow.classify(_decode(word).getDisassembly())
        assert kind is not TransferKind.INDIRECT_JUMP, f"{note}: classified {kind}"


def test_pin_indirect_includes_displacement_end_to_end():
    # a5 is symbolic but provably 0x300200; `jalr ra, 8(a5)` must pin 0x300208,
    # not 0x300200 (the displacement is part of the target).
    v = Verifier()
    ctx, actx = v._ctx, v._actx
    a5 = ctx.registers.x15
    ctx.setConcreteRegisterValue(a5, 0x300200)
    sv = ctx.symbolizeRegister(a5)
    ctx.pushPathConstraint(actx.equal(actx.variable(sv), actx.bv(0x300200, 64)))
    inst = Instruction(0x300000, _jalr(1, 15, 8).to_bytes(4, "little"))
    ctx.disassembly(inst)
    assert v._flow.resolve(inst) == 0x300208
