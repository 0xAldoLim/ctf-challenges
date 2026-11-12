"""Guard: Limits.trusted_frame_window must cover the wrappers' real stack use.

The engine re-taints `trusted_frame_window` bytes below sp after each trusted
call to model the frame the U-mode wrapper leaves on the guest stack (see
engine._clobber_trusted_frame). That is only sound if the window is at least as
large as the deepest stack a wrapper can use below the entry sp. This test
re-derives that depth from the built wrappers ELF and fails if the assumption
ever breaks (e.g. someone adds a bigger/recursive/indirect-calling routine), so
the soundness coupling cannot silently rot.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from verifier.limits import Limits

_ELF = (
    Path(__file__).resolve().parents[3]
    / "sources"
    / "trusted_lib"
    / "build"
    / "trusted_lib.elf"
)


def _objdump() -> str | None:
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    return shutil.which(f"{prefix}objdump")


def _max_stack_depth(disassembly: str) -> int:
    """Deepest stack (bytes) any entry can use below its caller's sp."""
    funcs: dict[str, dict] = {}
    cur: dict | None = None
    for line in disassembly.splitlines():
        head = re.match(r"^[0-9a-f]+ <([^>]+)>:", line)
        if head:
            cur = {"frame": 0, "calls": []}
            funcs[head.group(1)] = cur
            continue
        if cur is None:
            continue
        adj = re.search(r"addi\s+sp,sp,(-\d+)", line)
        if adj:
            cur["frame"] = max(cur["frame"], -int(adj.group(1)))
        call = re.search(r"\bjal\s+\w+,[0-9a-f]+\s+<([^>]+)>", line)
        if call:
            cur["calls"].append(call.group(1))
        elif re.search(r"\bjalr\b", line):  # indirect call -> static depth unknown
            cur["calls"].append("<indirect>")

    def depth(name: str, seen: frozenset[str]) -> int:
        fn = funcs.get(name)
        if fn is None or name in seen:  # external/recursive: count only its frame
            return fn["frame"] if fn else 0
        best = 0
        for callee in fn["calls"]:
            assert callee != "<indirect>", f"indirect call in {name}: depth is unsound"
            best = max(best, depth(callee, seen | {name}))
        return fn["frame"] + best

    return max((depth(n, frozenset()) for n in funcs), default=0)


@pytest.mark.skipif(not _ELF.exists(), reason="trusted_lib.elf not built")
def test_window_covers_wrappers_depth() -> None:
    objdump = _objdump()
    if objdump is None:
        pytest.skip("riscv64 objdump not available")
    dis = subprocess.run(
        [objdump, "-d", str(_ELF)], capture_output=True, text=True, check=True
    ).stdout
    depth = _max_stack_depth(dis)
    assert depth > 0, "could not parse any stack frame from the wrappers"
    assert depth <= Limits.trusted_frame_window, (
        f"wrappers use {depth} B below the entry sp, exceeding "
        f"trusted_frame_window={Limits.trusted_frame_window}; raise the window"
    )
