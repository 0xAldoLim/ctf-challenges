"""Frame-alias guard: a trusted-call buffer argument must not overlap the slice
of stack the callee uses for its own frame, `[sp - trusted_frame_window, sp)`.

The engine shims trusted stubs and models their return through the `ra` register,
so it never sees the stub spill/reload `ra` (and locals) in that slice. A buffer
argument aliasing it desyncs verifier from runtime -- most sharply, a
`read_file_plain` out-buffer pointed at the stub's own saved-`ra` slot makes the
real `ret` jump into attacker-supplied file bytes the verifier never inspected
(a stage-1 escape). These cases live as `unsafe_*` programs under c_testcases/
(so the generic suite also exercises them); here we additionally pin the precise
rejection reason per location, and confirm a legitimate non-stack buffer is not
over-rejected.
"""

import os
import shutil
from pathlib import Path

import pytest

from verifier.engine import Verifier

from .compile import CompileError, make_compile

_TESTCASES = Path(__file__).parent / "c_testcases"
_MAKE_DIR = Path(__file__).resolve().parents[3] / "static" / "example_program"


def _toolchain_available() -> bool:
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    return shutil.which(f"{prefix}gcc") is not None


def _verify(src_name: str, build_root: Path):
    if not _toolchain_available():
        pytest.skip("riscv64 cross-compilation toolchain not available in PATH")
    src = _TESTCASES / src_name
    try:
        blob = make_compile(
            _MAKE_DIR,
            src,
            build_root / src.stem,
            extra_cflags=f"-O0 -I{_MAKE_DIR}",
            target=src.stem,
            comptime_seed=1,
        ).read_bytes()
    except CompileError as exc:  # pragma: no cover
        pytest.skip(f"failed to compile {src_name}: {exc}")
    return Verifier().verify(blob)


@pytest.fixture(scope="module")
def build_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("callee_frame_alias")


# (source file, substring that must appear in the rejection reason)
_REJECTED = [
    ("unsafe_read_file_plain_frame_overwrite.c", "aliases the callee frame"),
    ("unsafe_create_file_plain_src_in_frame.c", "aliases the callee frame"),
    ("unsafe_mini_printf_fmt_in_frame.c", "lies in the callee frame"),
]


@pytest.mark.parametrize(
    "src_name,reason", _REJECTED, ids=[c[0][:-2] for c in _REJECTED]
)
def test_in_frame_argument_rejected(
    src_name: str, reason: str, build_root: Path
) -> None:
    report = _verify(src_name, build_root)
    assert not report.passed, f"{src_name} must be rejected"
    assert reason in report.issue, (
        f"{src_name} rejected for the wrong reason: {report.issue!r} "
        f"(expected substring {reason!r})"
    )


def test_data_segment_buffer_not_over_rejected(build_root: Path) -> None:
    report = _verify("safe_data_buffer_trusted_calls.c", build_root)
    assert report.passed, (
        f"a data-segment buffer (below sp, outside the frame window) must still "
        f"verify, but got: {report.issue}"
    )
