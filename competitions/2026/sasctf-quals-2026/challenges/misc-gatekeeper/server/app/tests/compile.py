import subprocess
from pathlib import Path


class CompileError(RuntimeError):
    pass


def make_compile(
    makefile_dir: Path,
    src: Path,
    out_dir: Path,
    extra_cflags: str = "",
    target: str = "prog",
    comptime_seed: int = 1,
) -> Path:
    """Build a single RV64 program blob via the example_program Makefile."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log = (out_dir / "build.log").open("w")

    cmd = [
        "make",
        "-C",
        str(makefile_dir),
        f"SRCS={src.absolute()}",
        f"BUILD_DIR={out_dir.absolute()}",
        f"EXE_NAME={target}",
        f"COMPTIME_SEED={comptime_seed}",
        f"EXTRA_CFLAGS={extra_cflags}",
        "all",
    ]
    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    log.close()
    if proc.returncode != 0:
        raise CompileError(f"make failed; see {out_dir / 'build.log'}")
    return out_dir / f"{target}.bin"
