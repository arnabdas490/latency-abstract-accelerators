from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from lair.compiler import compile_lair_file
from lair.generator_elaboration import (
    ToyGeneratorConfig,
    elaborate_toy_generators,
    timing_environment_from_elaboration,
)
from lair.parser import parse_lair_file
from lair.resolver import (
    ConstraintViolation,
    resolve_component_program,
)


SOURCE = ROOT / "examples/v1_3_components.lair"
DATA = ROOT / "examples/v0_6_data.json"
FROZEN = ROOT / "results/v1_3_canonical_hashes.json"

JSON_OUTPUT = (
    ROOT
    / "results/v1_3_configuration_sweep.json"
)

CSV_OUTPUT = (
    ROOT
    / "results/v1_3_configuration_sweep.csv"
)

MD_OUTPUT = (
    ROOT
    / "results/v1_3_configuration_sweep.md"
)

LATENCY_CHECKER = (
    ROOT
    / "tests/check_v1_1_pair_rtl_latency.py"
)

EXPECTED_MEMORY = [
    10,
    4,
    23,
    0,
]

CONFIGS = {
    "C1": {
        "A": 2,
        "B": 5,
        "pair": 5,
        "tail": 2,
        "total": 7,
        "accepted": True,
        "cycles": 43,
    },
    "C2": {
        "A": 5,
        "B": 2,
        "pair": 5,
        "tail": 5,
        "total": 10,
        "accepted": False,
        "cycles": None,
    },
    "C3": {
        "A": 3,
        "B": 3,
        "pair": 3,
        "tail": 3,
        "total": 6,
        "accepted": True,
        "cycles": 39,
    },
    "C4": {
        "A": 4,
        "B": 7,
        "pair": 7,
        "tail": 4,
        "total": 11,
        "accepted": False,
        "cycles": None,
    },
    "C5": {
        "A": 8,
        "B": 3,
        "pair": 8,
        "tail": 8,
        "total": 16,
        "accepted": False,
        "cycles": None,
    },
}


def sha256_file(path: Path) -> str:
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


def simulate(path: Path) -> tuple[int, list[int]]:
    result = subprocess.run(
        [
            "fud2",
            str(path),
            "-s",
            f"sim.data={DATA.relative_to(ROOT)}",
            "--to",
            "dat",
            "--through",
            "verilator",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
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
        raise RuntimeError(
            "Could not parse FUD2 result."
        )

    return (
        int(cycle_match.group(1)),
        [
            int(mem_match.group(i))
            for i in range(1, 5)
        ],
    )


def validate_rtl(
    rtl: Path,
    la: int,
    lb: int,
    report: Path,
) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(LATENCY_CHECKER),
            "--rtl",
            str(rtl),
            "--expected-a",
            str(la),
            "--expected-b",
            str(lb),
            "--output",
            str(report),
        ],
        cwd=ROOT,
        check=True,
    )

    return json.loads(
        report.read_text()
    )


def diagnostic_timing(
    program,
    config: ToyGeneratorConfig,
    rtl: Path,
) -> dict[str, int]:
    diagnostic = replace(
        program,
        constraints=(),
    )

    elaboration = elaborate_toy_generators(
        diagnostic,
        config,
        rtl,
    )

    environment = (
        timing_environment_from_elaboration(
            elaboration
        )
    )

    resolved = resolve_component_program(
        diagnostic,
        environment,
    )

    return resolved.timing_values


def write_csv(rows: list[dict]) -> None:
    fields = [
        "configuration",
        "L_A",
        "L_B",
        "T_pair",
        "T_tail",
        "T_total",
        "compiler_accepted",
        "measured_A",
        "measured_B",
        "rtl_timing_correct",
        "rtl_functional_correct",
        "calyx_emitted",
        "hardware_cycles",
        "expected_cycles",
        "cycle_match",
        "memory_correct",
    ]

    with CSV_OUTPUT.open(
        "w",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    key: row[key]
                    for key in fields
                }
            )


def write_markdown(
    source_sha: str,
    ir_sha: str,
    rows: list[dict],
    summary: dict,
) -> None:
    lines = [
        "# V1.3 component timing-interface sweep",
        "",
        "One unchanged latency-abstract source and symbolic IR "
        "were evaluated under five generator configurations.",
        "",
        f"- Source SHA256: `{source_sha}`",
        f"- Symbolic IR SHA256: `{ir_sha}`",
        "- Explicit timing bindings in source: `0`",
        "",
        "| Config | A | B | Pair | Tail | Total | Compiler | "
        "Measured RTL | Hardware cycles |",
        "|---|---:|---:|---:|---:|---:|---|---|---:|",
    ]

    for row in rows:
        decision = (
            "ACCEPT"
            if row["compiler_accepted"]
            else "REJECT"
        )

        rtl = (
            f"{row['measured_A']}/"
            f"{row['measured_B']}"
        )

        cycles = (
            str(row["hardware_cycles"])
            if row["hardware_cycles"] is not None
            else "—"
        )

        lines.append(
            f"| {row['configuration']} "
            f"| {row['L_A']} "
            f"| {row['L_B']} "
            f"| {row['T_pair']} "
            f"| {row['T_tail']} "
            f"| {row['T_total']} "
            f"| {decision} "
            f"| {rtl} "
            f"| {cycles} |"
        )

    lines.extend(
        [
            "",
            "## Validation summary",
            "",
            f"- Same source for C1-C5: "
            f"`{summary['same_source']}`",
            f"- Same symbolic IR for C1-C5: "
            f"`{summary['same_symbolic_ir']}`",
            f"- Matches frozen manifest: "
            f"`{summary['matches_frozen_manifest']}`",
            f"- Expected compiler decisions: "
            f"`{summary['acceptance_matches']}`",
            f"- All physical generator latencies validated: "
            f"`{summary['all_rtl_timing_correct']}`",
            f"- All generated kernels functionally validated: "
            f"`{summary['all_rtl_functional_correct']}`",
            f"- Rejected configurations emitted no Calyx: "
            f"`{summary['rejected_emit_no_calyx']}`",
            f"- Accepted hardware returned correct memory: "
            f"`{summary['accepted_memory_correct']}`",
            f"- Accepted hardware cycle counts matched targets: "
            f"`{summary['accepted_cycles_match']}`",
            "",
            "## Interpretation",
            "",
            "The experiment demonstrates timing propagation across "
            "reusable component interfaces after generator timing becomes "
            "known. The latency-abstract source and symbolic IR are unchanged "
            "across configurations. This remains a toy-generator mechanism "
            "experiment and does not by itself establish generality, "
            "performance advantage, or novelty.",
            "",
        ]
    )

    MD_OUTPUT.write_text(
        "\n".join(lines)
    )


def main() -> None:
    frozen = json.loads(
        FROZEN.read_text()
    )

    source_sha = sha256_file(
        SOURCE
    )

    symbolic = parse_lair_file(
        SOURCE
    )

    ir_sha = canonical_ir_hash(
        symbolic
    )

    if (
        source_sha
        != frozen["source_sha256"]
    ):
        raise RuntimeError(
            "Canonical source hash differs "
            "from frozen manifest."
        )

    if (
        ir_sha
        != frozen["symbolic_ir_sha256"]
    ):
        raise RuntimeError(
            "Canonical IR hash differs "
            "from frozen manifest."
        )

    rows = []

    with tempfile.TemporaryDirectory(
        prefix="v1_3_sweep_"
    ) as td:
        td = Path(td)

        for cid, expected in CONFIGS.items():
            print()
            print(
                "===== "
                f"{cid}: A={expected['A']} "
                f"B={expected['B']} "
                "====="
            )

            rtl = td / f"{cid}_kernels.sv"
            calyx = td / f"{cid}.futil"
            report = td / f"{cid}_rtl.json"

            config = ToyGeneratorConfig(
                {
                    "A": expected["A"],
                    "B": expected["B"],
                }
            )

            compiler_accepted = True
            failures = []

            try:
                result = compile_lair_file(
                    SOURCE,
                    config,
                    rtl_output=rtl,
                    calyx_output=calyx,
                )

                timing = (
                    result.resolved
                    .timing_values
                )

            except ConstraintViolation as exc:
                compiler_accepted = False

                failures = [
                    {
                        "name": f.name,
                        "left_value": (
                            f.left_value
                        ),
                        "op": f.op,
                        "right_value": (
                            f.right_value
                        ),
                    }
                    for f in exc.failures
                ]

                timing = diagnostic_timing(
                    symbolic,
                    config,
                    rtl,
                )

            if (
                compiler_accepted
                != expected["accepted"]
            ):
                raise RuntimeError(
                    f"{cid}: acceptance mismatch."
                )

            expected_timing = {
                "T_pair": expected["pair"],
                "T_tail": expected["tail"],
                "T_total": expected["total"],
            }

            for name, value in (
                expected_timing.items()
            ):
                if timing[name] != value:
                    raise RuntimeError(
                        f"{cid}: {name} "
                        f"expected {value}, "
                        f"got {timing[name]}."
                    )

            calyx_emitted = calyx.exists()

            if (
                calyx_emitted
                != compiler_accepted
            ):
                raise RuntimeError(
                    f"{cid}: unexpected "
                    "Calyx emission state."
                )

            rtl_report = validate_rtl(
                rtl,
                expected["A"],
                expected["B"],
                report,
            )

            measured_a = (
                rtl_report[
                    "measured_go_to_done_cycles"
                ]["kernel_a"]
            )

            measured_b = (
                rtl_report[
                    "measured_go_to_done_cycles"
                ]["kernel_b"]
            )

            cycles = None
            memory = None
            cycle_match = None
            memory_correct = None

            if compiler_accepted:
                cycles, memory = simulate(
                    calyx
                )

                cycle_match = (
                    cycles
                    == expected["cycles"]
                )

                memory_correct = (
                    memory
                    == EXPECTED_MEMORY
                )

                if not cycle_match:
                    raise RuntimeError(
                        f"{cid}: expected "
                        f"{expected['cycles']} "
                        f"hardware cycles, "
                        f"got {cycles}."
                    )

                if not memory_correct:
                    raise RuntimeError(
                        f"{cid}: incorrect "
                        f"memory {memory}."
                    )

            row = {
                "configuration": cid,
                "L_A": expected["A"],
                "L_B": expected["B"],
                "T_pair": timing["T_pair"],
                "T_tail": timing["T_tail"],
                "T_total": timing["T_total"],
                "compiler_accepted": (
                    compiler_accepted
                ),
                "constraint_failures": (
                    failures
                ),
                "measured_A": measured_a,
                "measured_B": measured_b,
                "rtl_timing_correct": (
                    rtl_report[
                        "timing_correct"
                    ]
                ),
                "rtl_functional_correct": (
                    rtl_report[
                        "functional_correct"
                    ]
                ),
                "rtl_sha256": (
                    rtl_report[
                        "rtl_sha256"
                    ]
                ),
                "calyx_emitted": (
                    calyx_emitted
                ),
                "hardware_cycles": cycles,
                "expected_cycles": (
                    expected["cycles"]
                ),
                "cycle_match": cycle_match,
                "hardware_memory": memory,
                "memory_correct": (
                    memory_correct
                ),
                "source_sha256": source_sha,
                "symbolic_ir_sha256": ir_sha,
            }

            rows.append(row)

            print(
                f"{cid}: "
                f"pair={row['T_pair']} "
                f"tail={row['T_tail']} "
                f"total={row['T_total']} "
                + (
                    "ACCEPT"
                    if compiler_accepted
                    else "REJECT"
                )
            )

            print(
                "  RTL measured:",
                measured_a,
                measured_b,
            )

            if compiler_accepted:
                print(
                    "  hardware:",
                    cycles,
                    memory,
                )
            else:
                print(
                    "  constraint:",
                    failures,
                )

    summary = {
        "same_source": (
            len(
                {
                    row["source_sha256"]
                    for row in rows
                }
            )
            == 1
        ),
        "same_symbolic_ir": (
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
        "matches_frozen_manifest": (
            source_sha
            == frozen["source_sha256"]
            and ir_sha
            == frozen[
                "symbolic_ir_sha256"
            ]
        ),
        "acceptance_matches": all(
            row["compiler_accepted"]
            == CONFIGS[
                row["configuration"]
            ]["accepted"]
            for row in rows
        ),
        "all_rtl_timing_correct": all(
            row["rtl_timing_correct"]
            for row in rows
        ),
        "all_rtl_functional_correct": all(
            row["rtl_functional_correct"]
            for row in rows
        ),
        "rejected_emit_no_calyx": all(
            not row["calyx_emitted"]
            for row in rows
            if not row["compiler_accepted"]
        ),
        "accepted_memory_correct": all(
            row["memory_correct"]
            for row in rows
            if row["compiler_accepted"]
        ),
        "accepted_cycles_match": all(
            row["cycle_match"]
            for row in rows
            if row["compiler_accepted"]
        ),
    }

    if not all(
        summary.values()
    ):
        raise RuntimeError(
            "V1.3 sweep summary contains "
            "a failed invariant."
        )

    record = {
        "source": str(
            SOURCE.relative_to(ROOT)
        ),
        "source_sha256": source_sha,
        "symbolic_ir_sha256": ir_sha,
        "explicit_timing_bindings": (
            len(symbolic.bindings)
        ),
        "results": rows,
        "summary": summary,
    }

    JSON_OUTPUT.write_text(
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    write_csv(rows)

    write_markdown(
        source_sha,
        ir_sha,
        rows,
        summary,
    )

    print()
    print(
        "===== V1.3 SWEEP SUMMARY ====="
    )

    for name, value in (
        summary.items()
    ):
        print(
            f"{name} = {value}"
        )

    print()
    print(
        "V1.3 CONFIGURATION SWEEP: PASS"
    )

    print(
        "JSON:",
        JSON_OUTPUT,
    )

    print(
        "CSV :",
        CSV_OUTPUT,
    )

    print(
        "MD  :",
        MD_OUTPUT,
    )


if __name__ == "__main__":
    main()
