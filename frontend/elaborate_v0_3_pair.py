#!/usr/bin/env python3

import json
from pathlib import Path

A_CONTRACT = Path("contracts/kernel_a.json")
B_CONTRACT = Path("contracts/kernel_b.json")

OUTPUT = Path("examples/generated/v0_3_pair.futil")
REPORT = Path("results/v0_3_pair_elaboration.json")


def load_latency(path):
    contract = json.loads(path.read_text())
    latency = int(contract["latency"])

    if latency < 1:
        raise ValueError(
            f"{path}: latency must be at least 1 cycle"
        )

    return contract["name"], latency


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


def main():
    name_a, latency_a = load_latency(A_CONTRACT)
    name_b, latency_b = load_latency(B_CONTRACT)

    target = max(latency_a, latency_b)

    delay_a = target - latency_a
    delay_b = target - latency_b

    # Declare only groups that will actually be used.
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

    report = {
        "kernel_a": {
            "name": name_a,
            "latency": latency_a,
            "alignment_delay": delay_a,
        },
        "kernel_b": {
            "name": name_b,
            "latency": latency_b,
            "alignment_delay": delay_b,
        },
        "target_latency": target,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print(f"L_A = {latency_a}")
    print(f"L_B = {latency_b}")
    print(f"T   = {target}")
    print(f"D_A = {delay_a}")
    print(f"D_B = {delay_b}")
    print(f"Emitted {OUTPUT}")
    print(f"Recorded {REPORT}")


if __name__ == "__main__":
    main()
