#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

VALID_PAIRS = [
    (2, 5),
    (5, 2),
    (3, 3),
]

INVALID_PAIRS = [
    (4, 7),
    (8, 3),
]

ITERATIONS = [1, 2, 4, 7]

RESULTS = Path("results/v0_7_dynamic_sweep.csv")
DATA = Path("examples/v0_6_data.json")
OUTPUT = Path("examples/generated/v0_6_dynamic_pair.futil")


def run(cmd, check=True):
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
    )

    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            + " ".join(cmd)
        )

    return result


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


def set_runtime_iterations(n):
    data = {
        "mem": {
            "data": [10, n, 0, 0],
            "format": {
                "numeric_type": "bitnum",
                "is_signed": False,
                "width": 32,
            },
        }
    }

    DATA.write_text(json.dumps(data, indent=2) + "\n")


def configure_pair(latency_a, latency_b):
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


def main():
    rows = []

    # ---------------------------------------------------------
    # Accepted configurations:
    # vary both elaboration-time latency and runtime iteration N.
    # ---------------------------------------------------------
    for latency_a, latency_b in VALID_PAIRS:
        target = max(latency_a, latency_b)
        delay_a = target - latency_a
        delay_b = target - latency_b

        for n in ITERATIONS:
            print(
                f"\n=== VALID "
                f"(L_A,L_B)=({latency_a},{latency_b}), "
                f"N={n} ==="
            )

            configure_pair(latency_a, latency_b)
            set_runtime_iterations(n)

            gate = run([
                sys.executable,
                "frontend/elaborate_v0_6_dynamic.py",
            ])

            output = run([
                "fud2",
                "examples/generated/v0_6_dynamic_pair.futil",
                "-s",
                "sim.data=examples/v0_6_data.json",
                "--to",
                "dat",
                "--through",
                "verilator",
            ])

            text = output.stdout + "\n" + output.stderr

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
                    "Could not parse simulator output."
                )

            cycles = int(cycle_match.group(1))

            mem = [
                int(mem_match.group(i))
                for i in range(1, 5)
            ]

            predicted = 7 + n * (target + 2)

            functional_correct = (
                mem == [10, n, 23, 0]
            )

            timing_match = (
                cycles == predicted
            )

            rows.append({
                "case": "accepted",
                "latency_a": latency_a,
                "latency_b": latency_b,
                "target_latency": target,
                "delay_a": delay_a,
                "delay_b": delay_b,
                "runtime_iterations": n,
                "predicted_cycles": predicted,
                "measured_cycles": cycles,
                "contract_accepted": True,
                "hardware_emitted": OUTPUT.exists(),
                "functional_correct": functional_correct,
                "timing_match": timing_match,
            })

            print(
                f"T={target}, "
                f"D_A={delay_a}, "
                f"D_B={delay_b}, "
                f"predicted={predicted}, "
                f"measured={cycles}, "
                f"correct={functional_correct}, "
                f"timing_match={timing_match}"
            )

    # ---------------------------------------------------------
    # Rejected configurations from the original pair sweep.
    # Runtime N is irrelevant because elaboration must stop first.
    # ---------------------------------------------------------
    for latency_a, latency_b in INVALID_PAIRS:
        print(
            f"\n=== EXPECTED REJECTION "
            f"(L_A,L_B)=({latency_a},{latency_b}) ==="
        )

        configure_pair(latency_a, latency_b)
        set_runtime_iterations(4)

        gate = run([
            sys.executable,
            "frontend/elaborate_v0_6_dynamic.py",
        ], check=False)

        target = max(latency_a, latency_b)
        rejected = gate.returncode != 0
        emitted = OUTPUT.exists()

        rows.append({
            "case": "rejected",
            "latency_a": latency_a,
            "latency_b": latency_b,
            "target_latency": target,
            "delay_a": target - latency_a,
            "delay_b": target - latency_b,
            "runtime_iterations": 4,
            "predicted_cycles": "",
            "measured_cycles": "",
            "contract_accepted": False,
            "hardware_emitted": emitted,
            "functional_correct": "",
            "timing_match": "",
        })

        print(
            f"exit_code={gate.returncode}, "
            f"rejected={rejected}, "
            f"hardware_emitted={emitted}"
        )

        if not rejected:
            raise RuntimeError(
                "Expected contract rejection, but configuration passed."
            )

        if emitted:
            raise RuntimeError(
                "Hardware exists after rejected configuration."
            )

    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "latency_a",
                "latency_b",
                "target_latency",
                "delay_a",
                "delay_b",
                "runtime_iterations",
                "predicted_cycles",
                "measured_cycles",
                "contract_accepted",
                "hardware_emitted",
                "functional_correct",
                "timing_match",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    # Restore canonical project state:
    # L_A=2, L_B=5, N=4.
    configure_pair(2, 5)
    set_runtime_iterations(4)

    run([
        sys.executable,
        "frontend/elaborate_v0_6_dynamic.py",
    ])

    print(f"\nSaved results to {RESULTS}")
    print(
        "Restored canonical configuration: "
        "(L_A,L_B,N)=(2,5,4)"
    )


if __name__ == "__main__":
    main()
