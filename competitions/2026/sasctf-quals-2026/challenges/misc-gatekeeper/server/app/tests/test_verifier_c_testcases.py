import os
import shutil
from pathlib import Path

import pytest

from verifier.engine import Verifier

from .compile import CompileError, make_compile

TESTCASE_DIR = Path(__file__).parent / "c_testcases"
# The example_program Makefile (and headers) used to build the testcases.
MAKE_DIR = Path(__file__).resolve().parents[3] / "static" / "example_program"


def _toolchain_available() -> bool:
    cross_prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    return shutil.which(f"{cross_prefix}gcc") is not None


def _discover_testcases() -> list[Path]:
    if not TESTCASE_DIR.exists():
        return []
    return sorted(TESTCASE_DIR.glob("*.c"))


@pytest.fixture(scope="session")
def testcase_build_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("verifier_c_testcases")


@pytest.mark.parametrize("src_path", _discover_testcases(), ids=lambda p: p.stem)
def test_c_testcases(src_path: Path, testcase_build_root: Path) -> None:
    if not _toolchain_available():
        pytest.skip("riscv64 cross-compilation toolchain not available in PATH")

    out_dir = testcase_build_root / src_path.stem
    try:
        bin_path = make_compile(
            MAKE_DIR,
            src_path,
            out_dir,
            extra_cflags=f"-O0 -I{MAKE_DIR}",
            target=src_path.stem,
            comptime_seed=1,
        )
    except CompileError as exc:  # pragma: no cover - compile failures reported as skip
        pytest.skip(f"failed to compile {src_path.name}: {exc}")

    program_blob = bin_path.read_bytes()
    report = Verifier().verify(program_blob)

    if src_path.name.startswith("safe_"):
        assert (
            report.passed
        ), f"expected {src_path.name} to pass, but got: {report.issue}"
    elif src_path.name.startswith("unsafe_"):
        assert (
            not report.passed
        ), f"expected {src_path.name} to fail, but verification passed"
    else:
        pytest.fail(f"unknown testcase category for {src_path.name}")
