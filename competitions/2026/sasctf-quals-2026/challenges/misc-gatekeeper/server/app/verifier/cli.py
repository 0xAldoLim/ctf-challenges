#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

from .engine import Verifier


def _parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="verifier", description="screen an RV64 guest image"
    )
    ap.add_argument("image", type=Path, help="raw RV64 program image to screen")
    ap.add_argument(
        "-q", "--quiet", action="store_true", help="hide the engine's debug trace"
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.DEBUG,
        format="%(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    verdict = Verifier().verify(args.image.read_bytes())
    print(verdict)
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
