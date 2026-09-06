#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ITERATIONS = [1, 2, 4, 7]

DATA = Path("examples/v0_6_data.json")
RESULTS = Path("results/v0_8_three_way_runtime_sweep.csv")

DESIGNS = {
    "true_li": Path("baselines/v0_8_true_li.futil"),
    "manual_static": Path("baselines/v0_8_manual_static.futil"),
    "latency_abstract": Path(
        "examples/generated/v0_6_dynamic_pair.futil"
    ),
}


def set_input(n):
    data = {
        "mem": {
            "data": [10, n, 0, 0],
            "format": {
                "numeric_type": "bitnum",
                "is_signed": False,
                "width": 32
            }
        }
    }

    DATA.write_text(json.dumps(data, indent=2) + "\n")


def simulate(path):
    result = subprocess.run(
        [
            "fud2",
            str(path),
            "-s",
            "sim.data=examples/v0_6_data.json",
            "--to",
            "dat",
            "--through",
            "verilator",
        ],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"Simulation failed for {path}"
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
        raise RuntimeError(
            f"Could not parse output for {path}"
        )

    cycles = int(cycle_match.group(1))

    memory = [
        int(mem_match.group(i))
        for i in range(1, 5)
    ]

    return cycles, memory


def main():
    rows = []

    for n in ITERATIONS:
        print(f"\n=== Runtime iterations N={n} ===")

        set_input(n)

        measurements = {}

        for name, path in DESIGNS.items():
            cycles, memory = simulate(path)

            correct = memory == [10, n, 23, 0]

            measurements[name] = cycles

            rows.append({
                "runtime_iterations": n,
                "design": name,
                "cycles": cycles,
                "functional_correct": correct,
            })

            print(
                f"{name:17s}: "
                f"cycles={cycles}, "
                f"correct={correct}"
            )

        print(
            "delta static-LI: "
            f"{measurements['manual_static'] - measurements['true_li']}"
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
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    # Restore canonical runtime input.
    set_input(4)

    print(f"\nSaved results to {RESULTS}")
    print("Restored canonical N=4.")


if __name__ == "__main__":
    main()
