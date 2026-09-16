#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from lair.compiler import compile_lair_file
from lair.generator_elaboration import (
    ToyGeneratorConfig,
)
from lair.resolver import ConstraintViolation


def parse_latency_assignments(
    assignments: list[str],
) -> dict[str, int]:
    values: dict[str, int] = {}

    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(
                "Latency assignment must have INSTANCE=CYCLES form: "
                f"{assignment}"
            )

        instance, raw_value = assignment.split(
            "=",
            1,
        )

        instance = instance.strip()

        if not instance:
            raise ValueError(
                "Latency assignment has empty instance name."
            )

        if instance in values:
            raise ValueError(
                f"Duplicate latency assignment for {instance}."
            )

        values[instance] = int(
            raw_value
        )

    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a latency-abstract .lair program through "
            "generator elaboration, timing resolution, and Calyx lowering."
        )
    )

    parser.add_argument(
        "source",
        type=Path,
    )

    parser.add_argument(
        "--latency",
        action="append",
        required=True,
        metavar="INSTANCE=CYCLES",
        help=(
            "Toy generator configuration. "
            "Repeat once per generator instance."
        ),
    )

    parser.add_argument(
        "--rtl-out",
        type=Path,
        default=Path(
            "examples/generated/v1_1_kernels.sv"
        ),
    )

    parser.add_argument(
        "--calyx-out",
        type=Path,
        default=Path(
            "examples/generated/v1_1_pair.futil"
        ),
    )

    args = parser.parse_args()

    try:
        latencies = parse_latency_assignments(
            args.latency
        )

        result = compile_lair_file(
            args.source,
            ToyGeneratorConfig(
                latencies
            ),
            rtl_output=args.rtl_out,
            calyx_output=args.calyx_out,
        )

    except ConstraintViolation as exc:
        print(
            "LAIR compilation rejected by timing constraints.",
            file=sys.stderr,
        )

        for failure in exc.failures:
            print(
                f"  [FAIL] {failure.name}: "
                f"{failure.left_value} "
                f"{failure.op} "
                f"{failure.right_value}",
                file=sys.stderr,
            )

        return 2

    except (
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        print(
            f"LAIR compilation failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print("===== V1.1 COMPILATION SUCCEEDED =====")

    print(
        "generator timing =",
        {
            item.instance: item.latency
            for item in result.elaboration.generators
        },
    )

    print(
        "timing environment =",
        result.timing_environment.to_dict(),
    )

    print(
        "resolved timing =",
        result.resolved.timing_values,
    )

    print(
        "RTL =",
        result.rtl_output,
    )

    print(
        "Calyx =",
        result.calyx_output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
