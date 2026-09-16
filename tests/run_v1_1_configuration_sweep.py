#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from lair.calyx_backend import write_v1_pair_calyx
from lair.compiler import compile_lair_file
from lair.generator_elaboration import (
    ToyGeneratorConfig,
    elaborate_toy_generators,
    timing_environment_from_elaboration,
)
from lair.parser import parse_lair_file
from lair.resolver import (
    ConstraintViolation,
    resolve_program,
)


SOURCE = ROOT / "examples/v1_0_pair.lair"
DATA = ROOT / "examples/v0_6_data.json"

LATENCY_CHECKER = (
    ROOT / "tests/check_v1_1_pair_rtl_latency.py"
)

CSV_OUT = (
    ROOT / "results/v1_1_configuration_sweep.csv"
)

JSON_OUT = (
    ROOT / "results/v1_1_configuration_summary.json"
)

FINDINGS_OUT = (
    ROOT / "results/v1_1_findings.md"
)

CANON_RTL = (
    ROOT / "examples/generated/v1_1_kernels.sv"
)

CANON_CALYX = (
    ROOT / "examples/generated/v1_1_pair.futil"
)


CONFIGS = [
    {
        "id": "C1",
        "la": 2,
        "lb": 5,
        "expected_valid": True,
        "expected_cycles": 35,
    },
    {
        "id": "C2",
        "la": 5,
        "lb": 2,
        "expected_valid": True,
        "expected_cycles": 35,
    },
    {
        "id": "C3",
        "la": 3,
        "lb": 3,
        "expected_valid": True,
        "expected_cycles": 27,
    },
    {
        "id": "C4",
        "la": 4,
        "lb": 7,
        "expected_valid": False,
        "expected_cycles": None,
    },
    {
        "id": "C5",
        "la": 8,
        "lb": 3,
        "expected_valid": False,
        "expected_cycles": None,
    },
]


EXPECTED_MEMORY = [10, 4, 23, 0]


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
            "Command failed: "
            + " ".join(str(x) for x in cmd)
        )

    return result


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(65536),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def canonical_ir_hash(program) -> str:
    canonical = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode()
    ).hexdigest()


def simulate(path: Path):
    result = run(
        [
            "fud2",
            path,
            "-s",
            "sim.data=examples/v0_6_data.json",
            "--to",
            "dat",
            "--through",
            "verilator",
        ]
    )

    text = (
        result.stdout
        + "\n"
        + result.stderr
    )

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

    cycles = int(
        cycle_match.group(1)
    )

    memory = [
        int(mem_match.group(i))
        for i in range(1, 5)
    ]

    return cycles, memory


def validate_rtl(
    rtl: Path,
    la: int,
    lb: int,
    report: Path,
):
    run(
        [
            sys.executable,
            LATENCY_CHECKER,
            "--rtl",
            rtl,
            "--expected-a",
            la,
            "--expected-b",
            lb,
            "--output",
            report,
        ]
    )

    return json.loads(
        report.read_text()
    )


def constraint_text(exc: ConstraintViolation) -> str:
    pieces = []

    for failure in exc.failures:
        pieces.append(
            f"{failure.name}: "
            f"{failure.left_value} "
            f"{failure.op} "
            f"{failure.right_value}"
        )

    return "; ".join(pieces)


def run_sweep():
    rows = []

    source_sha_initial = sha256(
        SOURCE
    )

    baseline_program = parse_lair_file(
        SOURCE
    )

    baseline_ir_hash = canonical_ir_hash(
        baseline_program
    )

    print(
        "Source SHA256:",
        source_sha_initial,
    )

    print(
        "Symbolic IR SHA256:",
        baseline_ir_hash,
    )

    for cfg in CONFIGS:
        cid = cfg["id"]
        la = cfg["la"]
        lb = cfg["lb"]

        print()
        print("=" * 72)
        print(
            f"{cid}: "
            f"L_A={la}, "
            f"L_B={lb}, "
            f"expected_valid={cfg['expected_valid']}"
        )
        print("=" * 72)

        with tempfile.TemporaryDirectory(
            prefix=f"v1_1_{cid}_"
        ) as td:
            td = Path(td)

            rtl = td / "kernels.sv"
            calyx = td / "pair.futil"
            latency_report_path = (
                td / "latency.json"
            )

            program = parse_lair_file(
                SOURCE
            )

            ir_before = canonical_ir_hash(
                program
            )

            source_sha_before = sha256(
                SOURCE
            )

            # Generator elaboration:
            # symbolic GeneratorDecls -> physical RTL
            # + logical GeneratorResult timing facts.
            elaboration = elaborate_toy_generators(
                program,
                ToyGeneratorConfig(
                    {
                        "A": la,
                        "B": lb,
                    }
                ),
                rtl,
            )

            environment = (
                timing_environment_from_elaboration(
                    elaboration
                )
            )

            generator_a = (
                elaboration
                .by_instance()["A"]
            )

            generator_b = (
                elaboration
                .by_instance()["B"]
            )

            rtl_hash = generator_a.rtl.sha256

            if (
                generator_b.rtl.sha256
                != rtl_hash
            ):
                raise RuntimeError(
                    f"{cid}: shared RTL hashes disagree"
                )

            # Independent physical go->done timing
            # measurement from generated RTL.
            latency_report = validate_rtl(
                rtl,
                la,
                lb,
                latency_report_path,
            )

            measured_a = (
                latency_report[
                    "measured_go_to_done_cycles"
                ]["kernel_a"]
            )

            measured_b = (
                latency_report[
                    "measured_go_to_done_cycles"
                ]["kernel_b"]
            )

            rtl_latency_validated = (
                measured_a == la
                and measured_b == lb
                and latency_report[
                    "timing_correct"
                ]
                and latency_report[
                    "functional_correct"
                ]
            )

            if not rtl_latency_validated:
                raise RuntimeError(
                    f"{cid}: physical RTL timing validation failed"
                )

            if (
                latency_report["rtl_sha256"]
                != rtl_hash
            ):
                raise RuntimeError(
                    f"{cid}: RTL SHA mismatch between "
                    "generator result and physical checker"
                )

            accepted = False
            resolved_t = max(
                la,
                lb,
            )

            constraint_failure = ""

            calyx_cycles = None
            calyx_memory = None
            calyx_correct = None
            expected_cycles_match = None

            calyx.unlink(
                missing_ok=True
            )

            try:
                resolved = resolve_program(
                    program,
                    environment,
                )

                accepted = True

                resolved_t = (
                    resolved
                    .timing_values["T"]
                )

                if not cfg["expected_valid"]:
                    raise RuntimeError(
                        f"{cid}: resolver accepted "
                        "an expected-invalid configuration"
                    )

                relative_rtl = Path(
                    os.path.relpath(
                        rtl,
                        start=calyx.parent,
                    )
                ).as_posix()

                write_v1_pair_calyx(
                    resolved,
                    calyx,
                    extern_rtl=relative_rtl,
                )

                calyx_cycles, calyx_memory = (
                    simulate(
                        calyx
                    )
                )

                calyx_correct = (
                    calyx_memory
                    == EXPECTED_MEMORY
                )

                expected_cycles_match = (
                    calyx_cycles
                    == cfg["expected_cycles"]
                )

                if not calyx_correct:
                    raise RuntimeError(
                        f"{cid}: incorrect hardware output "
                        f"{calyx_memory}"
                    )

                if not expected_cycles_match:
                    raise RuntimeError(
                        f"{cid}: expected "
                        f"{cfg['expected_cycles']} cycles, "
                        f"measured {calyx_cycles}"
                    )

            except ConstraintViolation as exc:
                accepted = False

                constraint_failure = (
                    constraint_text(exc)
                )

                if cfg["expected_valid"]:
                    raise RuntimeError(
                        f"{cid}: resolver rejected "
                        "an expected-valid configuration"
                    ) from exc

                if calyx.exists():
                    raise RuntimeError(
                        f"{cid}: rejected configuration "
                        "emitted Calyx hardware"
                    )

            ir_after = canonical_ir_hash(
                program
            )

            source_sha_after = sha256(
                SOURCE
            )

            row = {
                "config": cid,
                "L_A": la,
                "L_B": lb,
                "T": resolved_t,
                "expected_valid": cfg[
                    "expected_valid"
                ],
                "source_sha256": (
                    source_sha_before
                ),
                "source_unchanged": (
                    source_sha_before
                    == source_sha_after
                    == source_sha_initial
                ),
                "symbolic_ir_sha256": (
                    ir_before
                ),
                "ir_unchanged": (
                    ir_before
                    == ir_after
                    == baseline_ir_hash
                ),
                "generator_reported_L_A": (
                    generator_a.latency
                ),
                "generator_reported_L_B": (
                    generator_b.latency
                ),
                "measured_L_A": measured_a,
                "measured_L_B": measured_b,
                "rtl_latency_validated": (
                    rtl_latency_validated
                ),
                "rtl_sha256": rtl_hash,
                "compiler_accepted": accepted,
                "calyx_emitted": (
                    calyx.exists()
                ),
                "calyx_cycles": (
                    ""
                    if calyx_cycles is None
                    else calyx_cycles
                ),
                "calyx_correct": (
                    ""
                    if calyx_correct is None
                    else calyx_correct
                ),
                "expected_cycles": (
                    ""
                    if cfg["expected_cycles"] is None
                    else cfg["expected_cycles"]
                ),
                "expected_cycles_match": (
                    ""
                    if expected_cycles_match is None
                    else expected_cycles_match
                ),
                "output_memory": (
                    ""
                    if calyx_memory is None
                    else json.dumps(
                        calyx_memory
                    )
                ),
                "constraint_failure": (
                    constraint_failure
                ),
            }

            rows.append(
                row
            )

            print(
                f"RTL measured: "
                f"A={measured_a}, "
                f"B={measured_b}"
            )

            print(
                "RTL SHA256:",
                rtl_hash,
            )

            print(
                "Timing environment:",
                environment.to_dict(),
            )

            print(
                f"Resolved T={resolved_t}"
            )

            print(
                f"Compiler accepted={accepted}"
            )

            print(
                f"Calyx emitted={calyx.exists()}"
            )

            if accepted:
                print(
                    f"Hardware cycles={calyx_cycles}"
                )
                print(
                    f"Hardware memory={calyx_memory}"
                )
            else:
                print(
                    "Constraint failure:",
                    constraint_failure,
                )

    return (
        rows,
        source_sha_initial,
        baseline_ir_hash,
    )


def restore_canonical():
    print()
    print("=" * 72)
    print("RESTORING CANONICAL C1 (2,5)")
    print("=" * 72)

    result = compile_lair_file(
        SOURCE,
        ToyGeneratorConfig(
            {
                "A": 2,
                "B": 5,
            }
        ),
        rtl_output=CANON_RTL,
        calyx_output=CANON_CALYX,
    )

    if not CANON_RTL.exists():
        raise RuntimeError(
            "Canonical RTL restoration failed."
        )

    if not CANON_CALYX.exists():
        raise RuntimeError(
            "Canonical Calyx restoration failed."
        )

    if (
        result.resolved.timing_values["T"]
        != 5
    ):
        raise RuntimeError(
            "Canonical restored timing is not T=5."
        )

    print(
        "Canonical RTL SHA256:",
        sha256(CANON_RTL),
    )

    print(
        "Canonical Calyx restored:",
        CANON_CALYX,
    )


def write_results(
    rows,
    source_hash,
    ir_hash,
):
    CSV_OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        rows[0].keys()
    )

    with CSV_OUT.open(
        "w",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    valid_rows = [
        row
        for row in rows
        if row["expected_valid"]
    ]

    invalid_rows = [
        row
        for row in rows
        if not row["expected_valid"]
    ]

    summary = {
        "experiment": (
            "V1.1 generator-elaboration "
            "configuration sweep"
        ),
        "source": str(
            SOURCE.relative_to(ROOT)
        ),
        "source_sha256": source_hash,
        "symbolic_ir_sha256": ir_hash,
        "configurations": len(rows),
        "valid_configurations": len(
            valid_rows
        ),
        "invalid_configurations": len(
            invalid_rows
        ),
        "one_source_hash": all(
            row["source_sha256"]
            == source_hash
            for row in rows
        ),
        "one_symbolic_ir_hash": all(
            row["symbolic_ir_sha256"]
            == ir_hash
            for row in rows
        ),
        "all_source_unchanged": all(
            row["source_unchanged"]
            for row in rows
        ),
        "all_symbolic_ir_unchanged": all(
            row["ir_unchanged"]
            for row in rows
        ),
        "all_generated_rtl_latencies_validated": all(
            row[
                "rtl_latency_validated"
            ]
            for row in rows
        ),
        "all_valid_accepted": all(
            row["compiler_accepted"]
            and row["calyx_emitted"]
            for row in valid_rows
        ),
        "all_invalid_rejected": all(
            not row["compiler_accepted"]
            and not row["calyx_emitted"]
            for row in invalid_rows
        ),
        "all_valid_hardware_correct": all(
            row["calyx_correct"]
            is True
            for row in valid_rows
        ),
        "all_valid_expected_cycles_match": all(
            row["expected_cycles_match"]
            is True
            for row in valid_rows
        ),
        "distinct_generated_rtl_artifacts": (
            len(
                {
                    row["rtl_sha256"]
                    for row in rows
                }
            )
            == len(rows)
        ),
        "canonical_restored": (
            CANON_RTL.exists()
            and CANON_CALYX.exists()
            and sha256(CANON_RTL)
            == rows[0]["rtl_sha256"]
        ),
        "rows": rows,
    }

    JSON_OUT.write_text(
        json.dumps(
            summary,
            indent=2,
        )
        + "\n"
    )

    findings = f"""# V1.1 configuration sweep findings

## Experiment

One unchanged latency-abstract source program:

`examples/v1_0_pair.lair`

was evaluated under five toy-generator configurations.

Source SHA256:

`{source_hash}`

Canonical symbolic-IR SHA256:

`{ir_hash}`

## Results

| Config | L_A | L_B | T | Compiler | Physical timing | Cycles |
|---|---:|---:|---:|---|---|---:|
"""

    for row in rows:
        compiler = (
            "accepted"
            if row["compiler_accepted"]
            else "rejected"
        )

        physical = (
            f"{row['measured_L_A']}, "
            f"{row['measured_L_B']}"
        )

        cycles = (
            row["calyx_cycles"]
            if row["calyx_cycles"] != ""
            else "—"
        )

        findings += (
            f"| {row['config']} "
            f"| {row['L_A']} "
            f"| {row['L_B']} "
            f"| {row['T']} "
            f"| {compiler} "
            f"| {physical} "
            f"| {cycles} |\n"
        )

    findings += """
## Observations

- The LAIR source and canonical symbolic IR remained unchanged across all five generator configurations.
- Generator-produced timing facts were converted automatically into the compiler `TimingEnvironment`.
- Independent Verilator measurements confirmed the advertised physical go-to-done latency of both generated kernels for every configuration.
- C1, C2, and C3 were accepted and produced the expected hardware behavior.
- C4 and C5 generated physically valid RTL but were rejected by the symbolic `parallel_deadline` constraint before Calyx hardware emission.
- Different configurations produced different physical RTL while preserving the same latency-abstract source and symbolic IR.
- The canonical C1 `(2,5)` generated state was restored after the sweep.

## Scope and caveats

This is a toy-generator mechanism and modularity experiment. The `T <= 6` deadline is synthetic, and the observed cycle counts do not establish a general performance advantage. The experiment demonstrates automatic generator-timing propagation, timing-aware resolution, and compile-time rejection behavior; it does not by itself establish novelty or generality beyond this prototype.
"""

    FINDINGS_OUT.write_text(
        findings
    )

    print()
    print("===== SWEEP SUMMARY =====")

    for key in (
        "one_source_hash",
        "one_symbolic_ir_hash",
        "all_source_unchanged",
        "all_symbolic_ir_unchanged",
        "all_generated_rtl_latencies_validated",
        "all_valid_accepted",
        "all_invalid_rejected",
        "all_valid_hardware_correct",
        "all_valid_expected_cycles_match",
        "distinct_generated_rtl_artifacts",
        "canonical_restored",
    ):
        print(
            f"{key} = {summary[key]}"
        )

    print()
    print(
        "Saved:",
        CSV_OUT.relative_to(ROOT),
    )

    print(
        "Saved:",
        JSON_OUT.relative_to(ROOT),
    )

    print(
        "Saved:",
        FINDINGS_OUT.relative_to(ROOT),
    )

    required = [
        summary[
            "one_source_hash"
        ],
        summary[
            "one_symbolic_ir_hash"
        ],
        summary[
            "all_source_unchanged"
        ],
        summary[
            "all_symbolic_ir_unchanged"
        ],
        summary[
            "all_generated_rtl_latencies_validated"
        ],
        summary[
            "all_valid_accepted"
        ],
        summary[
            "all_invalid_rejected"
        ],
        summary[
            "all_valid_hardware_correct"
        ],
        summary[
            "all_valid_expected_cycles_match"
        ],
        summary[
            "canonical_restored"
        ],
    ]

    if not all(required):
        raise RuntimeError(
            "One or more V1.1 sweep checks failed."
        )


def main():
    rows = None
    source_hash = None
    ir_hash = None

    try:
        (
            rows,
            source_hash,
            ir_hash,
        ) = run_sweep()

    finally:
        # Always restore the checked-in canonical
        # successful configuration, even if a sweep
        # configuration fails unexpectedly.
        restore_canonical()

    write_results(
        rows,
        source_hash,
        ir_hash,
    )


if __name__ == "__main__":
    main()
