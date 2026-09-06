#!/usr/bin/env python3

import json
import subprocess
import sys
from pathlib import Path

RESOLVER = Path("frontend/resolve_v0_4_contract.py")
RESOLUTION = Path("results/v0_4_resolution.json")

OUTPUT = Path("examples/generated/v0_5_gated_pair.futil")
GATE_REPORT = Path("results/v0_5_gate.json")


def run_resolver():
    result = subprocess.run(
        [sys.executable, str(RESOLVER)],
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    return result.returncode


def wait_group(name):
    return f"""
    static<1> group {name} {{
    }}
"""


def repeat_control(count, group_name):
    if count == 0:
        return ""

    return f"""        static repeat {count} {{
          {group_name};
        }}
"""


def emit_calyx(bindings):
    latency_a = int(bindings["L_A"])
    latency_b = int(bindings["L_B"])
    target = int(bindings["T"])
    delay_a = int(bindings["D_A"])
    delay_b = int(bindings["D_B"])

    # Sanity-check the resolved timing relations before emission.
    if target != max(latency_a, latency_b):
        raise RuntimeError("Resolved T does not equal max(L_A, L_B).")

    if delay_a != target - latency_a:
        raise RuntimeError("Resolved D_A is inconsistent.")

    if delay_b != target - latency_b:
        raise RuntimeError("Resolved D_B is inconsistent.")

    if delay_a < 0 or delay_b < 0:
        raise RuntimeError("Alignment delay cannot be negative.")

    extra_groups = ""

    if delay_a > 0:
        extra_groups += wait_group("align_wait_a")

    if delay_b > 0:
        extra_groups += wait_group("align_wait_b")

    if latency_a > 1:
        extra_groups += wait_group("kernel_wait_a")

    if latency_b > 1:
        extra_groups += wait_group("kernel_wait_b")

    branch_a = (
        repeat_control(delay_a, "align_wait_a")
        + repeat_control(latency_a - 1, "kernel_wait_a")
        + "        kernel_a_compute;\n"
    )

    branch_b = (
        repeat_control(delay_b, "align_wait_b")
        + repeat_control(latency_b - 1, "kernel_wait_b")
        + "        kernel_b_compute;\n"
    )

    program = f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

component main() -> () {{
  cells {{
    @external(1) mem = comb_mem_d1(32, 2, 1);

    x = std_reg(32);
    a_out = std_reg(32);
    b_out = std_reg(32);

    add_a = std_add(32);
    add_b = std_add(32);
    add_final = std_add(32);
  }}

  wires {{
    group load_x {{
      mem.addr0 = 1'd0;
      x.in = mem.read_data;
      x.write_en = 1'b1;
      load_x[done] = x.done;
    }}

    static<1> group kernel_a_compute {{
      add_a.left = x.out;
      add_a.right = 32'd1;

      a_out.in = add_a.out;
      a_out.write_en = 1'b1;
    }}

    static<1> group kernel_b_compute {{
      add_b.left = x.out;
      add_b.right = 32'd2;

      b_out.in = add_b.out;
      b_out.write_en = 1'b1;
    }}
{extra_groups}
    group write_result {{
      add_final.left = a_out.out;
      add_final.right = b_out.out;

      mem.addr0 = 1'd1;
      mem.write_data = add_final.out;
      mem.write_en = 1'b1;

      write_result[done] = mem.done;
    }}
  }}

  control {{
    seq {{
      load_x;

      static par {{
        static seq {{
{branch_a}        }}

        static seq {{
{branch_b}        }}
      }}

      write_result;
    }}
  }}
}}
'''

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(program)


def main():
    # Critical: remove stale hardware before contract checking.
    OUTPUT.unlink(missing_ok=True)

    resolver_code = run_resolver()

    if resolver_code != 0:
        report = {
            "status": "rejected",
            "resolver_exit_code": resolver_code,
            "hardware_emitted": False,
        }

        GATE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        GATE_REPORT.write_text(
            json.dumps(report, indent=2) + "\n"
        )

        print(
            "\nHardware emission blocked by timing contract.",
            file=sys.stderr,
        )

        sys.exit(resolver_code)

    resolution = json.loads(RESOLUTION.read_text())

    if not resolution["valid"]:
        raise RuntimeError(
            "Resolver returned success for an invalid contract."
        )

    bindings = resolution["bindings"]

    emit_calyx(bindings)

    report = {
        "status": "accepted",
        "hardware_emitted": True,
        "output": str(OUTPUT),
        "bindings": bindings,
    }

    GATE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    GATE_REPORT.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print("\nTiming contract accepted.")
    print(f"Hardware emitted: {OUTPUT}")


if __name__ == "__main__":
    main()
