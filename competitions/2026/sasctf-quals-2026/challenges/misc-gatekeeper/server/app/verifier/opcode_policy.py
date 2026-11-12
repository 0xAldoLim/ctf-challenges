# base integer register/immediate ALU
_ALU = {
    "lui",
    "auipc",
    "addi",
    "slti",
    "sltiu",
    "xori",
    "ori",
    "andi",
    "slli",
    "srli",
    "srai",
    "add",
    "sub",
    "sll",
    "slt",
    "sltu",
    "xor",
    "srl",
    "sra",
    "or",
    "and",
}
# 32-bit "*w" forms unique to RV64
_WORD = {
    "addiw",
    "slliw",
    "srliw",
    "sraiw",
    "addw",
    "subw",
    "sllw",
    "srlw",
    "sraw",
}
# loads and stores
_MEM = {"lb", "lh", "lw", "lbu", "lhu", "lwu", "ld", "sb", "sh", "sw", "sd"}
# branches, jumps, and the accept terminator
_FLOW = {
    "jal",
    "jalr",
    "ret",
    "ebreak",
    "beq",
    "bne",
    "blt",
    "bge",
    "bltu",
    "bgeu",
}
# M extension, both widths
_MULDIV = {
    "mul",
    "mulh",
    "mulhsu",
    "mulhu",
    "div",
    "divu",
    "rem",
    "remu",
    "mulw",
    "divw",
    "divuw",
    "remw",
    "remuw",
}
# assembler pseudo-instructions
_PSEUDO = {
    "nop",
    "li",
    "mv",
    "not",
    "neg",
    "negw",
    "sext.w",
    "seqz",
    "snez",
    "sltz",
    "sgtz",
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
    "j",
    "jr",
    "call",
}

_ACCEPTED = frozenset(_ALU | _WORD | _MEM | _FLOW | _MULDIV | _PSEUDO)


class OpcodePolicy:
    @staticmethod
    def _head(disassembly: str) -> str:
        return disassembly.lower().split(" ", 1)[0].strip()

    def permits(self, disassembly: str) -> bool:
        return self._head(disassembly) in _ACCEPTED

    def __contains__(self, disassembly: str) -> bool:
        return self.permits(disassembly)


POLICY = OpcodePolicy()
