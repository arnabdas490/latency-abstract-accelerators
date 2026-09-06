#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

PAIRS = [
    (2, 5),
    (5, 2),
    (3, 3),
    (4, 7),
    (8, 3),
]

RESULTS = Path("results/v0_3_pair_sweep.csv")
REPORT = Path("results/v0_3_pair_elaboration.json")


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


def generate_contract(name, latency, out):
    run([
        sys.executable,
        "generators/toy_generator.py",
        "--name",
        name,
        "--latency",
        str(latency),
        "--out",
        out,
    ])


def main():
    rows = []

    for latency_a, latency_b in PAIRS:
        print(f"\n=== Testing (L_A, L_B)=({latency_a}, {latency_b}) ===")

        generate_contract(
            "kernel_a",
            latency_a,
            "contracts/kernel_a.json",
        )

        generate_contract(
            "kernel_b",
            latency_b,
            "contracts/kernel_b.json",
        )

        run([
            sys.executable,
            "frontend/elaborate_v0_3_pair.py",
        ])

        report = json.loads(REPORT.read_text())

        target = max(latency_a, latency_b)
        expected_delay_a = target - latency_a
        expected_delay_b = target - latency_b

        report_target = report["target_latency"]
        report_delay_a = report["kernel_a"]["alignment_delay"]
        report_delay_b = report["kernel_b"]["alignment_delay"]

        relations_correct = (
            report_target == target
            and report_delay_a == expected_delay_a
            and report_delay_b == expected_delay_b
        )

        output = run([
            "fud2",
            "examples/generated/v0_3_pair.futil",
            "-s",
            "sim.data=examples/v0_3_data.json",
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
                f"Could not parse simulator output for "
                f"({latency_a}, {latency_b})"
            )

        cycles = int(cycle_match.group(1))
        mem0 = int(mem_match.group(1))
        mem1 = int(mem_match.group(2))

        predicted_cycles = target + 2

        functional_correct = (
            mem0 == 10
            and mem1 == 23
        )

        timing_match = cycles == predicted_cycles

        rows.append({
            "latency_a": latency_a,
            "latency_b": latency_b,
            "target_latency": target,
            "delay_a": expected_delay_a,
            "delay_b": expected_delay_b,
            "predicted_cycles": predicted_cycles,
            "measured_cycles": cycles,
            "relations_correct": relations_correct,
            "functional_correct": functional_correct,
            "timing_match": timing_match,
        })

        print(
            f"T={target}, "
            f"D_A={expected_delay_a}, "
            f"D_B={expected_delay_b}, "
            f"predicted={predicted_cycles}, "
            f"measured={cycles}, "
            f"relations={relations_correct}, "
            f"correct={functional_correct}"
        )

    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "latency_a",
                "latency_b",
                "target_latency",
                "delay_a",
                "delay_b",
                "predicted_cycles",
                "measured_cycles",
                "relations_correct",
                "functional_correct",
                "timing_match",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # Restore canonical V0.3 configuration.
    generate_contract(
        "kernel_a",
        2,
        "contracts/kernel_a.json",
    )

    generate_contract(
        "kernel_b",
        5,
        "contracts/kernel_b.json",
    )

    run([
        sys.executable,
        "frontend/elaborate_v0_3_pair.py",
    ])

    print(f"\nSaved results to {RESULTS}")
    print("Restored canonical configuration: (L_A, L_B)=(2, 5)")


if __name__ == "__main__":
    main()
