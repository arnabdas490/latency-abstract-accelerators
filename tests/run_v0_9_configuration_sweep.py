#!/usr/bin/env python3

import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

A_CONTRACT = ROOT / "contracts/kernel_a.json"
B_CONTRACT = ROOT / "contracts/kernel_b.json"
DATA = ROOT / "examples/v0_6_data.json"

LI_FRONTEND = ROOT / "frontend/elaborate_v0_8_fixed_li.py"
LA_FRONTEND = ROOT / "frontend/elaborate_v0_8_fixed_la.py"
LATENCY_CHECKER = ROOT / "tests/check_v0_8_rtl_latency.py"

RTL = ROOT / "baselines/v0_8_fixed_li_kernels.sv"
LI_FUTIL = ROOT / "baselines/v0_8_fixed_li.futil"
LA_FUTIL = ROOT / "examples/generated/v0_8_fixed_la.futil"

CSV_OUT = ROOT / "results/v0_9_configuration_sweep.csv"
JSON_OUT = ROOT / "results/v0_9_configuration_summary.json"

CONFIGS = [
    {
        "id": "C1",
        "la": 2,
        "lb": 5,
        "expected_valid": True,
        "manual": ROOT / "baselines/v0_8_fixed_manual_static.futil",
    },
    {
        "id": "C2",
        "la": 5,
        "lb": 2,
        "expected_valid": True,
        "manual": ROOT / "baselines/v0_9_manual_static_5_2.futil",
    },
    {
        "id": "C3",
        "la": 3,
        "lb": 3,
        "expected_valid": True,
        "manual": ROOT / "baselines/v0_9_manual_static_3_3.futil",
    },
    {
        "id": "C4",
        "la": 4,
        "lb": 7,
        "expected_valid": False,
        "manual": None,
    },
    {
        "id": "C5",
        "la": 8,
        "lb": 3,
        "expected_valid": False,
        "manual": None,
    },
]


def run(cmd, check=True):
    result = subprocess.run(
        [str(x) for x in cmd],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(
            "Command failed: " + " ".join(str(x) for x in cmd)
        )

    return result


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)

    return h.hexdigest()


def write_contract(path, latency):
    obj = json.loads(path.read_text())
    obj["latency"] = latency
    path.write_text(json.dumps(obj, indent=2) + "\n")


def set_canonical_data():
    payload = {
        "mem": {
            "data": [10, 4, 0, 0],
            "format": {
                "numeric_type": "bitnum",
                "is_signed": False,
                "width": 32,
            },
        }
    }

    DATA.write_text(json.dumps(payload, indent=2) + "\n")


def simulate(path):
    result = run(
        [
            "fud2",
            path.relative_to(ROOT),
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
            f"Could not parse simulation result for {path}"
        )

    cycles = int(cycle_match.group(1))
    memory = [
        int(mem_match.group(i))
        for i in range(1, 5)
    ]

    return cycles, memory


def validate_rtl_latency(config_id):
    with tempfile.TemporaryDirectory(
        prefix=f"v0_9_{config_id}_"
    ) as td:
        report = Path(td) / "latency.json"

        run(
            [
                sys.executable,
                LATENCY_CHECKER.relative_to(ROOT),
                "--output",
                report,
            ]
        )

        return json.loads(report.read_text())


def manual_intervals(path):
    text = path.read_text()

    return [
        int(x)
        for x in re.findall(
            r"@interval\((\d+)\)",
            text,
        )
    ]


def main():
    original_a = A_CONTRACT.read_text()
    original_b = B_CONTRACT.read_text()
    original_data = DATA.read_text()

    la_source_hash_before = sha256(LA_FRONTEND)

    rows = []

    try:
        set_canonical_data()

        print(
            "LA frontend SHA256 before sweep:",
            la_source_hash_before,
        )

        for cfg in CONFIGS:
            cid = cfg["id"]
            la = cfg["la"]
            lb = cfg["lb"]
            target = max(la, lb)

            print()
            print("=" * 68)
            print(
                f"{cid}: L_A={la}, L_B={lb}, "
                f"T={target}, "
                f"expected_valid={cfg['expected_valid']}"
            )
            print("=" * 68)

            write_contract(A_CONTRACT, la)
            write_contract(B_CONTRACT, lb)

            # Generate physical RTL for this configuration.
            run(
                [
                    sys.executable,
                    LI_FRONTEND.relative_to(ROOT),
                ]
            )

            rtl_hash_before = sha256(RTL)

            # Independently measure physical go->done latency.
            latency_report = validate_rtl_latency(cid)

            measured_a = latency_report[
                "measured_go_to_done_cycles"
            ]["kernel_a"]
            measured_b = latency_report[
                "measured_go_to_done_cycles"
            ]["kernel_b"]

            timing_validated = (
                measured_a == la
                and measured_b == lb
                and latency_report["timing_correct"]
                and latency_report["functional_correct"]
            )

            print(
                f"RTL measured: A={measured_a}, B={measured_b}"
            )
            print(f"RTL SHA256: {rtl_hash_before}")

            if not timing_validated:
                raise RuntimeError(
                    f"{cid}: generated RTL failed latency validation"
                )

            # Opaque LI can execute regardless of synthetic LA deadline.
            li_cycles, li_memory = simulate(LI_FUTIL)
            li_correct = li_memory == [10, 4, 23, 0]

            print(
                f"opaque LI: cycles={li_cycles}, "
                f"correct={li_correct}"
            )

            # Ask the LA resolver/elaborator whether this timing is legal.
            la_result = run(
                [
                    sys.executable,
                    LA_FRONTEND.relative_to(ROOT),
                ],
                check=False,
            )

            la_accepted = la_result.returncode == 0
            hardware_emitted = LA_FUTIL.exists()

            print(
                f"LA accepted={la_accepted}, "
                f"hardware_emitted={hardware_emitted}"
            )

            if la_accepted != cfg["expected_valid"]:
                print(la_result.stdout)
                print(la_result.stderr, file=sys.stderr)
                raise RuntimeError(
                    f"{cid}: LA acceptance did not match expectation"
                )

            # LA elaboration must never regenerate/change physical RTL.
            rtl_hash_after = sha256(RTL)

            if rtl_hash_before != rtl_hash_after:
                raise RuntimeError(
                    f"{cid}: LA elaboration modified shared RTL"
                )

            row = {
                "config": cid,
                "L_A": la,
                "L_B": lb,
                "T": target,
                "expected_valid": cfg["expected_valid"],
                "measured_L_A": measured_a,
                "measured_L_B": measured_b,
                "rtl_latency_validated": timing_validated,
                "rtl_sha256": rtl_hash_before,
                "opaque_li_cycles": li_cycles,
                "opaque_li_correct": li_correct,
                "la_accepted": la_accepted,
                "la_hardware_emitted": hardware_emitted,
                "manual_static_cycles": "",
                "manual_static_correct": "",
                "la_cycles": "",
                "la_correct": "",
                "manual_equals_la": "",
                "manual_timing_literals": "",
                "manual_source_file": "",
            }

            if cfg["expected_valid"]:
                manual = cfg["manual"]

                intervals = manual_intervals(manual)

                if intervals[:2] != [la, lb]:
                    raise RuntimeError(
                        f"{cid}: manual oracle timing facts "
                        f"{intervals[:2]} do not match "
                        f"[{la}, {lb}]"
                    )

                manual_cycles, manual_memory = simulate(manual)
                la_cycles, la_memory = simulate(LA_FUTIL)

                manual_correct = (
                    manual_memory == [10, 4, 23, 0]
                )
                la_correct = (
                    la_memory == [10, 4, 23, 0]
                )
                equal = manual_cycles == la_cycles

                print(
                    f"manual static: cycles={manual_cycles}, "
                    f"correct={manual_correct}"
                )
                print(
                    f"LA resolved:   cycles={la_cycles}, "
                    f"correct={la_correct}"
                )
                print(f"manual == LA: {equal}")

                row.update(
                    {
                        "manual_static_cycles": manual_cycles,
                        "manual_static_correct": manual_correct,
                        "la_cycles": la_cycles,
                        "la_correct": la_correct,
                        "manual_equals_la": equal,
                        "manual_timing_literals": len(
                            intervals[:2]
                        ),
                        "manual_source_file": str(
                            manual.relative_to(ROOT)
                        ),
                    }
                )

                if not (
                    li_correct
                    and manual_correct
                    and la_correct
                    and equal
                ):
                    raise RuntimeError(
                        f"{cid}: valid configuration failed "
                        "functional/performance equivalence check"
                    )

            else:
                if hardware_emitted:
                    raise RuntimeError(
                        f"{cid}: invalid configuration emitted LA hardware"
                    )

                print(
                    "Rejected before LA hardware execution "
                    "(as intended)."
                )

            rows.append(row)

        la_source_hash_after = sha256(LA_FRONTEND)

        if la_source_hash_after != la_source_hash_before:
            raise RuntimeError(
                "LA frontend source changed during sweep."
            )

        CSV_OUT.parent.mkdir(parents=True, exist_ok=True)

        with CSV_OUT.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(rows)

        valid_rows = [
            r for r in rows
            if r["expected_valid"]
        ]
        invalid_rows = [
            r for r in rows
            if not r["expected_valid"]
        ]

        summary = {
            "experiment": "V0.9 configuration/modularity sweep",
            "runtime_iterations": 4,
            "valid_configurations": 3,
            "invalid_configurations": 2,
            "la_frontend_sha256_before": la_source_hash_before,
            "la_frontend_sha256_after": la_source_hash_after,
            "la_source_unchanged": (
                la_source_hash_before == la_source_hash_after
            ),
            "manual_static_source_variants": 3,
            "la_source_variants": 1,
            "all_generated_rtl_latencies_validated": all(
                r["rtl_latency_validated"]
                for r in rows
            ),
            "all_valid_manual_equal_la": all(
                r["manual_equals_la"]
                for r in valid_rows
            ),
            "all_invalid_rejected": all(
                not r["la_accepted"]
                and not r["la_hardware_emitted"]
                for r in invalid_rows
            ),
            "rows": rows,
        }

        JSON_OUT.write_text(
            json.dumps(summary, indent=2) + "\n"
        )

        print()
        print("===== V0.9 SUMMARY =====")
        print(
            "LA source unchanged: ",
            summary["la_source_unchanged"],
        )
        print(
            "All physical RTL timings validated: ",
            summary[
                "all_generated_rtl_latencies_validated"
            ],
        )
        print(
            "All valid manual == LA: ",
            summary["all_valid_manual_equal_la"],
        )
        print(
            "All invalid configs rejected: ",
            summary["all_invalid_rejected"],
        )
        print(
            "Manual source variants: ",
            summary["manual_static_source_variants"],
        )
        print(
            "LA source variants: ",
            summary["la_source_variants"],
        )
        print(
            f"Saved {CSV_OUT.relative_to(ROOT)}"
        )
        print(
            f"Saved {JSON_OUT.relative_to(ROOT)}"
        )

    finally:
        # Restore the exact canonical source inputs.
        A_CONTRACT.write_text(original_a)
        B_CONTRACT.write_text(original_b)
        DATA.write_text(original_data)

        # Restore canonical generated artifacts for L_A=2, L_B=5.
        run(
            [
                sys.executable,
                LI_FRONTEND.relative_to(ROOT),
            ]
        )
        run(
            [
                sys.executable,
                LA_FRONTEND.relative_to(ROOT),
            ]
        )

        print()
        print(
            "Restored canonical configuration "
            "L_A=2, L_B=5, N=4."
        )


if __name__ == "__main__":
    main()
