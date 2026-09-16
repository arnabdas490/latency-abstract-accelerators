#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from lair.calyx_backend import (
    write_resolved_program_calyx,
)
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


SOURCE = (
    ROOT
    / "examples/v1_2_hierarchical.lair"
)

LATENCY_CHECKER = (
    ROOT
    / "tests/check_v1_1_pair_rtl_latency.py"
)

CSV_OUT = (
    ROOT
    / "results/v1_2_configuration_sweep.csv"
)

JSON_OUT = (
    ROOT
    / "results/v1_2_configuration_summary.json"
)

FINDINGS_OUT = (
    ROOT
    / "results/v1_2_findings.md"
)


CONFIGS = [
    {
        "id": "C1",
        "la": 2,
        "lb": 5,
        "expected_pair": 5,
        "expected_total": 7,
        "expected_valid": True,
        "expected_cycles": 43,
    },
    {
        "id": "C2",
        "la": 5,
        "lb": 2,
        "expected_pair": 5,
        "expected_total": 10,
        "expected_valid": False,
        "expected_cycles": None,
    },
    {
        "id": "C3",
        "la": 3,
        "lb": 3,
        "expected_pair": 3,
        "expected_total": 6,
        "expected_valid": True,
        "expected_cycles": 39,
    },
    {
        "id": "C4",
        "la": 4,
        "lb": 7,
        "expected_pair": 7,
        "expected_total": 11,
        "expected_valid": False,
        "expected_cycles": None,
    },
    {
        "id": "C5",
        "la": 8,
        "lb": 3,
        "expected_pair": 8,
        "expected_total": 16,
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
        print(
            result.stderr,
            file=sys.stderr,
        )
        raise RuntimeError(
            "Command failed: "
            + " ".join(
                str(x)
                for x in cmd
            )
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

    if (
        cycle_match is None
        or mem_match is None
    ):
        print(text)

        raise RuntimeError(
            "Could not parse simulation result "
            f"for {path}"
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


def constraint_text(
    exc: ConstraintViolation,
) -> str:
    return "; ".join(
        (
            f"{failure.name}: "
            f"{failure.left_value} "
            f"{failure.op} "
            f"{failure.right_value}"
        )
        for failure in exc.failures
    )


def inspect_structural_timing(
    program,
    environment,
):
    """
    Resolve the exact same generators/control tree with constraints
    removed only so rejected configurations can report compiler-derived
    structural timing values.

    This does not decide acceptance. The original constrained program
    is always used for the actual accept/reject result.
    """

    diagnostic_program = replace(
        program,
        constraints=(),
    )

    diagnostic = resolve_program(
        diagnostic_program,
        environment,
    )

    return (
        diagnostic.timing_values[
            "T_pair"
        ],
        diagnostic.timing_values[
            "T_total"
        ],
    )


def write_findings(
    source_sha: str,
    ir_sha: str,
    rows: list[dict],
    summary: dict,
) -> None:
    lines = [
        "# V1.2 hierarchical timing sweep findings",
        "",
        "## Experiment",
        "",
        "One unchanged latency-abstract source program:",
        "",
        "`examples/v1_2_hierarchical.lair`",
        "",
        "was evaluated under five toy-generator configurations.",
        "",
        "The source contains no explicit `let` timing bindings. "
        "`T_pair` and `T_total` are named by control regions and "
        "their values are inferred from static-control composition.",
        "",
        "Source SHA256:",
        "",
        f"`{source_sha}`",
        "",
        "Canonical symbolic-IR SHA256:",
        "",
        f"`{ir_sha}`",
        "",
        "## Results",
        "",
        (
            "| Config | L_A | L_B | T_pair | T_total | "
            "Compiler | Physical timing | Cycles |"
        ),
        (
            "|---|---:|---:|---:|---:|---|---|---:|"
        ),
    ]

    for row in rows:
        compiler = (
            "accepted"
            if row["compiler_accepted"]
            else "rejected"
        )

        cycles = (
            str(row["calyx_cycles"])
            if row["calyx_cycles"] != ""
            else "—"
        )

        lines.append(
            "| "
            f"{row['config']} | "
            f"{row['L_A']} | "
            f"{row['L_B']} | "
            f"{row['T_pair']} | "
            f"{row['T_total']} | "
            f"{compiler} | "
            f"{row['measured_L_A']}, "
            f"{row['measured_L_B']} | "
            f"{cycles} |"
        )

    lines.extend(
        [
            "",
            "## Structural reversal check",
            "",
            (
                "C1 `(L_A,L_B)=(2,5)` and C2 `(5,2)` contain "
                "the same latency multiset `{2,5}` and both infer "
                "`T_pair = 5`."
            ),
            "",
            (
                "Because `A` is invoked again after the parallel "
                "region, the enclosing structural timing differs: "
                "C1 infers `T_total = 7`, while C2 infers "
                "`T_total = 10`."
            ),
            "",
            (
                "Under the unchanged `T_total <= 8` source "
                "constraint, C1 is accepted and C2 is rejected."
            ),
            "",
            "## Mechanically checked properties",
            "",
        ]
    )

    checks = [
        (
            "One source hash across all configurations",
            summary["one_source_hash"],
        ),
        (
            "One symbolic IR hash across all configurations",
            summary["one_symbolic_ir_hash"],
        ),
        (
            "Zero explicit timing bindings in the V1.2 source",
            summary["zero_manual_timing_bindings"],
        ),
        (
            "Source remained unchanged",
            summary["all_source_unchanged"],
        ),
        (
            "Symbolic IR remained unchanged",
            summary["all_symbolic_ir_unchanged"],
        ),
        (
            "All generated RTL latencies were physically validated",
            summary[
                "all_generated_rtl_latencies_validated"
            ],
        ),
        (
            "All structural timings matched expected values",
            summary[
                "all_expected_structural_timings_match"
            ],
        ),
        (
            "All expected-valid configurations were accepted",
            summary["all_valid_accepted"],
        ),
        (
            "All expected-invalid configurations were rejected",
            summary["all_invalid_rejected"],
        ),
        (
            "All rejected configurations emitted no Calyx",
            summary["all_rejected_emit_no_calyx"],
        ),
        (
            "All rejected configurations failed total_deadline",
            summary["all_invalid_fail_total_deadline"],
        ),
        (
            "All generator configurations produced distinct RTL artifacts",
            summary["distinct_generated_rtl_artifacts"],
        ),
        (
            "All accepted hardware produced correct output",
            summary["all_valid_hardware_correct"],
        ),
        (
            "All accepted cycle counts matched measured targets",
            summary[
                "all_valid_expected_cycles_match"
            ],
        ),
        (
            "C1/C2 structural reversal property holds",
            summary[
                "c1_c2_structural_reversal_property"
            ],
        ),
    ]

    for label, passed in checks:
        mark = "PASS" if passed else "FAIL"
        lines.append(
            f"- **{mark}** — {label}"
        )

    lines.extend(
        [
            "",
            "## Scope and caveats",
            "",
            (
                "This remains a toy-generator experiment with a "
                "synthetic `T_total <= 8` deadline and an A/B-specific "
                "external primitive shell. The result does not establish "
                "novelty or a general performance advantage."
            ),
            "",
            (
                "V1.2 strengthens the abstraction experiment by moving "
                "parallel/sequential timing composition into first-class "
                "IR semantics: the source names region timing results, "
                "while the compiler derives their concrete values from "
                "generator timing and control structure."
            ),
            "",
            (
                "The C1/C2 contrast demonstrates a case where the same "
                "leaf-latency multiset and same inner-parallel latency "
                "produce different higher-level timing and compilation "
                "outcomes because of structural composition."
            ),
            "",
            (
                "This is evidence against the narrow "
                "`parse latency -> print static<L>` implementation, "
                "but it does not by itself prove that a general-purpose "
                "compiler IR is superior to every possible custom script."
            ),
            "",
        ]
    )

    FINDINGS_OUT.write_text(
        "\n".join(lines)
    )


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

    baseline_binding_count = len(
        baseline_program.bindings
    )

    print(
        "Source SHA256:",
        source_sha_initial,
    )

    print(
        "Symbolic IR SHA256:",
        baseline_ir_hash,
    )

    print(
        "Explicit timing bindings:",
        baseline_binding_count,
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
            f"expected_pair={cfg['expected_pair']}, "
            f"expected_total={cfg['expected_total']}, "
            f"expected_valid={cfg['expected_valid']}"
        )
        print("=" * 72)

        with tempfile.TemporaryDirectory(
            prefix=f"v1_2_{cid}_"
        ) as td:
            td = Path(td)

            rtl = td / "kernels.sv"
            calyx = td / "program.futil"

            latency_report_path = (
                td / "latency.json"
            )

            program = parse_lair_file(
                SOURCE
            )

            source_sha_before = sha256(
                SOURCE
            )

            ir_before = canonical_ir_hash(
                program
            )

            binding_count = len(
                program.bindings
            )

            elaboration = (
                elaborate_toy_generators(
                    program,
                    ToyGeneratorConfig(
                        {
                            "A": la,
                            "B": lb,
                        }
                    ),
                    rtl,
                )
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

            rtl_hash = (
                generator_a.rtl.sha256
            )

            if (
                generator_b.rtl.sha256
                != rtl_hash
            ):
                raise RuntimeError(
                    f"{cid}: shared RTL hashes disagree"
                )

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
                    f"{cid}: physical RTL validation failed"
                )

            if (
                latency_report["rtl_sha256"]
                != rtl_hash
            ):
                raise RuntimeError(
                    f"{cid}: generator/checker RTL "
                    "SHA mismatch"
                )

            # Independently inspect compiler-derived structural
            # timings even when the actual constrained compilation
            # will reject the configuration.
            (
                resolved_pair,
                resolved_total,
            ) = inspect_structural_timing(
                program,
                environment,
            )

            structural_timings_match = (
                resolved_pair
                == cfg["expected_pair"]
                and resolved_total
                == cfg["expected_total"]
            )

            if not structural_timings_match:
                raise RuntimeError(
                    f"{cid}: structural timing mismatch: "
                    f"pair={resolved_pair}, "
                    f"total={resolved_total}"
                )

            accepted = False
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

                if not cfg["expected_valid"]:
                    raise RuntimeError(
                        f"{cid}: resolver accepted an "
                        "expected-invalid configuration"
                    )

                if (
                    resolved.timing_values[
                        "T_pair"
                    ]
                    != resolved_pair
                ):
                    raise RuntimeError(
                        f"{cid}: constrained/diagnostic "
                        "T_pair disagree"
                    )

                if (
                    resolved.timing_values[
                        "T_total"
                    ]
                    != resolved_total
                ):
                    raise RuntimeError(
                        f"{cid}: constrained/diagnostic "
                        "T_total disagree"
                    )

                write_resolved_program_calyx(
                    resolved,
                    calyx,
                    extern_rtl=rtl.name,
                )

                (
                    calyx_cycles,
                    calyx_memory,
                ) = simulate(
                    calyx
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
                    constraint_text(
                        exc
                    )
                )

                if cfg["expected_valid"]:
                    raise RuntimeError(
                        f"{cid}: resolver rejected an "
                        "expected-valid configuration"
                    ) from exc

                if calyx.exists():
                    raise RuntimeError(
                        f"{cid}: rejected configuration "
                        "emitted Calyx hardware"
                    )

            source_sha_after = sha256(
                SOURCE
            )

            ir_after = canonical_ir_hash(
                program
            )

            row = {
                "config": cid,
                "L_A": la,
                "L_B": lb,
                "T_pair": resolved_pair,
                "T_total": resolved_total,
                "expected_T_pair": (
                    cfg["expected_pair"]
                ),
                "expected_T_total": (
                    cfg["expected_total"]
                ),
                "expected_valid": (
                    cfg["expected_valid"]
                ),
                "manual_timing_bindings": (
                    binding_count
                ),
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
                "structural_timings_match": (
                    structural_timings_match
                ),
                "compiler_accepted": (
                    accepted
                ),
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
                    if cfg["expected_cycles"]
                    is None
                    else cfg["expected_cycles"]
                ),
                "expected_cycles_match": (
                    ""
                    if expected_cycles_match
                    is None
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
                f"{cid}: "
                f"T_pair={resolved_pair}, "
                f"T_total={resolved_total}, "
                f"accepted={accepted}, "
                f"RTL=({measured_a},{measured_b}), "
                f"cycles={calyx_cycles}"
            )

    fieldnames = list(
        rows[0].keys()
    )

    CSV_OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
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
        writer.writerows(
            rows
        )

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

    row_by_id = {
        row["config"]: row
        for row in rows
    }

    c1 = row_by_id["C1"]
    c2 = row_by_id["C2"]

    c1_c2_structural_reversal_property = (
        sorted(
            [
                c1["L_A"],
                c1["L_B"],
            ]
        )
        == sorted(
            [
                c2["L_A"],
                c2["L_B"],
            ]
        )
        and c1["T_pair"]
        == c2["T_pair"]
        == 5
        and c1["T_total"] == 7
        and c2["T_total"] == 10
        and c1["compiler_accepted"]
        and not c2["compiler_accepted"]
    )

    summary = {
        "experiment": (
            "V1.2 hierarchical structural timing "
            "configuration sweep"
        ),
        "source": (
            "examples/v1_2_hierarchical.lair"
        ),
        "source_sha256": (
            source_sha_initial
        ),
        "symbolic_ir_sha256": (
            baseline_ir_hash
        ),
        "configurations": len(
            rows
        ),
        "valid_configurations": len(
            valid_rows
        ),
        "invalid_configurations": len(
            invalid_rows
        ),
        "one_source_hash": (
            len(
                {
                    row["source_sha256"]
                    for row in rows
                }
            )
            == 1
        ),
        "one_symbolic_ir_hash": (
            len(
                {
                    row[
                        "symbolic_ir_sha256"
                    ]
                    for row in rows
                }
            )
            == 1
        ),
        "zero_manual_timing_bindings": (
            baseline_binding_count == 0
            and all(
                row[
                    "manual_timing_bindings"
                ]
                == 0
                for row in rows
            )
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
        "all_expected_structural_timings_match": all(
            row[
                "structural_timings_match"
            ]
            for row in rows
        ),
        "all_valid_accepted": all(
            row["compiler_accepted"]
            and row["calyx_emitted"]
            for row in valid_rows
        ),
        "all_invalid_rejected": all(
            not row[
                "compiler_accepted"
            ]
            for row in invalid_rows
        ),
        "all_rejected_emit_no_calyx": all(
            not row["calyx_emitted"]
            for row in invalid_rows
        ),
        "all_invalid_fail_total_deadline": all(
            "total_deadline"
            in row["constraint_failure"]
            for row in invalid_rows
        ),
        "all_valid_hardware_correct": all(
            row["calyx_correct"]
            is True
            for row in valid_rows
        ),
        "all_valid_expected_cycles_match": all(
            row[
                "expected_cycles_match"
            ]
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
        "c1_c2_structural_reversal_property": (
            c1_c2_structural_reversal_property
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

    write_findings(
        source_sha_initial,
        baseline_ir_hash,
        rows,
        summary,
    )

    required_checks = {
        key: value
        for key, value in summary.items()
        if key
        not in {
            "experiment",
            "source",
            "source_sha256",
            "symbolic_ir_sha256",
            "configurations",
            "valid_configurations",
            "invalid_configurations",
            "rows",
        }
    }

    print()
    print(
        "===== V1.2 SUMMARY CHECKS ====="
    )

    for name, passed in (
        required_checks.items()
    ):
        print(
            f"{name}: {passed}"
        )

        if passed is not True:
            raise RuntimeError(
                f"V1.2 summary check failed: "
                f"{name}"
            )

    print()
    print(
        "Wrote:",
        CSV_OUT.relative_to(
            ROOT
        ),
    )
    print(
        "Wrote:",
        JSON_OUT.relative_to(
            ROOT
        ),
    )
    print(
        "Wrote:",
        FINDINGS_OUT.relative_to(
            ROOT
        ),
    )


if __name__ == "__main__":
    run_sweep()
