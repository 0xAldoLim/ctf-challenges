import json
import logging
import os
import resource
import sys

logging.disable(logging.CRITICAL)

_cap = int(os.getenv("VERIFY_MEM_MB", "4608")) * 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_AS, (_cap, _cap))
except (ValueError, OSError):
    pass

from verifier.engine import Verifier


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"passed": False, "issue": "usage: verify_worker <program>"}))
        return 2
    try:
        with open(sys.argv[1], "rb") as fh:
            blob = fh.read()
        report = Verifier().verify(blob)
    except MemoryError:
        print(
            json.dumps({"passed": False, "issue": "verification exceeded memory limit"})
        )
        return 3
    except Exception as exc:
        print(json.dumps({"passed": False, "issue": f"internal error: {exc}"}))
        return 4

    print(json.dumps({"passed": bool(report.passed), "issue": report.issue}))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
