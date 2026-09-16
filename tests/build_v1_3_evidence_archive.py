from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_OUTPUT = (
    ROOT
    / "results/v1_3_evidence_manifest.json"
)

FINDINGS_OUTPUT = (
    ROOT
    / "results/v1_3_findings.md"
)

SWEEP = (
    ROOT
    / "results/v1_3_configuration_sweep.json"
)

INVARIANCE = (
    ROOT
    / "results/v1_3_same_source_same_ir.json"
)

FROZEN = (
    ROOT
    / "results/v1_3_canonical_hashes.json"
)


CORE_IMPLEMENTATION = [
    "lair/ast.py",
    "lair/component_graph.py",
    "lair/component_timing.py",
    "lair/parser.py",
    "lair/resolver.py",
    "lair/compiler.py",
    "lair/calyx_backend.py",
    "lair/generator_elaboration.py",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(65536),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def tracked_files() -> set[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    }


ARCHIVE_SELF_FILES = {
    "tests/build_v1_3_evidence_archive.py",
    "results/v1_3_evidence_manifest.json",
    "results/v1_3_findings.md",
}


def is_v1_3_artifact(path: str) -> bool:
    if path in ARCHIVE_SELF_FILES:
        return False

    name = Path(path).name

    return (
        "v1_3" in name
        or path
        == "docs/v1_3_component_timing_interfaces.md"
    )


def build_manifest(
    sweep: dict,
    invariance: dict,
    frozen: dict,
) -> dict:
    tracked = tracked_files()

    selected = {
        path
        for path in tracked
        if is_v1_3_artifact(path)
    }

    selected.update(
        CORE_IMPLEMENTATION
    )

    missing_from_git = [
        path
        for path in CORE_IMPLEMENTATION
        if path not in tracked
    ]

    if missing_from_git:
        raise RuntimeError(
            "Core V1.3 implementation files "
            "are not tracked: "
            + ", ".join(
                missing_from_git
            )
        )

    artifacts = []

    for relative in sorted(selected):
        path = ROOT / relative

        if not path.is_file():
            raise RuntimeError(
                f"Tracked artifact missing: "
                f"{relative}"
            )

        artifacts.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(
                    path
                ),
            }
        )

    summary = sweep[
        "summary"
    ]

    if not all(
        summary.values()
    ):
        raise RuntimeError(
            "Sweep contains failed "
            "validation invariant."
        )

    if not invariance[
        "all_source_hashes_identical"
    ]:
        raise RuntimeError(
            "Source invariance proof failed."
        )

    if not invariance[
        "all_symbolic_ir_hashes_identical"
    ]:
        raise RuntimeError(
            "Symbolic IR invariance proof failed."
        )

    if not invariance[
        "matches_frozen_manifest"
    ]:
        raise RuntimeError(
            "Invariance proof does not match "
            "frozen manifest."
        )

    if (
        sweep["source_sha256"]
        != frozen["source_sha256"]
        or sweep[
            "symbolic_ir_sha256"
        ]
        != frozen[
            "symbolic_ir_sha256"
        ]
    ):
        raise RuntimeError(
            "Sweep hashes do not match "
            "frozen canonical hashes."
        )

    if (
        sweep[
            "explicit_timing_bindings"
        ]
        != 0
    ):
        raise RuntimeError(
            "Canonical V1.3 source unexpectedly "
            "contains explicit timing bindings."
        )

    return {
        "schema_version": 1,
        "experiment": (
            "V1.3 reusable component "
            "timing interfaces"
        ),
        "canonical": {
            "source": sweep["source"],
            "source_sha256": (
                sweep["source_sha256"]
            ),
            "symbolic_ir_sha256": (
                sweep[
                    "symbolic_ir_sha256"
                ]
            ),
            "explicit_timing_bindings": (
                sweep[
                    "explicit_timing_bindings"
                ]
            ),
        },
        "validation_summary": summary,
        "invariance": {
            "all_source_hashes_identical": (
                invariance[
                    "all_source_hashes_identical"
                ]
            ),
            "all_symbolic_ir_hashes_identical": (
                invariance[
                    "all_symbolic_ir_hashes_identical"
                ]
            ),
            "matches_frozen_manifest": (
                invariance[
                    "matches_frozen_manifest"
                ]
            ),
        },
        "configuration_count": len(
            sweep["results"]
        ),
        "artifact_count": len(
            artifacts
        ),
        "artifacts": artifacts,
    }


def format_memory(
    value,
) -> str:
    if value is None:
        return "—"

    return "[" + ", ".join(
        str(x)
        for x in value
    ) + "]"


def build_findings(
    sweep: dict,
    manifest: dict,
) -> str:
    rows = sweep["results"]

    by_id = {
        row["configuration"]: row
        for row in rows
    }

    c1 = by_id["C1"]
    c2 = by_id["C2"]

    lines = [
        "# V1.3 Findings — Reusable Component Timing Interfaces",
        "",
        "## Research question",
        "",
        "Can generator-resolved timing propagate across reusable "
        "module boundaries without requiring a parent component to "
        "know the child's internal generator or control structure?",
        "",
        "## Mechanism demonstrated",
        "",
        "The canonical V1.3 source defines reusable `pair`, `tail`, "
        "and `pipeline` components. Generator latencies are absent "
        "from source. Each component exports one compiler-derived "
        "timing interface (`T_pair`, `T_tail`, or `T_total`).",
        "",
        "The resolver evaluates child components first, exports only "
        "their component timing interfaces, and resolves the parent "
        "from those interfaces. Parent timing resolution therefore "
        "does not require child generator facts or child bodies.",
        "",
        "After timing resolution and constraint checking, the current "
        "toy Calyx backend is permitted to expand already-resolved "
        "component bodies into the established A/B physical shell. "
        "V1.3 therefore demonstrates modularity at the compiler-IR "
        "timing boundary; it does not claim preservation of physical "
        "module boundaries in emitted RTL.",
        "",
        "## Canonical-program invariants",
        "",
        f"- Source: `{sweep['source']}`",
        f"- Source SHA256: `{sweep['source_sha256']}`",
        f"- Symbolic IR SHA256: "
        f"`{sweep['symbolic_ir_sha256']}`",
        f"- Explicit timing bindings in source: "
        f"`{sweep['explicit_timing_bindings']}`",
        "- The same source and same symbolic IR are used for C1-C5.",
        "",
        "## Configuration sweep",
        "",
        "| Config | A | B | T_pair | T_tail | T_total | "
        "Compiler | Measured RTL | Hardware cycles | Memory |",
        "|---|---:|---:|---:|---:|---:|---|---|---:|---|",
    ]

    for row in rows:
        decision = (
            "ACCEPT"
            if row[
                "compiler_accepted"
            ]
            else "REJECT"
        )

        cycles = (
            str(
                row[
                    "hardware_cycles"
                ]
            )
            if row[
                "hardware_cycles"
            ]
            is not None
            else "—"
        )

        measured = (
            f"{row['measured_A']}/"
            f"{row['measured_B']}"
        )

        lines.append(
            f"| {row['configuration']} "
            f"| {row['L_A']} "
            f"| {row['L_B']} "
            f"| {row['T_pair']} "
            f"| {row['T_tail']} "
            f"| {row['T_total']} "
            f"| {decision} "
            f"| {measured} "
            f"| {cycles} "
            f"| {format_memory(row['hardware_memory'])} |"
        )

    lines.extend(
        [
            "",
            "## C1/C2 reversal centerpiece",
            "",
            "C1 and C2 use the same source and symbolic IR and have "
            "the same multiset of generator latencies `{2, 5}`.",
            "",
            f"- C1 assigns A={c1['L_A']}, B={c1['L_B']}. "
            f"`T_pair={c1['T_pair']}`, "
            f"`T_tail={c1['T_tail']}`, "
            f"`T_total={c1['T_total']}`; the program is accepted.",
            f"- C2 reverses the assignment to "
            f"A={c2['L_A']}, B={c2['L_B']}. "
            f"`T_pair` remains {c2['T_pair']}, but "
            f"`T_tail` becomes {c2['T_tail']}; "
            f"`T_total` becomes {c2['T_total']}, violating "
            "the `T_total <= 8` constraint.",
            "",
            "The unchanged `pair` latency alongside the changed "
            "`tail` latency isolates the effect of reusable component "
            "structure: the parent observes exported timing interfaces "
            "rather than reconstructing child implementation timing.",
            "",
            "## Physical validation",
            "",
            "Independent Verilator checks validated the advertised "
            "go-to-done latency and functional behavior of both "
            "generated kernels for all five configurations.",
            "",
            "Accepted C1 and C3 were additionally lowered through "
            "Calyx and simulated end-to-end:",
            "",
            f"- C1: {c1['hardware_cycles']} cycles, "
            f"memory {format_memory(c1['hardware_memory'])}.",
            f"- C3: {by_id['C3']['hardware_cycles']} cycles, "
            f"memory "
            f"{format_memory(by_id['C3']['hardware_memory'])}.",
            "",
            "Rejected C2, C4, and C5 retain generated physical RTL "
            "for independent latency validation but emit no Calyx "
            "program after the timing constraint fails.",
            "",
            "## What V1.3 establishes",
            "",
            "V1.3 provides a working compiler prototype in which "
            "generator timing becomes known after source composition, "
            "is converted into timing facts, is inferred through "
            "static control, crosses reusable component boundaries "
            "through explicit timing interfaces, influences parent "
            "timing and compile-time constraints, and reaches "
            "executable Calyx for accepted configurations.",
            "",
            "This goes beyond the original trivial "
            "`generator -> read latency -> print static<L>` mechanism: "
            "timing now participates in a structured compiler IR and "
            "composes across reusable module boundaries.",
            "",
            "## Limits and non-claims",
            "",
            "- The generators and deadline constraint are synthetic.",
            "- The experiment is a mechanism/modularity prototype, "
            "not a representative accelerator benchmark.",
            "- The measured cycle counts do not establish a general "
            "performance advantage.",
            "- The current backend expands resolved reusable components "
            "into a toy A/B shell; physical RTL module boundaries are "
            "not a V1.3 claim.",
            "- V1.3 does not by itself establish novelty relative to "
            "Calyx, Piezo, Filament, Lilac, or other prior systems.",
            "- Broader generator integrations and realistic numerical "
            "kernels remain future validation work.",
            "",
            "## Reproducibility",
            "",
            "The full C1-C5 experiment is regenerated with:",
            "",
            "```bash",
            "python tests/run_v1_3_configuration_sweep.py",
            "```",
            "",
            "The source/IR invariance proof is regenerated with:",
            "",
            "```bash",
            "python tests/check_v1_3_same_source_ir.py",
            "```",
            "",
            f"The machine-readable evidence manifest covers "
            f"{manifest['artifact_count']} tracked implementation, "
            "test, source, design, and result artifacts.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    sweep = json.loads(
        SWEEP.read_text()
    )

    invariance = json.loads(
        INVARIANCE.read_text()
    )

    frozen = json.loads(
        FROZEN.read_text()
    )

    manifest = build_manifest(
        sweep,
        invariance,
        frozen,
    )

    MANIFEST_OUTPUT.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    FINDINGS_OUTPUT.write_text(
        build_findings(
            sweep,
            manifest,
        )
    )

    print(
        "===== V1.3 EVIDENCE ARCHIVE ====="
    )

    print(
        "artifacts hashed =",
        manifest[
            "artifact_count"
        ],
    )

    print(
        "source SHA =",
        manifest[
            "canonical"
        ][
            "source_sha256"
        ],
    )

    print(
        "IR SHA     =",
        manifest[
            "canonical"
        ][
            "symbolic_ir_sha256"
        ],
    )

    print()

    for name, value in (
        manifest[
            "validation_summary"
        ].items()
    ):
        print(
            f"{name} = {value}"
        )

    print()
    print(
        "V1.3 EVIDENCE ARCHIVE: PASS"
    )

    print(
        "manifest:",
        MANIFEST_OUTPUT,
    )

    print(
        "findings:",
        FINDINGS_OUTPUT,
    )


if __name__ == "__main__":
    main()
