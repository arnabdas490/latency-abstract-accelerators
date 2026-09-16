#!/usr/bin/env python3

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ITERATIONS = [0, 1, 2, 4, 7]

DATA = ROOT / "examples/v0_6_data.json"
RTL = ROOT / "baselines/v0_8_fixed_li_kernels.sv"
STORED_HASH = ROOT / "results/v0_8_shared_rtl.sha256"
RESULTS = ROOT / "results/v0_8_shared_rtl_runtime_sweep.csv"

DESIGNS = {
    "opaque_li": ROOT / "baselines/v0_8_fixed_li.futil",
    "manual_static": ROOT / "baselines/v0_8_fixed_manual_static.futil",
    "latency_abstract": ROOT / "examples/generated/v0_8_fixed_la.futil",
}


def run(cmd):
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"Command failed ({result.returncode}): "
            + " ".join(str(x) for x in cmd)
        )
    return result


def set_input(n):
    payload = {
        "mem": {
            "data": [10, n, 0, 0],
            "format": {
                "numeric_type": "bitnum",
                "is_signed": False,
                "width": 32,
            },
        }
    }
    DATA.write_text(json.dumps(payload, indent=2) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def simulate(path):
    result = run(
        [
            "fud2",
            str(path.relative_to(ROOT)),
            "-s",
            "sim.data=examples/v0_6_data.json",
            "--to",
            "dat",
            "--through",
            "verilator",
        ]
    )

    text = result.stdout + "\n" + result.stderr

    cycle_match = re.search(
        r'"cycles"\s*:\s*(\d+)',
        text,
    )

    mem_match = re.search(
        r'"mem"\s*:\s*\[\s*'
        r'(\d+)\s*,\s*'
        r'(\d+)\s*,\s*'
        r'(\d+)\s*,\s*'
        r'(\d+)\s*\]',
        text,
    )

    if cycle_match is None or mem_match is None:
        print(text)
        raise RuntimeError(
            f"Could not parse simulation output for {path}"
        )

    cycles = int(cycle_match.group(1))
    memory = [
        int(mem_match.group(i))
        for i in range(1, 5)
    ]

    return cycles, memory


def main():
    rows = []

    try:
        # Reconstruct canonical fixed-latency RTL from the contracts.
        run([sys.executable, "frontend/elaborate_v0_8_fixed_li.py"])

        actual_hash = sha256(RTL)
        expected_hash = STORED_HASH.read_text().split()[0]

        print("===== SHARED RTL CHECK =====")
        print(f"expected = {expected_hash}")
        print(f"actual   = {actual_hash}")

        if actual_hash != expected_hash:
            raise RuntimeError(
                "Shared RTL hash does not match canonical V0.8 RTL."
            )

        # Resolve timing and emit the LA/static composition.
        run([sys.executable, "frontend/elaborate_v0_8_fixed_la.py"])

        after_la_hash = sha256(RTL)
        if after_la_hash != actual_hash:
            raise RuntimeError(
                "LA elaboration unexpectedly modified shared RTL."
            )

        print("Shared RTL preserved across LI and LA compositions.")

        for n in ITERATIONS:
            print(f"\n===== N={n} =====")
            set_input(n)

            measurements = {}

            for name, path in DESIGNS.items():
                cycles, memory = simulate(path)

                expected_result = 0 if n == 0 else 23
                expected_memory = [10, n, expected_result, 0]
                correct = memory == expected_memory
                measurements[name] = cycles

                rows.append(
                    {
                        "runtime_iterations": n,
                        "design": name,
                        "cycles": cycles,
                        "functional_correct": correct,
                        "rtl_sha256": actual_hash,
                    }
                )

                print(
                    f"{name:18s}: "
                    f"cycles={cycles:3d}, "
                    f"memory={memory}, "
                    f"correct={correct}"
                )

            print(
                "opaque-LA delta: "
                f"{measurements['opaque_li'] - measurements['latency_abstract']}"
            )
            print(
                "manual == LA: "
                f"{measurements['manual_static'] == measurements['latency_abstract']}"
            )

        RESULTS.parent.mkdir(parents=True, exist_ok=True)

        with RESULTS.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "runtime_iterations",
                    "design",
                    "cycles",
                    "functional_correct",
                    "rtl_sha256",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nSaved results to {RESULTS.relative_to(ROOT)}")

    finally:
        # Always restore the canonical N=4 input.
        set_input(4)
        print("Restored canonical input N=4.")


if __name__ == "__main__":
    main()
