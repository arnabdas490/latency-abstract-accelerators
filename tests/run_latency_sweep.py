#!/usr/bin/env python3

import csv
import re
import subprocess
import sys
from pathlib import Path

LATENCIES = [1, 2, 3, 4, 5]
RESULTS = Path("results/v0_2_latency_sweep.csv")


def run(cmd):
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            + " ".join(cmd)
        )

    return result.stdout + "\n" + result.stderr


def main():
    rows = []

    for latency in LATENCIES:
        print(f"\n=== Testing L={latency} ===")

        run([
            sys.executable,
            "generators/toy_generator.py",
            "--latency",
            str(latency),
        ])

        run([
            sys.executable,
            "frontend/elaborate_v0_2.py",
        ])

        output = run([
            "fud2",
            "examples/generated/v0_2_generated.futil",
            "-s",
            "sim.data=examples/v0_1_data.json",
            "--to",
            "dat",
            "--through",
            "verilator",
        ])

        cycle_match = re.search(r'"cycles"\s*:\s*(\d+)', output)
        mem_match = re.search(
            r'"mem"\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]',
            output,
        )

        if cycle_match is None or mem_match is None:
            raise RuntimeError(
                f"Could not parse simulator output for L={latency}"
            )

        cycles = int(cycle_match.group(1))
        mem0 = int(mem_match.group(1))
        mem1 = int(mem_match.group(2))

        predicted = 12 + 5 * latency
        correct = (mem0 == 5 and mem1 == 5)
        prediction_match = (cycles == predicted)

        rows.append({
            "latency": latency,
            "predicted_cycles": predicted,
            "measured_cycles": cycles,
            "correct": correct,
            "prediction_match": prediction_match,
        })

        print(
            f"L={latency}: "
            f"predicted={predicted}, "
            f"measured={cycles}, "
            f"correct={correct}"
        )

    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "latency",
                "predicted_cycles",
                "measured_cycles",
                "correct",
                "prediction_match",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # Restore our canonical V0.2 example to L=3.
    run([
        sys.executable,
        "generators/toy_generator.py",
        "--latency",
        "3",
    ])
    run([
        sys.executable,
        "frontend/elaborate_v0_2.py",
    ])

    print(f"\nSaved results to {RESULTS}")


if __name__ == "__main__":
    main()
