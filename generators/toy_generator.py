#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--latency", type=int, required=True)
    parser.add_argument("--name", default="toy_increment")
    parser.add_argument(
        "--out",
        default="contracts/toy_kernel.json",
    )
    args = parser.parse_args()

    if args.latency < 1:
        raise ValueError("Latency must be at least 1 cycle.")

    contract = {
        "name": args.name,
        "latency": args.latency,
        "generator": "toy_generator",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(contract, indent=2) + "\n")

    print(
        f"Generated {out}: "
        f"name={args.name}, latency={args.latency}"
    )


if __name__ == "__main__":
    main()
