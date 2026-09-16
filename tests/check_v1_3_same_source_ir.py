from dataclasses import replace
from pathlib import Path
import hashlib
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from lair.environment import TimingEnvironment
from lair.parser import parse_lair_file
from lair.resolver import (
    ConstraintViolation,
    resolve_component_program,
)


SOURCE = (
    ROOT
    / "examples/v1_3_components.lair"
)

FROZEN = (
    ROOT
    / "results/v1_3_canonical_hashes.json"
)

OUTPUT = (
    ROOT
    / "results/v1_3_same_source_same_ir.json"
)

CONFIGS = {
    "C1": (2, 5),
    "C2": (5, 2),
    "C3": (3, 3),
    "C4": (4, 7),
    "C5": (8, 3),
}


def canonical_ir_hash(program) -> str:
    canonical = json.dumps(
        program.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode()
    ).hexdigest()


def source_hash() -> str:
    return hashlib.sha256(
        SOURCE.read_bytes()
    ).hexdigest()


def main() -> None:
    frozen = json.loads(
        FROZEN.read_text()
    )

    rows = []

    for cid, (la, lb) in CONFIGS.items():
        # Parse the exact same source afresh for every configuration.
        program = parse_lair_file(
            SOURCE
        )

        src_sha = source_hash()
        ir_sha = canonical_ir_hash(
            program
        )

        if (
            src_sha
            != frozen["source_sha256"]
        ):
            raise RuntimeError(
                f"{cid}: source hash changed"
            )

        if (
            ir_sha
            != frozen["symbolic_ir_sha256"]
        ):
            raise RuntimeError(
                f"{cid}: symbolic IR hash changed"
            )

        environment = TimingEnvironment(
            {
                "L_A": la,
                "L_B": lb,
            }
        )

        accepted = True
        failures = []

        try:
            resolve_component_program(
                program,
                environment,
            )

        except ConstraintViolation as exc:
            accepted = False

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

        diagnostic = replace(
            program,
            constraints=(),
        )

        resolved = resolve_component_program(
            diagnostic,
            environment,
        )

        rows.append(
            {
                "configuration": cid,
                "generator_latencies": {
                    "A": la,
                    "B": lb,
                },
                "source_sha256": src_sha,
                "symbolic_ir_sha256": ir_sha,
                "bindings": len(
                    program.bindings
                ),
                "timing": {
                    "T_pair": (
                        resolved
                        .timing_values[
                            "T_pair"
                        ]
                    ),
                    "T_tail": (
                        resolved
                        .timing_values[
                            "T_tail"
                        ]
                    ),
                    "T_total": (
                        resolved
                        .timing_values[
                            "T_total"
                        ]
                    ),
                },
                "compiler_accepted": (
                    accepted
                ),
                "constraint_failures": (
                    failures
                ),
            }
        )

    source_hashes = {
        row["source_sha256"]
        for row in rows
    }

    ir_hashes = {
        row["symbolic_ir_sha256"]
        for row in rows
    }

    if len(source_hashes) != 1:
        raise RuntimeError(
            "Configurations do not share "
            "one source hash."
        )

    if len(ir_hashes) != 1:
        raise RuntimeError(
            "Configurations do not share "
            "one symbolic IR hash."
        )

    record = {
        "claim": (
            "C1-C5 use one unchanged "
            "latency-abstract source and "
            "one unchanged symbolic IR."
        ),
        "source": str(
            SOURCE.relative_to(ROOT)
        ),
        "source_sha256": (
            next(iter(source_hashes))
        ),
        "symbolic_ir_sha256": (
            next(iter(ir_hashes))
        ),
        "bindings": 0,
        "configurations": rows,
        "all_source_hashes_identical": True,
        "all_symbolic_ir_hashes_identical": True,
        "matches_frozen_manifest": True,
    }

    OUTPUT.write_text(
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        "===== V1.3 SAME-SOURCE / "
        "SAME-IR PROOF ====="
    )

    print(
        "source SHA =",
        record["source_sha256"],
    )

    print(
        "IR SHA     =",
        record["symbolic_ir_sha256"],
    )

    print()

    for row in rows:
        t = row["timing"]

        print(
            row["configuration"],
            f"A={row['generator_latencies']['A']}",
            f"B={row['generator_latencies']['B']}",
            f"pair={t['T_pair']}",
            f"tail={t['T_tail']}",
            f"total={t['T_total']}",
            (
                "ACCEPT"
                if row["compiler_accepted"]
                else "REJECT"
            ),
        )

    print()
    print(
        "all source hashes identical =",
        True,
    )

    print(
        "all symbolic IR hashes identical =",
        True,
    )

    print(
        "matches frozen manifest =",
        True,
    )

    print()
    print(
        "V1.3 SAME-SOURCE / "
        "SAME-IR PROOF: PASS"
    )

    print(
        "evidence =",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
