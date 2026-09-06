#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ITERATIONS = [0, 1, 2, 4, 7]

DATA = Path("examples/v0_8_boundary_data.json")
DYNAMIC = Path("baselines/v0_8_probe_dynamic_body.futil")
STATIC = Path("baselines/v0_8_probe_static_body.futil")
RESULTS = Path("results/v0_8_boundary_probe.csv")


def make_program(static_body):
    if static_body:
        incr_group = """
    static<1> group incr {
      add_counter.left = counter.out;
      add_counter.right = 32'd1;

      counter.in = add_counter.out;
      counter.write_en = 1'b1;
    }
"""
        loop_body = """        static seq {
          incr;
        }
"""
    else:
        incr_group = """
    group incr {
      add_counter.left = counter.out;
      add_counter.right = 32'd1;

      counter.in = add_counter.out;
      counter.write_en = 1'b1;

      incr[done] = counter.done;
    }
"""
        loop_body = """        incr;
"""

    return f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

component main() -> () {{
  cells {{
    @external(1) mem = comb_mem_d1(32, 2, 1);

    counter = std_reg(32);
    add_counter = std_add(32);
    lt = std_lt(32);
  }}

  wires {{
    group init_counter {{
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init_counter[done] = counter.done;
    }}

    comb group cond {{
      mem.addr0 = 1'd0;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }}
{incr_group}
    group write_counter {{
      mem.addr0 = 1'd1;
      mem.write_data = counter.out;
      mem.write_en = 1'b1;

      write_counter[done] = mem.done;
    }}
  }}

  control {{
    seq {{
      init_counter;

      while lt.out with cond {{
{loop_body}      }}

      write_counter;
    }}
  }}
}}
'''


def set_input(n):
    data = {
        "mem": {
            "data": [n, 0],
            "format": {
                "numeric_type": "bitnum",
                "is_signed": False,
                "width": 32
            }
        }
    }

    DATA.write_text(json.dumps(data, indent=2) + "\n")


def simulate(path):
    result = subprocess.run(
        [
            "fud2",
            str(path),
            "-s",
            "sim.data=examples/v0_8_boundary_data.json",
            "--to",
            "dat",
            "--through",
            "verilator",
        ],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Simulation failed: {path}")

    text = result.stdout + "\n" + result.stderr

    cycle_match = re.search(
        r'"cycles"\s*:\s*(\d+)',
        text,
    )

    mem_match = re.search(
        r'"mem"\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]',
        text,
    )

    if cycle_match is None or mem_match is None:
        raise RuntimeError("Could not parse simulator output.")

    cycles = int(cycle_match.group(1))
    memory = [
        int(mem_match.group(1)),
        int(mem_match.group(2)),
    ]

    return cycles, memory


def main():
    DYNAMIC.write_text(make_program(False))
    STATIC.write_text(make_program(True))

    rows = []

    for n in ITERATIONS:
        print(f"\n=== N={n} ===")
        set_input(n)

        dynamic_cycles, dynamic_mem = simulate(DYNAMIC)
        static_cycles, static_mem = simulate(STATIC)

        dynamic_correct = dynamic_mem == [n, n]
        static_correct = static_mem == [n, n]

        delta = static_cycles - dynamic_cycles

        print(
            f"dynamic: cycles={dynamic_cycles}, "
            f"correct={dynamic_correct}"
        )
        print(
            f"static : cycles={static_cycles}, "
            f"correct={static_correct}"
        )
        print(f"static - dynamic = {delta}")

        rows.append({
            "runtime_iterations": n,
            "dynamic_cycles": dynamic_cycles,
            "static_cycles": static_cycles,
            "delta_cycles": delta,
            "dynamic_correct": dynamic_correct,
            "static_correct": static_correct,
        })

    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "runtime_iterations",
                "dynamic_cycles",
                "static_cycles",
                "delta_cycles",
                "dynamic_correct",
                "static_correct",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    set_input(4)

    print(f"\nSaved results to {RESULTS}")
    print("Restored probe input N=4.")


if __name__ == "__main__":
    main()
