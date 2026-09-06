#!/usr/bin/env python3

import json
from pathlib import Path

A_CONTRACT = Path("contracts/kernel_a.json")
B_CONTRACT = Path("contracts/kernel_b.json")

OUTPUT = Path("baselines/v0_8_dynamic.futil")
REPORT = Path("results/v0_8_dynamic_baseline.json")


def load_latency(path):
    contract = json.loads(path.read_text())
    latency = int(contract["latency"])

    if latency < 1:
        raise ValueError(
            f"{path}: latency must be at least 1 cycle"
        )

    return contract["name"], latency


def dynamic_wait_group(name, reg):
    return f"""
    group {name} {{
      {reg}.in = {reg}.out;
      {reg}.write_en = 1'b1;
      {name}[done] = {reg}.done;
    }}
"""


def repeat_control(count, group_name):
    if count == 0:
        return ""

    return f"""          repeat {count} {{
            {group_name};
          }}
"""


def main():
    name_a, latency_a = load_latency(A_CONTRACT)
    name_b, latency_b = load_latency(B_CONTRACT)

    extra_cells = ""
    extra_groups = ""

    if latency_a > 1:
        extra_cells += "    wait_a_reg = std_reg(1);\n"
        extra_groups += dynamic_wait_group(
            "kernel_wait_a",
            "wait_a_reg",
        )

    if latency_b > 1:
        extra_cells += "    wait_b_reg = std_reg(1);\n"
        extra_groups += dynamic_wait_group(
            "kernel_wait_b",
            "wait_b_reg",
        )

    branch_a = (
        repeat_control(latency_a - 1, "kernel_wait_a")
        + "          kernel_a_compute;\n"
    )

    branch_b = (
        repeat_control(latency_b - 1, "kernel_wait_b")
        + "          kernel_b_compute;\n"
    )

    program = f'''import "primitives/core.futil";
import "primitives/memories/comb.futil";

component main() -> () {{
  cells {{
    @external(1) mem = comb_mem_d1(32, 4, 2);

    x = std_reg(32);
    counter = std_reg(32);
    a_out = std_reg(32);
    b_out = std_reg(32);

    add_a = std_add(32);
    add_b = std_add(32);
    add_counter = std_add(32);
    add_final = std_add(32);

    lt = std_lt(32);
{extra_cells}  }}

  wires {{
    group load_x {{
      mem.addr0 = 2'd0;
      x.in = mem.read_data;
      x.write_en = 1'b1;
      load_x[done] = x.done;
    }}

    group init_counter {{
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init_counter[done] = counter.done;
    }}

    comb group cond {{
      mem.addr0 = 2'd1;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }}

    group kernel_a_compute {{
      add_a.left = x.out;
      add_a.right = 32'd1;

      a_out.in = add_a.out;
      a_out.write_en = 1'b1;
      kernel_a_compute[done] = a_out.done;
    }}

    group kernel_b_compute {{
      add_b.left = x.out;
      add_b.right = 32'd2;

      b_out.in = add_b.out;
      b_out.write_en = 1'b1;
      kernel_b_compute[done] = b_out.done;
    }}

    group incr_counter {{
      add_counter.left = counter.out;
      add_counter.right = 32'd1;

      counter.in = add_counter.out;
      counter.write_en = 1'b1;
      incr_counter[done] = counter.done;
    }}
{extra_groups}
    group write_result {{
      add_final.left = a_out.out;
      add_final.right = b_out.out;

      mem.addr0 = 2'd2;
      mem.write_data = add_final.out;
      mem.write_en = 1'b1;

      write_result[done] = mem.done;
    }}
  }}

  control {{
    seq {{
      load_x;
      init_counter;

      while lt.out with cond {{
        seq {{
          par {{
            seq {{
{branch_a}            }}

            seq {{
{branch_b}            }}
          }}

          incr_counter;
        }}
      }}

      write_result;
    }}
  }}
}}
'''

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(program)

    report = {
        "baseline": "fully_dynamic",
        "kernel_a": {
            "name": name_a,
            "latency": latency_a,
        },
        "kernel_b": {
            "name": name_b,
            "latency": latency_b,
        },
        "uses_symbolic_alignment": False,
        "uses_static_control": False,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print("Emitted fully dynamic baseline")
    print(f"L_A = {latency_a}")
    print(f"L_B = {latency_b}")
    print(f"Hardware: {OUTPUT}")


if __name__ == "__main__":
    main()
