#!/usr/bin/env python3
import subprocess
import sys
import os

FLAG = "SAS{placeholder}"
SIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim")
SIM_BIN = os.path.join(SIM_DIR, "obj_dir", "Vtop")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ciphertext.hex")


def build_sim():
    print("[*] Building simulation...")
    result = subprocess.run(
        ["make", "all"], cwd=SIM_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[!] Build failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("[+] Build successful.")


def run_sim(flag_str):
    print(f"[*] Running simulation with flag: {flag_str}")
    result = subprocess.run(
        [SIM_BIN, flag_str], capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"[!] Simulation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def main():
    flag = FLAG
    if len(sys.argv) > 1:
        flag = sys.argv[1]

    if not os.path.exists(SIM_BIN):
        build_sim()

    ciphertext_hex = run_sim(flag)

    if not ciphertext_hex:
        print("[!] No output from simulation.", file=sys.stderr)
        sys.exit(1)

    with open(OUTPUT_FILE, "w") as f:
        f.write(ciphertext_hex + "\n")

    print(f"[+] Ciphertext written to {OUTPUT_FILE}")
    print(f"[+] Content:\n{ciphertext_hex}")


if __name__ == "__main__":
    main()
