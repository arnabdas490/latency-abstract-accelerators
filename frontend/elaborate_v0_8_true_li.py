#!/usr/bin/env python3

import json
from pathlib import Path

A_CONTRACT = Path("contracts/kernel_a.json")
B_CONTRACT = Path("contracts/kernel_b.json")

OUTPUT = Path("baselines/v0_8_true_li.futil")
REPORT = Path("results/v0_8_true_li_baseline.json")


def load_latency(path):
    contract = json.loads(path.read_text())
    latency = int(contract["latency"])

    if latency < 1:
        raise ValueError("Latency must be >= 1")

    return latency


def make_kernel(name, latency, add_constant):
    if latency > 1:
        extra_cell = "    wait_reg = std_reg(1);\n"

        wait_group = """
    group wait_cycle {
      wait_reg.in = wait_reg.out;
      wait_reg.write_en = 1'b1;
      wait_cycle[done] = wait_reg.done;
    }
"""

        wait_control = f"""      repeat {latency - 1} {{
        wait_cycle;
      }}
"""
    else:
        extra_cell = ""
        wait_group = ""
        wait_control = ""

    return f'''
component {name}(x: 32) -> (out: 32) {{
  cells {{
    result = std_reg(32);
    add = std_add(32);
{extra_cell}  }}

  wires {{
    group compute {{
      add.left = x;
      add.right = 32'd{add_constant};

      result.in = add.out;
      result.write_en = 1'b1;

      compute[done] = result.done;
    }}
{wait_group}
    out = result.out;
  }}

  control {{
    seq {{
{wait_control}      compute;
    }}
  }}
}}
'''


def main():
    latency_a = load_latency(A_CONTRACT)
    latency_b = load_latency(B_CONTRACT)

    # Only the generated child components know their concrete latencies.
    kernel_a = make_kernel("kernel_a", latency_a, 1)
    kernel_b = make_kernel("kernel_b", latency_b, 2)

    # IMPORTANT:
    # This parent composition contains no L_A, L_B, T, D_A, or D_B.
    parent = '''
component main() -> () {
  cells {
    @external(1) mem = comb_mem_d1(32, 4, 2);

    x = std_reg(32);
    counter = std_reg(32);

    a = kernel_a();
    b = kernel_b();

    add_counter = std_add(32);
    add_final = std_add(32);

    lt = std_lt(32);
  }

  wires {
    group load_x {
      mem.addr0 = 2'd0;
      x.in = mem.read_data;
      x.write_en = 1'b1;
      load_x[done] = x.done;
    }

    group init_counter {
      counter.in = 32'd0;
      counter.write_en = 1'b1;
      init_counter[done] = counter.done;
    }

    comb group cond {
      mem.addr0 = 2'd1;
      lt.left = counter.out;
      lt.right = mem.read_data;
    }

    group incr_counter {
      add_counter.left = counter.out;
      add_counter.right = 32'd1;

      counter.in = add_counter.out;
      counter.write_en = 1'b1;

      incr_counter[done] = counter.done;
    }

    group write_result {
      add_final.left = a.out;
      add_final.right = b.out;

      mem.addr0 = 2'd2;
      mem.write_data = add_final.out;
      mem.write_en = 1'b1;

      write_result[done] = mem.done;
    }
  }

  control {
    seq {
      load_x;
      init_counter;

      while lt.out with cond {
        seq {
          par {
            invoke a(x=x.out)();
            invoke b(x=x.out)();
          }

          incr_counter;
        }
      }

      write_result;
    }
  }
}
'''

    program = (
        'import "primitives/core.futil";\n'
        'import "primitives/memories/comb.futil";\n'
        + kernel_a
        + kernel_b
        + parent
    )

    OUTPUT.write_text(program)

    report = {
        "baseline": "true_latency_insensitive",
        "kernel_a_internal_latency": latency_a,
        "kernel_b_internal_latency": latency_b,
        "parent_knows_latency": False,
        "parent_uses_symbolic_alignment": False,
        "parent_control": "dynamic invoke + dynamic par"
    }

    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print("Emitted true latency-insensitive baseline")
    print(f"Kernel A internal latency = {latency_a}")
    print(f"Kernel B internal latency = {latency_b}")
    print("Parent timing knowledge = NONE")
    print(f"Hardware: {OUTPUT}")


if __name__ == "__main__":
    main()
